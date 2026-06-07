from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Literal

from app.configs.environment_configuration import get_environment_configuration
from app.constants.simulation_log_event_types import ROUTE_REOPTIMIZED
from app.lib.logging.logging import get_logger
from app.lib.route_geometry import decode_polyline
from app.models.courier import Courier
from app.models.courier_route import CourierRoute
from app.models.simulation import Simulation
from app.models.reoptimization_event import ReoptimizationEvent, ReoptimizationOutcomeEnum
from app.models.route import RouteLeg, RouteStatusEnum
from app.repositories.courier_route_repository import CourierRouteRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.repositories.route_repository import RouteRepository
from app.repositories.simulation_log_repository import SimulationLogRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.schemas.courier_route_schema import CreateCourierRoute
from app.schemas.optimization_run_schema import CreateOptimizationRun
from app.schemas.route_schema import CreateRouteLeg
from app.schemas.simulation_log_schema import CreateSimulationLog
from app.schemas.simulation_schema import UpdateSimulationSchema
from app.schemas.solution_schema import CreateSolution
from app.services.matrix_service import MatrixService
from app.services.solver import GreedySolver, SolverProblem, TabuSearchSolver
from app.services.tomtom_service import TomTomService
from app.models.node import Node
from app.lib.date_converter import format_departure_time


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
        courier_route_repository: CourierRouteRepository,
        solution_repository: SolutionRepository,
    ):
        self.settings = get_environment_configuration()
        self.route_repository = route_repository
        self.node_repository = node_repository
        self.simulation_repository = simulation_repository
        self.matrix_service = matrix_service
        self.tomtom_service = tomtom_service
        self.optimization_run_repository = optimization_run_repository
        self.courier_route_repository = courier_route_repository
        self.solution_repository = solution_repository

    async def handle_congestion(
        self,
        *,
        simulation_id: str,
        route_leg_id: int,
        courier_route_id: int,
        courier_id: int,
        current_sequence: int,
        delay_seconds: int,
        congestion_check_id: int | None = None,
        force_duration_update_only: bool = False,
        is_baseline: bool,
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
        
        origin_node = node_by_id.get(current_route_leg.from_node_id)
        if origin_node is None:
            raise ValueError(f"Origin node {current_route_leg.from_node_id} could not be loaded.")

        route_node_indices = list(snapshot["routes"])
        
        if destination_node.matrix_index not in route_node_indices:
            raise ValueError(
                f"Destination matrix index {destination_node.matrix_index} is missing from courier route {courier_route_id}."
            )

        destination_route_index = -1
        for i in range(len(route_node_indices) - 1):
            if route_node_indices[i] == origin_node.matrix_index and route_node_indices[i+1] == destination_node.matrix_index:
                destination_route_index = i + 1
                break
            
        if destination_route_index == -1:
            destination_route_index = route_node_indices.index(destination_node.matrix_index)
        
        remaining_node_indices = route_node_indices[destination_route_index + 1 : -1]

        old_future_legs = self.route_repository.get_route_legs_by_courier_route_id(courier_route_id)
        old_future_distance_in_meters = sum(
            route_leg.distance_in_meters for route_leg in old_future_legs if route_leg.sequence > current_sequence
        )
        old_future_time_in_seconds = sum(
            route_leg.travel_time_in_seconds for route_leg in old_future_legs if route_leg.sequence > current_sequence
        )
        baseline_total_distance_in_meters = int(snapshot["total_distance_in_meters"])
        baseline_total_time_in_seconds = int(snapshot["total_time_in_seconds"])
        baseline_with_delay_total_time_in_seconds = baseline_total_time_in_seconds + delay_seconds

        logger.info({
            "event_type": "DEBUG_ROUTE_ORIGINAL",
            "courier_route_id": courier_route_id,
            "route_version": snapshot["route_version"],
            "route_node_indices": route_node_indices,
            "origin_node_matrix_index": origin_node.matrix_index if origin_node else None,
            "current_sequence": current_sequence
        })

        logger.info(
            {
                "event_type": "dvrp_reoptimization_started",
                "simulation_id": simulation_id,
                "courier_route_id": courier_route_id,
                "courier_id": courier_id,
                "route_leg_id": route_leg_id,
                "current_sequence": current_sequence,
                "delay_seconds": delay_seconds,
                "force_duration_update_only": force_duration_update_only,
                "origin_node_id": current_route_leg.from_node_id,
                "origin_matrix_index": origin_node.matrix_index,
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

        logger.info(f"Processing reoptimization for baseline: {is_baseline}")
        if force_duration_update_only or not remaining_node_indices or is_baseline:
            self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)
            final_optimization_run = self._store_no_solver_run(
                simulation_id=simulation_id,
                congestion_check_id=congestion_check_id,
                before_total_distance_in_meters=baseline_total_distance_in_meters,
                before_total_time_in_seconds=baseline_total_time_in_seconds,
                after_total_distance_in_meters=baseline_total_distance_in_meters,
                after_total_time_in_seconds=baseline_with_delay_total_time_in_seconds,
                courier_id=courier_id,
                is_baseline=is_baseline,
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
                    "reason": (
                        "baseline_route_monitoring_only" if is_baseline
                        else "delay_below_resequence_threshold" if force_duration_update_only
                        else "no_remaining_nodes_to_resequence"
                    ),
                    "baseline_total_time_in_seconds": baseline_total_time_in_seconds,
                    "baseline_with_delay_total_time_in_seconds": baseline_with_delay_total_time_in_seconds,
                    "reoptimized_total_time_in_seconds": baseline_with_delay_total_time_in_seconds,
                    "delay_seconds": delay_seconds,
                    "selected_algorithm": "none",
                    "time_improved": False,
                    "sequence_changed": False,
                    "would_resequence": False,
                }
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
                algorithm_used=final_optimization_run.algorithm,
                outcome=ReoptimizationOutcomeEnum.duration_updated,
                before_total_distance_in_meters=baseline_total_distance_in_meters,
                before_total_time_in_seconds=baseline_total_time_in_seconds,
                after_total_distance_in_meters=baseline_total_distance_in_meters,
                after_total_time_in_seconds=baseline_with_delay_total_time_in_seconds,
                before_computation_time_in_ms=0.0,
                optimization_run_id=final_optimization_run.id,
                is_baseline=is_baseline,
            )

        reoptimization_departure_time = current_route_leg.arrival_time + timedelta(seconds=delay_seconds)

        selected_node_indices = [
            origin_node.matrix_index,
            destination_node.matrix_index,
            *remaining_node_indices,
            0,
        ]
        
        selected_nodes: list[Node] = []
        for matrix_idx in selected_node_indices:
            node = node_by_matrix_index.get(matrix_idx)
            if node is None:
                raise ValueError(f"Node dengan matrix index {matrix_idx} tidak ditemukan.")
            selected_nodes.append(node)

        logger.info(f"Generating live submatrix from TomTom for {len(selected_nodes)} nodes...")
        submatrix = await self.matrix_service.generate_live_submatrix_for_reoptimization(
            nodes=selected_nodes,
            departure_time=reoptimization_departure_time
        )
        
        logger.info(
            {
                "event_type": "live_submatrix_built_for_reoptimization",
                "submatrix": json.dumps(submatrix),
            }
        )
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

        # The courier departs the current node only after the delayed arrival,
        # so TomTom must plan traffic-aware routes from that shifted moment.
        reoptimization_departure_time = current_route_leg.arrival_time + timedelta(seconds=delay_seconds)

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
            current_departure_time=reoptimization_departure_time,
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
            current_departure_time=reoptimization_departure_time,
        )

        candidate_plans = [
            self._build_candidate_plan(
                snapshot_total_distance_in_meters=baseline_total_distance_in_meters,
                snapshot_total_time_in_seconds=baseline_total_time_in_seconds,
                delay_seconds=delay_seconds,
                old_future_distance_in_meters=old_future_distance_in_meters,
                old_future_time_in_seconds=old_future_time_in_seconds,
                candidate=greedy_candidate,
            ),
            self._build_candidate_plan(
                snapshot_total_distance_in_meters=baseline_total_distance_in_meters,
                snapshot_total_time_in_seconds=baseline_total_time_in_seconds,
                delay_seconds=delay_seconds,
                old_future_distance_in_meters=old_future_distance_in_meters,
                old_future_time_in_seconds=old_future_time_in_seconds,
                candidate=tabu_candidate,
            ),
        ]

        # Persist both candidate runs for post-hoc algorithm comparison analytics.
        self._store_reoptimization_comparison_runs(
            simulation_id=simulation_id,
            courier_id=courier_id,
            congestion_check_id=congestion_check_id,
            before_total_distance_in_meters=baseline_total_distance_in_meters,
            before_total_time_in_seconds=baseline_total_time_in_seconds,
            greedy_candidate=greedy_candidate,
            tabu_candidate=tabu_candidate,
        )
        final_candidate = candidate_plans[1]

        time_improved = int(final_candidate["estimated_total_time_in_seconds"]) < baseline_with_delay_total_time_in_seconds
        original_comparison_sequence = [origin_node.matrix_index, destination_node.matrix_index, *remaining_node_indices]
        sequence_changed = self._is_sequence_changed(
            original_node_indices=original_comparison_sequence,
            candidate_route=list(final_candidate["route"]),
            depot_matrix_index=0,
        )

        logger.info(
            "Sequence comparison -> original=%s candidate=%s changed=%s",
            original_comparison_sequence,
            [n for n in final_candidate["route"] if n != 0],
            sequence_changed,
        )

        route_resequenced = (
            sequence_changed
            if self.settings.ENVIRONMENT == "development"
            else (time_improved and sequence_changed)
        )

        logger.info(
            "Resequence decision -> env=%s should_resequence=%s "
            "(time_improved=%s sequence_changed=%s)",
            self.settings.ENVIRONMENT,
            route_resequenced,
            time_improved,
            sequence_changed,
        )
        logger.info(f"Environment: {self.settings.ENVIRONMENT}")
        logger.info(f"Should resequence: {route_resequenced} (time improved: {time_improved}, sequence changed: {sequence_changed})")

        final_new_courier_route_id: int | None = None

        if route_resequenced:
            is_initial_route = snapshot["route_version"] == 1
            await self.route_repository.update_route_legs_after_sequence(courier_route_id, current_sequence, is_initial_route=is_initial_route)

            self.route_repository.transition_current_route_leg_for_reoptimization(current_route_leg.id, is_initial_route=is_initial_route)

            logger.info({
                "event_type": "DEBUG_ARRAY_SLICING",
                "current_sequence": current_sequence,
                "slice_index_calculated": current_sequence - 1,
                "route_node_indices_before_slice": route_node_indices,
                "solver_candidate_route": list(final_candidate["route"])
            })

            visited_node_indices = route_node_indices[:destination_route_index - 1]

            full_route_nodes = visited_node_indices + list(final_candidate["route"])

            logger.info(
                {
                    "event_type": "full_route_nodes_reconstructed",
                    "simulation_id": simulation_id,
                    "courier_route_id": courier_route_id,
                    "visited_node_indices": visited_node_indices,
                    "candidate_route": list(final_candidate["route"]),
                    "full_route_nodes": full_route_nodes,
                }
            )

            newest_solution = await self.solution_repository.insert_solution(
                solution_data=CreateSolution(
                    simulation_id=simulation_id,
                    courier_id=courier_id,
                    demand_in_kilograms=sum(demands) / 1000,
                    routes=full_route_nodes,
                    time_in_seconds=int(final_candidate["estimated_total_time_in_seconds"]),
                )
            )

            await self.courier_route_repository.deactivate_courier_route(courier_route_id)

            newest_courier_route = await self.courier_route_repository.insert_courier_route(
                courier_route=CreateCourierRoute(
                    solution_id=newest_solution.id,
                    courier_id=courier_id,
                    is_active=True,
                    is_initial_route=False,
                    reoptimized_from_route_id=courier_route_id,
                    route_version=snapshot["route_version"] + 1,
                    total_distance_in_meters=int(final_candidate["estimated_total_distance_in_meters"]),
                    total_time_in_seconds=int(final_candidate["estimated_total_time_in_seconds"]),
                    trigger_node_id=destination_node.id,
                    triggered_by_traffic=True
                )
            )

            duplicate_running_leg = CreateRouteLeg(
                courier_route_id=newest_courier_route.id,
                from_node_id=current_route_leg.from_node_id,
                to_node_id=current_route_leg.to_node_id,
                origin_latitude=float(current_route_leg.origin_latitude),
                origin_longitude=float(current_route_leg.origin_longitude),
                destination_latitude=float(current_route_leg.destination_latitude),
                destination_longitude=float(current_route_leg.destination_longitude),
                sequence=current_sequence,
                encoded_polyline=current_route_leg.encoded_polyline,
                encoded_polyline_precision=current_route_leg.encoded_polyline_precision,
                distance_in_meters=current_route_leg.distance_in_meters,
                travel_time_in_seconds=current_route_leg.travel_time_in_seconds,
                traffic_delay_in_seconds=current_route_leg.traffic_delay_in_seconds,
                departure_time=current_route_leg.departure_time,
                arrival_time=current_route_leg.arrival_time,
                no_traffic_travel_time_in_seconds=current_route_leg.no_traffic_travel_time_in_seconds,
                historic_traffic_travel_time_in_seconds=current_route_leg.historic_traffic_travel_time_in_seconds,
                live_traffic_incidents_travel_time_in_seconds=current_route_leg.live_traffic_incidents_travel_time_in_seconds,
                route_status=RouteStatusEnum.running,
                traffic_distance_in_meters=current_route_leg.traffic_distance_in_meters,
            )

            reoptimized_route_legs = self._build_reoptimized_route_legs(
                courier_route_id=newest_courier_route.id,
                current_sequence=current_sequence,
                route_nodes=list(final_candidate["route"]),
                route_response=final_candidate["route_response"],
                node_by_matrix_index=node_by_matrix_index,
            )

            if reoptimized_route_legs:
                self.route_repository.bulk_insert_route_legs([duplicate_running_leg] + reoptimized_route_legs)

            final_after_total_distance_in_meters = int(final_candidate["estimated_total_distance_in_meters"])
            final_after_total_time_in_seconds = int(final_candidate["estimated_total_time_in_seconds"])
            final_outcome = ReoptimizationOutcomeEnum.resequence_applied
            final_decision = "resequence_applied"
            final_new_courier_route_id = newest_courier_route.id
        elif time_improved and not sequence_changed:
            self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)
            final_after_total_distance_in_meters = baseline_total_distance_in_meters
            final_after_total_time_in_seconds = int(final_candidate["estimated_total_time_in_seconds"])
            final_outcome = ReoptimizationOutcomeEnum.duration_updated
            final_decision = "duration_updated_same_sequence"
        else:
            self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)
            final_after_total_distance_in_meters = baseline_total_distance_in_meters
            final_after_total_time_in_seconds = baseline_with_delay_total_time_in_seconds
            final_outcome = ReoptimizationOutcomeEnum.no_improvement
            final_decision = "duration_updated"

        final_optimization_run = self._store_final_reoptimization_run(
            simulation_id=simulation_id,
            congestion_check_id=congestion_check_id,
            before_total_distance_in_meters=baseline_total_distance_in_meters,
            before_total_time_in_seconds=baseline_total_time_in_seconds,
            greedy_candidate=candidate_plans[0],
            tabu_candidate=candidate_plans[1],
            selected_algorithm=final_candidate["algorithm"],
            courier_id=courier_id,
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
                "reoptimization_departure_time": reoptimization_departure_time.isoformat(),
                "old_future_distance_in_meters": old_future_distance_in_meters,
                "old_future_time_in_seconds": old_future_time_in_seconds,
                "baseline_total_time_in_seconds": baseline_total_time_in_seconds,
                "baseline_with_delay_total_time_in_seconds": baseline_with_delay_total_time_in_seconds,
                "greedy_candidate": {
                    "algorithm": greedy_candidate["algorithm"],
                    "distance_in_meters": int(greedy_candidate["summary"]["lengthInMeters"]),
                    "travel_time_in_seconds": int(greedy_candidate["summary"]["travelTimeInSeconds"]),
                    "estimated_total_distance_in_meters": int(candidate_plans[0]["estimated_total_distance_in_meters"]),
                    "estimated_total_time_in_seconds": int(candidate_plans[0]["estimated_total_time_in_seconds"]),
                    "computation_time_in_ms": round(float(greedy_candidate["computation_time_in_ms"]), 3),
                    "nodes_explored": int(greedy_candidate["nodes_explored"]),
                },
                "tabu_candidate": {
                    "algorithm": tabu_candidate["algorithm"],
                    "distance_in_meters": int(tabu_candidate["summary"]["lengthInMeters"]),
                    "travel_time_in_seconds": int(tabu_candidate["summary"]["travelTimeInSeconds"]),
                    "estimated_total_distance_in_meters": int(candidate_plans[1]["estimated_total_distance_in_meters"]),
                    "estimated_total_time_in_seconds": int(candidate_plans[1]["estimated_total_time_in_seconds"]),
                    "computation_time_in_ms": round(float(tabu_candidate["computation_time_in_ms"]), 3),
                    "nodes_explored": int(tabu_candidate["nodes_explored"]),
                },
                "selected_algorithm": final_candidate["algorithm"],
                "selected_distance_in_meters": final_after_total_distance_in_meters,
                "selected_travel_time_in_seconds": final_after_total_time_in_seconds,
                "reoptimized_total_time_in_seconds": final_after_total_time_in_seconds,
                "baseline_total_time_in_seconds": baseline_total_time_in_seconds,
                "time_improved": time_improved,
                "sequence_changed": sequence_changed,
                "route_resequenced": route_resequenced,
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
                "decision": final_decision,
                "reason": (
                    "candidate_improves_total_time_and_sequence_changed"
                    if route_resequenced
                    else "candidate_improves_time_but_sequence_unchanged"
                    if (time_improved and not sequence_changed)
                    else "candidate_not_better_than_existing_route"
                ),
                "baseline_total_time_in_seconds": baseline_total_time_in_seconds,
                "baseline_with_delay_total_time_in_seconds": baseline_with_delay_total_time_in_seconds,
                "reoptimized_total_time_in_seconds": final_after_total_time_in_seconds,
                "delay_seconds": delay_seconds,
                "selected_algorithm": final_candidate["algorithm"],
                "time_improved": time_improved,
                "sequence_changed": sequence_changed,
                "would_resequence": route_resequenced,
            }
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
            optimization_run_id=final_optimization_run.id,
            algorithm_used=final_candidate["algorithm"],  # type: ignore
            outcome=final_outcome,
            before_total_distance_in_meters=baseline_total_distance_in_meters,
            before_total_time_in_seconds=baseline_total_time_in_seconds,
            after_total_distance_in_meters=final_after_total_distance_in_meters,
            after_total_time_in_seconds=final_after_total_time_in_seconds,
            before_computation_time_in_ms=float(final_candidate["computation_time_in_ms"]),
            is_baseline=is_baseline,
            after_route_id=final_new_courier_route_id,
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
        algorithm_used: Literal["greedy", "tabu_search"] | None,
        outcome: ReoptimizationOutcomeEnum,
        before_total_distance_in_meters: int,
        before_total_time_in_seconds: int,
        after_total_distance_in_meters: int,
        after_total_time_in_seconds: int,
        before_computation_time_in_ms: float,
        is_baseline: bool = False,
        after_route_id: int | None = None,
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
                after_route_id=after_route_id or courier_route_id,
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

        _sim_update_fields: dict[str, Any] = {
            "total_incidents_affecting_routes": int(getattr(simulation, "total_incidents_affecting_routes", 0) or 0) + 1,
        }
        # Baseline incidents only propagate delay — they do not alter the "after"
        # totals that belong to the active (reoptimized) route tracking.
        if not is_baseline:
            _sim_update_fields.update({
                "final_total_distance_in_meters": after_total_distance_in_meters,
                "final_total_duration_in_seconds": after_total_time_in_seconds,
                "distance_improvement_in_meters": int(getattr(simulation, "initial_total_distance_in_meters", 0) or 0) - after_total_distance_in_meters,
                "duration_improvement_in_seconds": int(getattr(simulation, "initial_total_duration_in_seconds", 0) or 0) - after_total_time_in_seconds,
                "total_reoptimized_routes": int(getattr(simulation, "total_reoptimized_routes", 0) or 0) + 1,
            })
        await self.simulation_repository.update_simulation(simulation_id, UpdateSimulationSchema(**_sim_update_fields))

        await SimulationLogRepository(self.route_repository.db).create_log(
            CreateSimulationLog(
                simulation_id=simulation_id,
                courier_route_id=courier_route_id,
                courier_id=courier_id,
                event_type=ROUTE_REOPTIMIZED,
                title=(
                    f"Route resequenced for courier route {courier_route_id}"
                    if outcome == ReoptimizationOutcomeEnum.resequence_applied
                    else f"Route duration updated for courier route {courier_route_id}"
                ),
                description=(
                    f"Route leg {route_leg_id} was delayed by {delay_seconds} seconds and the route was resequenced."
                    if outcome == ReoptimizationOutcomeEnum.resequence_applied
                    else f"Route leg {route_leg_id} was delayed by {delay_seconds} seconds and the route duration was updated without changing the node sequence."
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

    def _store_no_solver_run(
        self,
        *,
        simulation_id: str,
        courier_id: int,
        congestion_check_id: int | None,
        before_total_distance_in_meters: int,
        before_total_time_in_seconds: int,
        after_total_distance_in_meters: int,
        after_total_time_in_seconds: int,
        is_baseline: bool,
    ) -> Any:
        from uuid import UUID

        run_type_val = "baseline_tracking" if is_baseline else "duration_update"
        triggered_time = datetime.now(timezone.utc)

        created_runs = self.optimization_run_repository.bulk_insert_optimization_runs(
            [
                # Record 1: Greedy
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type=run_type_val,
                    algorithm="greedy",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=after_total_distance_in_meters,
                    total_travel_time_in_seconds=after_total_time_in_seconds,
                    computation_time_in_ms=0.0,
                    total_nodes_explored=0,
                    congestion_check_id=congestion_check_id,
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                    triggered_at=triggered_time,
                    courier_id=courier_id
                ),
                # Record 2: Tabu Search
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type=run_type_val,
                    algorithm="tabu_search",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=after_total_distance_in_meters,
                    total_travel_time_in_seconds=after_total_time_in_seconds,
                    computation_time_in_ms=0.0,
                    total_nodes_explored=0,
                    congestion_check_id=congestion_check_id,
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                    triggered_at=triggered_time,
                    courier_id=courier_id
                )
            ]
        )

        return created_runs[0]

    def _store_final_reoptimization_run(
        self,
        *,
        simulation_id: str,
        courier_id: int,
        congestion_check_id: int | None,
        before_total_distance_in_meters: int,
        before_total_time_in_seconds: int,
        greedy_candidate: dict[str, Any],
        tabu_candidate: dict[str, Any],
        selected_algorithm: Literal["greedy", "tabu_search"],
    ) -> Any:
        from uuid import UUID

        triggered_at = datetime.now(timezone.utc)

        created_runs = self.optimization_run_repository.bulk_insert_optimization_runs(
            [
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="reoptimization",
                    algorithm="greedy",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=int(greedy_candidate["estimated_total_distance_in_meters"]),
                    total_travel_time_in_seconds=int(greedy_candidate["estimated_total_time_in_seconds"]),
                    computation_time_in_ms=float(greedy_candidate["computation_time_in_ms"]),
                    total_nodes_explored=int(greedy_candidate["nodes_explored"]),
                    congestion_check_id=congestion_check_id,
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                    triggered_at=triggered_at,
                    courier_id=courier_id
                ),
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="reoptimization",
                    algorithm="tabu_search",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=int(tabu_candidate["estimated_total_distance_in_meters"]),
                    total_travel_time_in_seconds=int(tabu_candidate["estimated_total_time_in_seconds"]),
                    computation_time_in_ms=float(tabu_candidate["computation_time_in_ms"]),
                    total_nodes_explored=int(tabu_candidate["nodes_explored"]),
                    congestion_check_id=congestion_check_id,
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                    triggered_at=triggered_at,
                    courier_id=courier_id
                ),
            ]
        )

        # Return the run that corresponds to the algorithm actually applied.
        selected_index = 0 if selected_algorithm == "greedy" else 1
        return created_runs[selected_index]

    def _build_candidate_plan(
        self,
        *,
        snapshot_total_distance_in_meters: int,
        snapshot_total_time_in_seconds: int,
        delay_seconds: int,
        old_future_distance_in_meters: int,
        old_future_time_in_seconds: int,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        future_distance_in_meters = int(candidate["summary"]["lengthInMeters"])
        future_time_in_seconds = int(candidate["summary"]["travelTimeInSeconds"])

        return {
            **candidate,
            "future_distance_in_meters": future_distance_in_meters,
            "future_time_in_seconds": future_time_in_seconds,
            "estimated_total_distance_in_meters": snapshot_total_distance_in_meters - old_future_distance_in_meters + future_distance_in_meters,
            "estimated_total_time_in_seconds": snapshot_total_time_in_seconds + delay_seconds + (future_time_in_seconds - old_future_time_in_seconds),
        }

    def _build_reoptimized_route_legs(
        self,
        *,
        courier_route_id: int,
        current_sequence: int,
        route_nodes: list[int],
        route_response: dict[str, Any],
        node_by_matrix_index: dict[int, Any],
    ) -> list[CreateRouteLeg]:
        route_legs: list[CreateRouteLeg] = []
        legs = route_response["routes"][0]["legs"]

        for index, leg in enumerate(legs):
            origin_node = node_by_matrix_index.get(route_nodes[index])
            destination_node = node_by_matrix_index.get(route_nodes[index + 1])

            if origin_node is None or destination_node is None:
                raise ValueError(
                    f"Failed to rebuild reoptimized leg for matrix indices {route_nodes[index]}->{route_nodes[index + 1]}."
                )

            summary = leg["summary"]
            route_legs.append(
                CreateRouteLeg(
                    courier_route_id=courier_route_id,
                    from_node_id=origin_node.id,
                    to_node_id=destination_node.id,
                    origin_latitude=float(origin_node.latitude),
                    origin_longitude=float(origin_node.longitude),
                    destination_latitude=float(destination_node.latitude),
                    destination_longitude=float(destination_node.longitude),
                    sequence=current_sequence + index + 1,
                    encoded_polyline=leg["encodedPolyline"],
                    encoded_polyline_precision=int(leg["encodedPolylinePrecision"]),
                    distance_in_meters=int(summary["lengthInMeters"]),
                    travel_time_in_seconds=int(summary["travelTimeInSeconds"]),
                    traffic_delay_in_seconds=int(summary["trafficDelayInSeconds"]),
                    traffic_distance_in_meters=int(summary["trafficLengthInMeters"]),
                    departure_time=datetime.fromisoformat(str(summary["departureTime"]).replace("Z", "+00:00")),
                    arrival_time=datetime.fromisoformat(str(summary["arrivalTime"]).replace("Z", "+00:00")),
                    no_traffic_travel_time_in_seconds=int(summary["noTrafficTravelTimeInSeconds"]),
                    historic_traffic_travel_time_in_seconds=int(summary["historicTrafficTravelTimeInSeconds"]),
                    live_traffic_incidents_travel_time_in_seconds=int(summary["liveTrafficIncidentsTravelTimeInSeconds"]),
                    route_status=RouteStatusEnum.planned,
                )
            )

        return route_legs

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
        route_response = self.tomtom_service.generate_routes(route_points, depart_at=format_departure_time(current_departure_time))
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
        courier_id: int,
        congestion_check_id: int | None,
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
                    run_type="reoptimization_candidate",
                    algorithm="greedy",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=int(greedy_candidate["summary"]["lengthInMeters"]),
                    total_travel_time_in_seconds=int(greedy_candidate["summary"]["travelTimeInSeconds"]),
                    computation_time_in_ms=float(greedy_candidate["computation_time_in_ms"]),
                    total_nodes_explored=int(greedy_candidate["nodes_explored"]),
                    congestion_check_id=congestion_check_id,
                    triggered_at=datetime.now(timezone.utc),
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                    courier_id=courier_id
                ),
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="reoptimization_candidate",
                    algorithm="tabu_search",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=int(tabu_candidate["summary"]["lengthInMeters"]),
                    total_travel_time_in_seconds=int(tabu_candidate["summary"]["travelTimeInSeconds"]),
                    computation_time_in_ms=float(tabu_candidate["computation_time_in_ms"]),
                    total_nodes_explored=int(tabu_candidate["nodes_explored"]),
                    congestion_check_id=congestion_check_id,
                    triggered_at=datetime.now(timezone.utc),
                    before_total_distance_in_meters=before_total_distance_in_meters,
                    before_total_travel_time_in_seconds=before_total_time_in_seconds,
                    courier_id=courier_id
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

    def _build_submatrix(
        self,
        time_matrix: list[list[int]],
        node_indices: list[int],
        congested_origin_index: int | None = None,
        congested_destination_index: int | None = None,
        big_m_penalty: int = 999_999,
    ) -> list[list[int]]:
        """Extract a submatrix for the given node_indices.

        If ``congested_origin_index`` and ``congested_destination_index`` are
        provided (both are global matrix indices), the edge between them is
        replaced with ``big_m_penalty`` so the solver treats that leg as
        effectively impassable and seeks an alternative ordering (En-Route
        Diversion).  The penalty must be an integer — OR-Tools does not accept
        ``float('inf')``.
        """
        submatrix: list[list[int]] = []
        for origin_index in node_indices:
            row: list[int] = []
            for destination_index in node_indices:
                cell = time_matrix[origin_index][destination_index]
                if (
                    congested_origin_index is not None
                    and congested_destination_index is not None
                    and origin_index == congested_origin_index
                    and destination_index == congested_destination_index
                ):
                    cell = big_m_penalty
                row.append(cell)
            submatrix.append(row)
        return submatrix

    @staticmethod
    def _is_sequence_changed(
        original_node_indices: list[int],
        candidate_route: list[int],
        depot_matrix_index: int,
    ) -> bool:
        """Return True only when the solver produced a genuinely different visit order.

        The raw ``candidate_route`` from ``_parse_solver_route`` includes the
        depot at both ends (e.g. [depot, A, B, C, depot]).  We strip those
        and compare only the delivery-node portion against ``original_node_indices``.
        """
        # Strip leading / trailing depot entries
        interior = [n for n in candidate_route if n != depot_matrix_index]
        return interior != list(original_node_indices)

    def _conversion_demand_to_grams(self, demand: float) -> int:
        return round(demand * 1000)