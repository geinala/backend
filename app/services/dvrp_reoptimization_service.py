from __future__ import annotations

import math
from datetime import datetime, timezone
import json
from typing import Any, Literal

from app.constants.simulation_log_event_types import ROUTE_REOPTIMIZED
from app.lib.logging.logging import get_logger
from app.lib.route_geometry import decode_polyline
from app.models.courier import Courier
from app.models.courier_route import CourierRoute
from app.models.simulation import Simulation
from app.models.reoptimization_event import ReoptimizationEvent, ReoptimizationOutcomeEnum
from app.models.route import RouteLeg
from app.repositories.node_repository import NodeRepository
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.repositories.route_repository import RouteRepository
from app.repositories.simulation_log_repository import SimulationLogRepository
from app.repositories.simulation_repository import SimulationRepository
from app.schemas.optimization_run_schema import CreateOptimizationRun
from app.schemas.simulation_log_schema import CreateSimulationLog
from app.services.matrix_service import MatrixService
from app.services.solver import GreedySolver, SolverProblem, TabuSearchSolver
from app.services.tomtom_service import TomTomService


logger = get_logger(__name__)


class DVRPReoptimizationService:
    def __init__(
        self,
        route_repository: RouteRepository,
        node_repository: NodeRepository,
        simulation_repository: SimulationRepository,
        matrix_service: MatrixService,
        tomtom_service: TomTomService,
        optimization_run_repository: OptimizationRunRepository,
    ):
        self.route_repository = route_repository
        self.node_repository = node_repository
        self.simulation_repository = simulation_repository
        self.matrix_service = matrix_service
        self.tomtom_service = tomtom_service
        self.optimization_run_repository = optimization_run_repository

    async def handle_congestion(
        self,
        *,
        simulation_id: str,
        route_leg_id: int,
        courier_route_id: int,
        courier_id: int,
        current_sequence: int,
        delay_seconds: int,
        traffic_incident_id: int | None = None,
        congestion_check_id: int | None = None,
    ) -> dict[str, Any]:
        snapshot = self.route_repository.get_courier_route_snapshot(courier_route_id)
        if snapshot is None:
            raise ValueError(f"Courier route {courier_route_id} not found for simulation {simulation_id}.")

        current_route_leg = self.route_repository.get_route_leg_by_id(route_leg_id)
        if current_route_leg is None:
            raise ValueError(f"Route leg {route_leg_id} not found for simulation {simulation_id}.")

        nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        node_by_matrix_index = {node.matrix_index: node for node in nodes}
        node_by_id = {node.id: node for node in nodes}

        destination_node = node_by_id.get(current_route_leg.to_node_id)
        if destination_node is None:
            raise ValueError(f"Destination node {current_route_leg.to_node_id} could not be loaded.")

        route_node_indices = list(snapshot["routes"])
        if destination_node.matrix_index not in route_node_indices:
            raise ValueError(
                f"Destination matrix index {destination_node.matrix_index} is missing from courier route {courier_route_id}."
            )

        destination_route_index = route_node_indices.index(destination_node.matrix_index)
        remaining_node_indices = route_node_indices[destination_route_index + 1 : -1]

        old_future_legs = self.route_repository.get_route_legs_by_courier_route_id(courier_route_id)
        old_future_distance_in_meters = sum(
            route_leg.distance_in_meters for route_leg in old_future_legs if route_leg.sequence > current_sequence
        )
        old_future_time_in_seconds = sum(
            route_leg.travel_time_in_seconds for route_leg in old_future_legs if route_leg.sequence > current_sequence
        )

        logger.info(
            {
                "event_type": "dvrp_reoptimization_started",
                "simulation_id": simulation_id,
                "courier_route_id": courier_route_id,
                "courier_id": courier_id,
                "route_leg_id": route_leg_id,
                "current_sequence": current_sequence,
                "delay_seconds": delay_seconds,
                "destination_node_id": current_route_leg.to_node_id,
                "destination_matrix_index": destination_node.matrix_index,
                "remaining_node_count": len(remaining_node_indices),
                "route_before_total_distance_in_meters": snapshot["total_distance_in_meters"],
                "route_before_total_time_in_seconds": snapshot["total_time_in_seconds"],
                "future_distance_in_meters": old_future_distance_in_meters,
                "future_time_in_seconds": old_future_time_in_seconds,
                "current_route_leg": {
                    "id": current_route_leg.id,
                    "sequence": current_route_leg.sequence,
                    "origin_latitude": current_route_leg.origin_latitude,
                    "origin_longitude": current_route_leg.origin_longitude,
                    "destination_latitude": current_route_leg.destination_latitude,
                    "destination_longitude": current_route_leg.destination_longitude,
                },
            }
        )

        self.route_repository.update_route_leg_delay(route_leg_id, delay_seconds)

        if not remaining_node_indices:
            self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)
            final_optimization_run = self._store_final_reoptimization_run(
                simulation_id=simulation_id,
                congestion_check_id=congestion_check_id,
                before_total_distance_in_meters=snapshot["total_distance_in_meters"],
                before_total_time_in_seconds=snapshot["total_time_in_seconds"],
                after_total_distance_in_meters=snapshot["total_distance_in_meters"],
                after_total_time_in_seconds=snapshot["total_time_in_seconds"] + delay_seconds,
                algorithm_used="tabu_search",
                computation_time_in_ms=0.0,
                total_nodes_explored=0,
            )
            return await self._finalize_reoptimization(
                simulation_id=simulation_id,
                courier_route_id=courier_route_id,
                courier_id=courier_id,
                current_route_leg=current_route_leg,
                current_sequence=current_sequence,
                delay_seconds=delay_seconds,
                congestion_check_id=congestion_check_id,
                route_leg_id=route_leg_id,
                algorithm_used="tabu_search", # TODO: consider using a different algorithm identifier for pure resequencing updates in the future
                outcome=ReoptimizationOutcomeEnum.duration_updated,
                before_total_distance_in_meters=snapshot["total_distance_in_meters"],
                before_total_time_in_seconds=snapshot["total_time_in_seconds"],
                after_total_distance_in_meters=snapshot["total_distance_in_meters"],
                after_total_time_in_seconds=snapshot["total_time_in_seconds"] + delay_seconds,
                before_computation_time_in_ms=0.0,
                total_nodes_explored=0,
                optimization_run_id=final_optimization_run.id,
            )

        time_matrix = await self.matrix_service.build_time_matrix(simulation_id)
        selected_node_indices = [destination_node.matrix_index, *remaining_node_indices, 0]
        submatrix = self._build_submatrix(time_matrix, selected_node_indices)
        demands = [
            0,
            *[
                self._conversion_demand_to_grams(node_by_matrix_index[matrix_index].demand)
                for matrix_index in remaining_node_indices
            ],
            0,
        ]

        courier = self.route_repository.db.query(Courier).filter(Courier.id == courier_id).first()
        if courier is None:
            raise ValueError(f"Courier {courier_id} could not be loaded.")

        greedy_candidate = self._build_reoptimization_candidate(
            algorithm="greedy",
            solver=GreedySolver(),
            problem=SolverProblem(
                time_matrix=submatrix,
                demands=demands,
                courier=courier,
                start_index=0,
                end_index=len(selected_node_indices) - 1,
            ),
            selected_node_indices=selected_node_indices,
            node_by_matrix_index=node_by_matrix_index,
            current_departure_time=current_route_leg.arrival_time,
        )

        tabu_candidate = self._build_reoptimization_candidate(
            algorithm="tabu_search",
            solver=TabuSearchSolver(),
            problem=SolverProblem(
                time_matrix=submatrix,
                demands=demands,
                courier=courier,
                start_index=0,
                end_index=len(selected_node_indices) - 1,
            ),
            selected_node_indices=selected_node_indices,
            node_by_matrix_index=node_by_matrix_index,
            current_departure_time=current_route_leg.arrival_time,
        )

        final_candidate = tabu_candidate
        final_optimization_run = self._store_final_reoptimization_run(
            simulation_id=simulation_id,
            congestion_check_id=congestion_check_id,
            before_total_distance_in_meters=snapshot["total_distance_in_meters"],
            before_total_time_in_seconds=snapshot["total_time_in_seconds"],
            after_total_distance_in_meters=snapshot["total_distance_in_meters"],
            after_total_time_in_seconds=snapshot["total_time_in_seconds"] + delay_seconds,
            algorithm_used=final_candidate["algorithm"],
            computation_time_in_ms=float(final_candidate["computation_time_in_ms"]),
            total_nodes_explored=int(final_candidate["nodes_explored"]),
        )
        final_total_distance_in_meters = int(final_candidate["summary"]["lengthInMeters"])
        final_total_time_in_seconds = int(final_candidate["summary"]["travelTimeInSeconds"])
        reoptimized_total_time_in_seconds = (
            snapshot["total_time_in_seconds"]
            + delay_seconds
            + (final_total_time_in_seconds - old_future_time_in_seconds)
        )

        logger.info(
            {
                "event_type": "dvrp_reoptimization_candidates_evaluated",
                "simulation_id": simulation_id,
                "courier_route_id": courier_route_id,
                "courier_id": courier_id,
                "route_leg_id": route_leg_id,
                "current_sequence": current_sequence,
                "delay_seconds": delay_seconds,
                "old_future_distance_in_meters": old_future_distance_in_meters,
                "old_future_time_in_seconds": old_future_time_in_seconds,
                "greedy_candidate": {
                    "algorithm": greedy_candidate["algorithm"],
                    "distance_in_meters": int(greedy_candidate["summary"]["lengthInMeters"]),
                    "travel_time_in_seconds": int(greedy_candidate["summary"]["travelTimeInSeconds"]),
                    "computation_time_in_ms": round(float(greedy_candidate["computation_time_in_ms"]), 3),
                    "nodes_explored": int(greedy_candidate["nodes_explored"]),
                },
                "tabu_candidate": {
                    "algorithm": tabu_candidate["algorithm"],
                    "distance_in_meters": int(tabu_candidate["summary"]["lengthInMeters"]),
                    "travel_time_in_seconds": int(tabu_candidate["summary"]["travelTimeInSeconds"]),
                    "computation_time_in_ms": round(float(tabu_candidate["computation_time_in_ms"]), 3),
                    "nodes_explored": int(tabu_candidate["nodes_explored"]),
                },
                "selected_algorithm": final_candidate["algorithm"],
                "selected_distance_in_meters": final_total_distance_in_meters,
                "selected_travel_time_in_seconds": final_total_time_in_seconds,
                "reoptimized_total_time_in_seconds": reoptimized_total_time_in_seconds,
                "baseline_total_time_in_seconds": snapshot["total_time_in_seconds"],
            }
        )

        logger.info(
            {
                "event_type": "dvrp_reoptimization_decision",
                "simulation_id": simulation_id,
                "courier_route_id": courier_route_id,
                "courier_id": courier_id,
                "route_leg_id": route_leg_id,
                "current_sequence": current_sequence,
                "decision": "duration_updated",
                "reason": "resequence_temporarily_disabled",
                "baseline_total_time_in_seconds": snapshot["total_time_in_seconds"],
                "reoptimized_total_time_in_seconds": reoptimized_total_time_in_seconds,
                "delay_seconds": delay_seconds,
                "selected_algorithm": final_candidate["algorithm"],
                "would_resequence": reoptimized_total_time_in_seconds < snapshot["total_time_in_seconds"],
            }
        )

        self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)
        return await self._finalize_reoptimization(
            simulation_id=simulation_id,
            courier_route_id=courier_route_id,
            courier_id=courier_id,
            current_route_leg=current_route_leg,
            current_sequence=current_sequence,
            delay_seconds=delay_seconds,
            congestion_check_id=congestion_check_id,
            route_leg_id=route_leg_id,
            optimization_run_id=final_optimization_run.id,
            algorithm_used=final_candidate["algorithm"], # type: ignore
            outcome=ReoptimizationOutcomeEnum.duration_updated,
            before_total_distance_in_meters=snapshot["total_distance_in_meters"],
            before_total_time_in_seconds=snapshot["total_time_in_seconds"],
            after_total_distance_in_meters=snapshot["total_distance_in_meters"],
            after_total_time_in_seconds=snapshot["total_time_in_seconds"] + delay_seconds,
            before_computation_time_in_ms=float(final_candidate["computation_time_in_ms"]),
            total_nodes_explored=int(final_candidate["nodes_explored"]),
        )

    async def _finalize_reoptimization(
        self,
        *,
        simulation_id: str,
        courier_route_id: int,
        courier_id: int,
        current_route_leg: RouteLeg,
        current_sequence: int,
        delay_seconds: int,
        congestion_check_id: int | None,
        route_leg_id: int,
        optimization_run_id: int,
        algorithm_used: Literal["greedy", "tabu_search"],
        outcome: ReoptimizationOutcomeEnum,
        before_total_distance_in_meters: int,
        before_total_time_in_seconds: int,
        after_total_distance_in_meters: int,
        after_total_time_in_seconds: int,
        before_computation_time_in_ms: float,
        total_nodes_explored: int,
    ) -> dict[str, Any]:
        simulation = self.simulation_repository.db.query(Simulation).filter_by(id=simulation_id).first()
        if simulation is None:
            raise ValueError(f"Simulation {simulation_id} could not be loaded.")

        current_route = self.route_repository.db.query(CourierRoute).filter(CourierRoute.id == courier_route_id).first()
        if current_route is None:
            raise ValueError(f"Courier route {courier_route_id} could not be loaded.")

        current_route.total_distance_in_meters = after_total_distance_in_meters
        current_route.total_time_in_seconds = after_total_time_in_seconds

        courier_position_payload = self._build_courier_position_payload(
            courier_id=courier_id,
            route_leg=current_route_leg,
        )

        self.route_repository.db.add(
            ReoptimizationEvent(
                simulation_id=simulation.id,
                optimization_run_id=optimization_run_id,
                congestion_check_id=congestion_check_id,
                reopt_sequence=int(getattr(simulation, "total_reoptimized_routes", 0) or 0) + 1,
                triggered_at=datetime.now(timezone.utc),
                before_route_id=courier_route_id,
                before_total_distance_in_meters=before_total_distance_in_meters,
                before_total_time_in_seconds=before_total_time_in_seconds,
                after_route_id=courier_route_id,
                after_total_distance_in_meters=after_total_distance_in_meters,
                after_total_time_in_seconds=after_total_time_in_seconds,
                courier_position=courier_position_payload,
                distance_saved_in_meters=before_total_distance_in_meters - after_total_distance_in_meters,
                time_saved_in_seconds=before_total_time_in_seconds - after_total_time_in_seconds,
                algorithm_used=algorithm_used,
                computation_time_in_ms=before_computation_time_in_ms,
                outcome=outcome.value,
                trigger_route_leg_id=route_leg_id,
                total_incident_delay_in_seconds=delay_seconds,
            )
        )

        await self.simulation_repository.update_simulation_fields(
            simulation_id,
            {
                "final_total_distance_in_meters": after_total_distance_in_meters,
                "final_total_duration_in_seconds": after_total_time_in_seconds,
                "distance_improvement_in_meters": int(getattr(simulation, "initial_total_distance_in_meters", 0) or 0) - after_total_distance_in_meters,
                "duration_improvement_in_seconds": int(getattr(simulation, "initial_total_duration_in_seconds", 0) or 0) - after_total_time_in_seconds,
                "total_reoptimized_routes": int(getattr(simulation, "total_reoptimized_routes", 0) or 0) + 1,
                "total_incidents_affecting_routes": int(getattr(simulation, "total_incidents_affecting_routes", 0) or 0) + 1,
            },
        )

        await SimulationLogRepository(self.route_repository.db).create_log(
            CreateSimulationLog(
                simulation_id=simulation_id,
                courier_route_id=courier_route_id,
                courier_id=courier_id,
                event_type=ROUTE_REOPTIMIZED,
                title=f"Route duration updated for courier route {courier_route_id}",
                description=(
                    f"Route leg {route_leg_id} was delayed by {delay_seconds} seconds and the route duration was "
                    f"updated without changing the node sequence."
                ),
                latitude=float(current_route_leg.destination_latitude),
                longitude=float(current_route_leg.destination_longitude),
                metadata=json.dumps(
                    {
                        "outcome": outcome.value,
                        "optimization_run_id": optimization_run_id,
                        "congestion_check_id": congestion_check_id,
                        "trigger_route_leg_id": route_leg_id,
                        "delay_seconds": delay_seconds,
                        "before_total_time_in_seconds": before_total_time_in_seconds,
                        "after_total_time_in_seconds": after_total_time_in_seconds,
                        "algorithm_used": algorithm_used,
                    }
                ),
            )
        )

        logger.info(
            {
                "event_type": "dvrp_reoptimization_completed",
                "simulation_id": simulation_id,
                "courier_route_id": courier_route_id,
                "courier_id": courier_id,
                "route_leg_id": route_leg_id,
                "current_sequence": current_sequence,
                "algorithm_used": algorithm_used,
                "outcome": outcome.value,
                "before_total_time_in_seconds": before_total_time_in_seconds,
                "after_total_time_in_seconds": after_total_time_in_seconds,
                "before_total_distance_in_meters": before_total_distance_in_meters,
                "after_total_distance_in_meters": after_total_distance_in_meters,
                "improvement_in_distance_in_meters": before_total_distance_in_meters - after_total_distance_in_meters,
                "improvement_in_time_in_seconds": before_total_time_in_seconds - after_total_time_in_seconds,
                "distance_saved_in_meters": before_total_distance_in_meters - after_total_distance_in_meters,
                "time_saved_in_seconds": before_total_time_in_seconds - after_total_time_in_seconds,
                "courier_position": courier_position_payload,
                "reopt_sequence": int(getattr(simulation, "total_reoptimized_routes", 0) or 0) + 1,
            }
        )

        return {
            "simulation_id": simulation_id,
            "courier_route_id": courier_route_id,
            "algorithm_used": algorithm_used,
            "outcome": outcome.value,
            "before_total_time_in_seconds": before_total_time_in_seconds,
            "after_total_time_in_seconds": after_total_time_in_seconds,
            "before_total_distance_in_meters": before_total_distance_in_meters,
            "after_total_distance_in_meters": after_total_distance_in_meters,
        }

    def _store_final_reoptimization_run(
        self,
        *,
        simulation_id: str,
        congestion_check_id: int | None,
        before_total_distance_in_meters: int,
        before_total_time_in_seconds: int,
        after_total_distance_in_meters: int,
        after_total_time_in_seconds: int,
        algorithm_used: Literal["greedy", "tabu_search"],
        computation_time_in_ms: float,
        total_nodes_explored: int,
    ) -> Any:
        from uuid import UUID

        created_runs = self.optimization_run_repository.bulk_insert_optimization_runs(
            [
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="reoptimization",
                    algorithm=algorithm_used,
                    trigger_type="traffic_incident",
                    total_distance_in_meters=after_total_distance_in_meters,
                    total_travel_time_in_seconds=after_total_time_in_seconds,
                    computation_time_in_ms=computation_time_in_ms,
                    total_nodes_explored=total_nodes_explored,
                    congestion_check_id=congestion_check_id,
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                    triggered_at=datetime.now(timezone.utc),
                )
            ]
        )

        return created_runs[0]

    @staticmethod
    def _calculate_bearing_degrees(
        start_latitude: float,
        start_longitude: float,
        end_latitude: float,
        end_longitude: float,
    ) -> int:
        start_latitude_radians = math.radians(start_latitude)
        end_latitude_radians = math.radians(end_latitude)
        delta_longitude_radians = math.radians(end_longitude - start_longitude)

        x_component = math.sin(delta_longitude_radians) * math.cos(end_latitude_radians)
        y_component = (
            math.cos(start_latitude_radians) * math.sin(end_latitude_radians)
            - math.sin(start_latitude_radians)
            * math.cos(end_latitude_radians)
            * math.cos(delta_longitude_radians)
        )

        bearing = (math.degrees(math.atan2(x_component, y_component)) + 360.0) % 360.0
        return int(round(bearing)) % 360

    @classmethod
    def _build_courier_position_payload(cls, courier_id: int, route_leg: RouteLeg) -> str:
        route_points = decode_polyline(route_leg.encoded_polyline, route_leg.encoded_polyline_precision)

        if len(route_points) >= 2:
            latitude, longitude = route_points[0]
            bearing = cls._calculate_bearing_degrees(
                start_latitude=route_points[0][0],
                start_longitude=route_points[0][1],
                end_latitude=route_points[1][0],
                end_longitude=route_points[1][1],
            )
        else:
            latitude = float(route_leg.origin_latitude)
            longitude = float(route_leg.origin_longitude)
            bearing = cls._calculate_bearing_degrees(
                start_latitude=float(route_leg.origin_latitude),
                start_longitude=float(route_leg.origin_longitude),
                end_latitude=float(route_leg.destination_latitude),
                end_longitude=float(route_leg.destination_longitude),
            )

        return json.dumps(
            [
                {
                    "courier_id": courier_id,
                    "lat": round(latitude, 6),
                    "lng": round(longitude, 6),
                    "bearing": bearing,
                }
            ]
        )

    def _build_reoptimization_candidate(
        self,
        *,
        algorithm: str,
        solver: GreedySolver | TabuSearchSolver,
        problem: SolverProblem,
        selected_node_indices: list[int],
        node_by_matrix_index: dict[int, Any],
        current_departure_time: datetime,
    ) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc)
        manager, routing, solution = solver.solve(problem)
        computation_time_in_ms = max((datetime.now(timezone.utc) - started_at).total_seconds() * 1000, 0.0)

        if solution is None:
            raise RuntimeError(f"No {algorithm} solution could be found for reoptimization.")

        route = self._parse_solver_route(manager, routing, solution, selected_node_indices)
        route_points = ":".join(self._build_route_points(route, node_by_matrix_index))
        route_response = self.tomtom_service.generate_routes(route_points, current_departure_time.isoformat())
        summary = route_response["routes"][0]["summary"]

        return {
            "algorithm": algorithm,
            "route": route,
            "route_response": route_response,
            "summary": summary,
            "computation_time_in_ms": computation_time_in_ms,
            "nodes_explored": len(route),
        }

    def _store_reoptimization_comparison_runs(
        self,
        *,
        simulation_id: str,
        courier_route_id: int,
        before_total_distance_in_meters: int,
        before_total_time_in_seconds: int,
        greedy_candidate: dict[str, Any],
        tabu_candidate: dict[str, Any],
    ) -> list[Any]:
        from uuid import UUID

        return self.optimization_run_repository.bulk_insert_optimization_runs(
            [
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="reoptimization",
                    algorithm="greedy",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=int(greedy_candidate["summary"]["lengthInMeters"]),
                    total_travel_time_in_seconds=int(greedy_candidate["summary"]["travelTimeInSeconds"]),
                    computation_time_in_ms=float(greedy_candidate["computation_time_in_ms"]),
                    total_nodes_explored=int(greedy_candidate["nodes_explored"]),
                    congestion_check_id=None,
                    triggered_at=datetime.now(timezone.utc),
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                ),
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="reoptimization",
                    algorithm="tabu_search",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=int(tabu_candidate["summary"]["lengthInMeters"]),
                    total_travel_time_in_seconds=int(tabu_candidate["summary"]["travelTimeInSeconds"]),
                    computation_time_in_ms=float(tabu_candidate["computation_time_in_ms"]),
                    total_nodes_explored=int(tabu_candidate["nodes_explored"]),
                    congestion_check_id=None,
                    triggered_at=datetime.now(timezone.utc),
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                ),
            ]
        )

    def _parse_solver_route(
        self,
        manager: Any,
        routing: Any,
        solution: Any,
        selected_node_indices: list[int],
    ) -> list[int]:
        index = routing.Start(0)
        route_nodes: list[int] = []

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_nodes.append(int(selected_node_indices[int(node_index)]))
            index = solution.Value(routing.NextVar(index))

        route_nodes.append(int(selected_node_indices[int(manager.IndexToNode(index))]))
        return route_nodes

    def _build_route_points(
        self,
        route_nodes: list[int],
        node_by_matrix_index: dict[int, Any],
    ) -> list[str]:
        route_points: list[str] = []

        for node_index in route_nodes:
            node = node_by_matrix_index.get(node_index)

            if node is not None:
                route_points.append(f"{node.latitude},{node.longitude}")

        return route_points

    def _build_submatrix(self, time_matrix: list[list[int]], node_indices: list[int]) -> list[list[int]]:
        return [
            [time_matrix[origin_index][destination_index] for destination_index in node_indices]
            for origin_index in node_indices
        ]

    def _conversion_demand_to_grams(self, demand: float) -> int:
        return round(demand * 1000)