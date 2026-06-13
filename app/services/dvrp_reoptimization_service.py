from __future__ import annotations
import math
from datetime import datetime, timezone
import json
from typing import Literal, TypedDict, cast, Sequence
from app.configs.environment_configuration import get_environment_configuration
from app.constants.simulation_log_event_types import ROUTE_REOPTIMIZED
from app.lib.logging.logging import get_logger
from app.lib.route_geometry import decode_polyline
from app.models.courier import Courier
from app.models.courier_route import CourierRoute
from app.models.simulation import Simulation
from app.models.reoptimization_event import ReoptimizationEvent, ReoptimizationOutcomeEnum
from app.models.route import RouteLeg, RouteStatusEnum
from app.models.optimization_run import OptimizationRun
from app.repositories.courier_route_repository import CourierRouteRepository
from app.repositories.daily_optimization_log_repository import DailyOptimizationLogRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.repositories.route_repository import RouteRepository
from app.repositories.simulation_log_repository import SimulationLogRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.repositories.tabu_search_configuration_repository import TabuSearchConfigurationRepository
from app.schemas.courier_route_schema import CreateCourierRoute
from app.schemas.daily_optimization_log_schema import DailyOptimizationLogCreate
from app.schemas.optimization_run_schema import CreateOptimizationRun
from app.schemas.route_schema import CreateRouteLeg
from app.schemas.simulation_log_schema import CreateSimulationLog
from app.schemas.simulation_schema import UpdateSimulationSchema
from app.schemas.solution_schema import CreateSolution
from app.services.manual_solver.solver_execution_service import SolverExecutionService
from app.services.matrix_service import MatrixService
from app.services.manual_solver.manual_solver import GreedySolver as ManualGreedySolver, TabuSearchSolver as ManualTabuSearchSolver
from app.services.manual_solver.types import ManualSolverProblem
from app.services.tomtom_service import TomTomService
from app.models.node import Node
from app.lib.date_converter import format_departure_time

logger = get_logger(__name__)

class RouteLegSummary(TypedDict):
    lengthInMeters: int | float
    travelTimeInSeconds: int | float
    trafficDelayInSeconds: int | float
    trafficLengthInMeters: int | float
    departureTime: str
    arrivalTime: str
    noTrafficTravelTimeInSeconds: int | float
    historicTrafficTravelTimeInSeconds: int | float
    liveTrafficIncidentsTravelTimeInSeconds: int | float

class TomTomRouteLeg(TypedDict):
    summary: RouteLegSummary
    encodedPolyline: str
    encodedPolylinePrecision: int

class TomTomRoute(TypedDict):
    summary: RouteLegSummary
    legs: list[TomTomRouteLeg]

class TomTomResponse(TypedDict):
    routes: list[TomTomRoute]

AlgorithmLiteral = Literal["greedy", "tabu_search"]

class CandidatePlan(TypedDict):
    algorithm: AlgorithmLiteral
    route: list[int]
    computation_time_in_ms: float
    nodes_explored: int
    future_distance_in_meters: float
    future_time_in_seconds: float
    estimated_total_distance_in_meters: float
    estimated_total_time_in_seconds: float
    route_response: TomTomResponse | None
    summary: RouteLegSummary | None

class SolverResult(TypedDict):
    algorithm: AlgorithmLiteral
    route_nodes: list[int]
    internal_time_in_seconds: float
    computation_time_in_ms: float
    nodes_explored: int

class ReoptimizationResult(TypedDict):
    simulation_id: str
    courier_route_id: int
    algorithm_used: AlgorithmLiteral | None
    outcome: str
    before_total_time_in_seconds: float
    after_total_time_in_seconds: float
    before_total_distance_in_meters: float
    after_total_distance_in_meters: float

class CourierRouteSnapshot(TypedDict):
    routes: Sequence[int]
    total_distance_in_meters: int | float
    total_time_in_seconds: int | float
    route_version: int

class CourierPositionLog(TypedDict):
    courier_id: int
    lat: float
    lng: float
    bearing: int

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
        tabu_search_configuration_repository: TabuSearchConfigurationRepository,
        daily_optimization_log_repository: DailyOptimizationLogRepository,
        solver_execution_service: SolverExecutionService
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
        self.tabu_search_configuration_repository = tabu_search_configuration_repository
        self.daily_optimization_log_repository = daily_optimization_log_repository
        self.solver_execution_service = solver_execution_service

    async def handle_congestion(
        self,
        *,
        simulation_id: str,
        route_leg_id: int,
        courier_route_id: int,
        courier_id: int,
        current_sequence: int,
        delay_seconds: int,
        resequence_improvement_threshold_percent: float,
        congestion_check_id: int | None = None,
        force_duration_update_only: bool = False,
        is_baseline: bool,
    ) -> ReoptimizationResult:
        simulation = await self.simulation_repository.get_simulation_by_id(simulation_id)
        if simulation is None:
            logger.error(f"Simulation {simulation_id} not found for congestion handling.")
            raise ValueError(f"Simulation {simulation_id} not found.")
        
        raw_snapshot = self.route_repository.get_courier_route_snapshot(courier_route_id)
        if raw_snapshot is None:
            logger.error(f"Courier route {courier_route_id} not found for congestion handling in simulation {simulation_id}.")
            raise ValueError(f"Courier route {courier_route_id} not found for simulation {simulation_id}.")
        
        snapshot = cast(CourierRouteSnapshot, raw_snapshot)

        current_route_leg = self.route_repository.get_route_leg_by_id(route_leg_id)
        if current_route_leg is None:
             logger.error(f"Route leg {route_leg_id} not found for congestion handling in simulation {simulation_id}.")
             raise ValueError(f"Route leg {route_leg_id} not found for simulation {simulation_id}.")
        original_current_leg_travel_time = int(current_route_leg.travel_time_in_seconds)

        nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        node_by_matrix_index: dict[int, Node] = {node.matrix_index: node for node in nodes}
        node_by_id: dict[int, Node] = {node.id: node for node in nodes}

        destination_node = node_by_id.get(current_route_leg.to_node_id)
        if destination_node is None:
            logger.error(f"Destination node {current_route_leg.to_node_id} not found for congestion handling in simulation {simulation_id}.")
            raise ValueError(f"Destination node {current_route_leg.to_node_id} could not be loaded.")
        
        origin_node = node_by_id.get(current_route_leg.from_node_id)
        if origin_node is None:
            logger.error(f"Origin node {current_route_leg.from_node_id} not found for congestion handling in simulation {simulation_id}.")
            raise ValueError(f"Origin node {current_route_leg.from_node_id} could not be loaded.")

        route_node_indices = list(snapshot["routes"])
        
        if destination_node.matrix_index not in route_node_indices:
            logger.error(f"Destination node with matrix index {destination_node.matrix_index} is missing from courier route {courier_route_id} for congestion handling in simulation {simulation_id}.")
            raise ValueError(
                f"Destination matrix index {destination_node.matrix_index} is missing from courier route {courier_route_id}."
            )

        origin_idx = current_sequence - 1
        
        if origin_idx >= len(route_node_indices):
            origin_idx = len(route_node_indices) - 1

        visited_node_indices = route_node_indices[:origin_idx + 1]
        
        nodes_after_origin = route_node_indices[origin_idx + 1:]
        
        remaining_node_indices = [
            n for n in nodes_after_origin 
            if n != destination_node.matrix_index and n != 0
        ]

        logger.info({
            "event_type": "DEBUG_ROUTE_SLICING",
            "courier_route_id": courier_route_id,
            "courier_id": courier_id,
            "origin_node_matrix_index": origin_node.matrix_index,
            "destination_node_matrix_index": destination_node.matrix_index,
            "original_route": route_node_indices,
            "origin_idx": origin_idx,
            "visited_node_indices": visited_node_indices,
            "raw_remaining": nodes_after_origin,
            "remaining_node_indices": remaining_node_indices,
        })

        old_future_legs = self.route_repository.get_route_legs_by_courier_route_id(courier_route_id)
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

        self.route_repository.update_route_leg_delay(route_leg_id, delay_seconds)

        should_update_duration_only = (
            force_duration_update_only
            or not remaining_node_indices
            or is_baseline
        )
        
        if should_update_duration_only:
            self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)

            current_route_leg.route_status = RouteStatusEnum.baseline_running if is_baseline else RouteStatusEnum.running

            latest_times = self.optimization_run_repository.get_latest_total_times_per_algorithm(
                simulation_id=simulation_id,
                courier_id=courier_id,
            )

            greedy_before_time = latest_times.get("greedy", baseline_total_time_in_seconds)
            tabu_before_time   = latest_times.get("tabu_search", baseline_total_time_in_seconds)

            final_optimization_run = self._store_no_solver_run(
                simulation_id=simulation_id,
                congestion_check_id=congestion_check_id,
                greedy_before_distance_in_meters=baseline_total_distance_in_meters,
                greedy_before_time_in_seconds=greedy_before_time,
                greedy_after_distance_in_meters=baseline_total_distance_in_meters,
                greedy_after_time_in_seconds=greedy_before_time + delay_seconds,
                tabu_before_distance_in_meters=baseline_total_distance_in_meters,
                tabu_before_time_in_seconds=tabu_before_time,
                tabu_after_distance_in_meters=baseline_total_distance_in_meters,
                tabu_after_time_in_seconds=tabu_before_time + delay_seconds,
                courier_id=courier_id,
                is_baseline=is_baseline,
            )
            
            return await self._finalize_reoptimization(
                simulation_id=simulation_id,
                courier_route_id=courier_route_id,
                courier_id=courier_id,
                current_route_leg=current_route_leg,
                delay_seconds=delay_seconds,
                congestion_check_id=congestion_check_id,
                route_leg_id=route_leg_id,
                algorithm_used=cast(AlgorithmLiteral, final_optimization_run.algorithm),
                outcome=ReoptimizationOutcomeEnum.duration_updated,
                before_total_distance_in_meters=baseline_total_distance_in_meters,
                before_total_time_in_seconds=baseline_total_time_in_seconds,
                after_total_distance_in_meters=baseline_total_distance_in_meters,
                after_total_time_in_seconds=baseline_with_delay_total_time_in_seconds,
                before_computation_time_in_ms=0.0,
                optimization_run_id=final_optimization_run.id,
                is_baseline=is_baseline,
            )

        reoptimization_departure_time = current_route_leg.departure_time

        selected_node_indices = [
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
        
        time_matrix, distance_matrix = await self.matrix_service.generate_live_distance_matrix_and_time_matrix(
            nodes=selected_nodes,
            departure_time=reoptimization_departure_time
        )
        
        # logger.warning("TESTING MODE ACTIVE: Memaksa Big M Penalty pada arc [0][1]")
        # if len(time_matrix) > 0 and len(time_matrix[0]) > 1 and not is_baseline:
        #     time_matrix[0][1] = time_matrix[0][1] + delay_seconds
            
        logger.info(f"Time matrix after TomTom generation: {time_matrix}")
        
        demands = [
            0,
            *[
                self._conversion_demand_to_grams(node_by_matrix_index[matrix_index].demand)
                for matrix_index in remaining_node_indices
            ],
            0,
        ]
        
        tabu_search_active_config = await self.tabu_search_configuration_repository.get_active_tabu_search_configuration()

        courier = self.route_repository.db.query(Courier).filter(Courier.id == courier_id).first()
        if courier is None:
            raise ValueError(f"Courier {courier_id} could not be loaded.")
        
        n_c = len(selected_node_indices) - 1 if simulation.is_with_adaptive_parameters else len(route_node_indices) - 1
        
        logger.info(f"Running solvers for reoptimization with {n_c} nodes in the problem...")
        
        solver_result = await self.solver_execution_service.run(
            distance_matrix=[[float(x) for x in row] for row in distance_matrix],
            time_matrix=[[float(x) for x in row] for row in time_matrix],
            start_index=0,
            end_index=len(selected_node_indices) - 1,
            n_nodes=n_c,
            tabu_config=tabu_search_active_config,
        )
        
        def process_solver_tour(tour: list[int]) -> list[int]:
            mapped_route = [selected_node_indices[local_idx] for local_idx in tour]

            clean_route: list[int] = []
            for i, node_idx in enumerate(mapped_route):
                if node_idx == 0 and i != 0:
                    continue
                clean_route.append(node_idx)

            if len(clean_route) > 1 and clean_route[-1] != 0:
                clean_route.append(0)

            clean: list[int] = []
            for n in clean_route:
                if not clean or clean[-1] != n:
                    clean.append(n)
            return clean
        
        greedy_route_nodes = process_solver_tour(solver_result.greedy_assignment.tour)
        tabu_route_nodes = process_solver_tour(solver_result.tabu_assignment.tour)
        
        greedy_result: SolverResult = {
            "algorithm": "greedy",
            "route_nodes": greedy_route_nodes,
            "internal_time_in_seconds": solver_result.greedy_assignment.total_duration_in_seconds,
            "computation_time_in_ms": solver_result.greedy_time_ms,
            "nodes_explored": len(greedy_route_nodes),
        }

        tabu_result: SolverResult = {
            "algorithm": "tabu_search",
            "route_nodes": tabu_route_nodes,
            "internal_time_in_seconds": solver_result.tabu_assignment.total_duration_in_seconds,
            "computation_time_in_ms": solver_result.tabu_time_ms,
            "nodes_explored": len(tabu_route_nodes),
        }
        
        if tabu_search_active_config:
            greedy_fitness = greedy_result["internal_time_in_seconds"]
            tabu_fitness = tabu_result["internal_time_in_seconds"]
            
            improvement_pct = 0.0
            if greedy_fitness > 0:
                improvement_pct = ((greedy_fitness - tabu_fitness) / greedy_fitness) * 100.0

            log_payload = DailyOptimizationLogCreate(
                config_id=tabu_search_active_config.id,
                date=datetime.now(timezone.utc),
                total_nodes=len(selected_node_indices) - 1,
                total_couriers=1,
                execution_time_ms=tabu_result["computation_time_in_ms"],
                total_fitness_score=tabu_fitness,
                improvement_percentage=improvement_pct
            )
            
            await self.daily_optimization_log_repository.create_daily_optimization_log(data=log_payload)
            logger.info(f"Daily optimization log created for Reoptimization with {improvement_pct:.2f}% improvement using config {tabu_search_active_config.id}")
        
        logger.info({
            "event_type": "DEBUG_SOLVER_OUTPUT",
            "courier_route_id": courier_route_id,
            "courier_id": courier_id,
            "selected_node_indices_input": selected_node_indices,
            "greedy_raw_route": greedy_result["route_nodes"],
            "tabu_raw_route": tabu_result["route_nodes"]
        })

        tabu_route_points = ":".join(self._build_route_points(tabu_result["route_nodes"], node_by_matrix_index))
        greedy_route_points = ":".join(self._build_route_points(greedy_result["route_nodes"], node_by_matrix_index))
        
        logger.warning({
            "greedy_route_nodes": greedy_result["route_nodes"],
            "greedy_route_points": greedy_route_points,

            "tabu_route_nodes": tabu_result["route_nodes"],
            "tabu_route_points": tabu_route_points,
        })
        
        tabu_route_response = cast(TomTomResponse, self.tomtom_service.generate_routes(
            tabu_route_points, depart_at=format_departure_time(reoptimization_departure_time)
        ))
        tabu_summary = tabu_route_response["routes"][0]["summary"]
        
        greedy_route_response = cast(TomTomResponse, self.tomtom_service.generate_routes(
            greedy_route_points, depart_at=format_departure_time(reoptimization_departure_time)
        ))
        greedy_summary = greedy_route_response["routes"][0]["summary"]
        
        past_distance = sum(
            leg.distance_in_meters for leg in old_future_legs if leg.sequence < current_sequence
        )
        past_time = sum(
            leg.travel_time_in_seconds for leg in old_future_legs if leg.sequence < current_sequence
        )
        
        historical_distance_in_meters = past_distance + int(current_route_leg.distance_in_meters)
        historical_time_in_seconds = past_time + original_current_leg_travel_time + delay_seconds
        
        logger.info({
            "event_type": "DEBUG_HISTORICAL_TIME_CHECK",
            "current_leg_travel_time_before_calc": current_route_leg.travel_time_in_seconds,
            "delay_seconds": delay_seconds,
            "past_time": past_time,
        })
        
        baseline_future_time = sum(
            leg.travel_time_in_seconds for leg in old_future_legs if leg.sequence > current_sequence
        )
        fair_baseline_total_time_in_seconds = historical_time_in_seconds + baseline_future_time
        
        greedy_plan: CandidatePlan = {
            "algorithm": "greedy",
            "route": greedy_result["route_nodes"],
            "computation_time_in_ms": greedy_result["computation_time_in_ms"],
            "nodes_explored": greedy_result["nodes_explored"],
            "future_distance_in_meters": int(greedy_summary["lengthInMeters"]),
            "future_time_in_seconds": int(greedy_summary["travelTimeInSeconds"]),
            "estimated_total_distance_in_meters": historical_distance_in_meters + int(greedy_summary["lengthInMeters"]),
            "estimated_total_time_in_seconds": historical_time_in_seconds + int(greedy_summary["travelTimeInSeconds"]),
            "route_response": greedy_route_response,
            "summary": greedy_summary,
        }

        tabu_plan: CandidatePlan = {
            "algorithm": "tabu_search",
            "route": tabu_result["route_nodes"],
            "computation_time_in_ms": tabu_result["computation_time_in_ms"],
            "nodes_explored": tabu_result["nodes_explored"],
            "future_distance_in_meters": int(tabu_summary["lengthInMeters"]),
            "future_time_in_seconds": int(tabu_summary["travelTimeInSeconds"]),
            "estimated_total_distance_in_meters": historical_distance_in_meters + int(tabu_summary["lengthInMeters"]),
            "estimated_total_time_in_seconds": historical_time_in_seconds + int(tabu_summary["travelTimeInSeconds"]),
            "route_response": tabu_route_response,
            "summary": tabu_summary,
        }

        self._store_reoptimization_comparison_runs(
            simulation_id=simulation_id,
            courier_id=courier_id,
            congestion_check_id=congestion_check_id,
            before_total_distance_in_meters=baseline_total_distance_in_meters,
            before_total_time_in_seconds=baseline_total_time_in_seconds,
            greedy_candidate=greedy_plan,
            tabu_candidate=tabu_plan,
        )
        
        final_candidate = tabu_plan

        candidate_time = int(final_candidate["estimated_total_time_in_seconds"])
        time_improved = candidate_time < fair_baseline_total_time_in_seconds
        
        improvement_percentage = 0.0
        
        if time_improved and fair_baseline_total_time_in_seconds > 0:
            improvement_percentage = ((fair_baseline_total_time_in_seconds - candidate_time) / fair_baseline_total_time_in_seconds) * 100.0        

        original_comparison_sequence = [destination_node.matrix_index, *remaining_node_indices]
        sequence_changed = self._is_sequence_changed(
            original_node_indices=original_comparison_sequence,
            candidate_route=list(final_candidate["route"]),
            depot_matrix_index=0,
        )
        
        is_above_threshold = improvement_percentage >= resequence_improvement_threshold_percent

        # Just for testing, we want to see resequencing happen more often in dev environment
        # route_resequenced = (
        #      sequence_changed
        #      if self.settings.ENVIRONMENT == "development"
        #      else (time_improved and sequence_changed and is_above_threshold) 
        #  )
        
        route_resequenced = time_improved and sequence_changed and is_above_threshold
        
        logger.info({
            "event_type": "DEBUG_RESEQUENCE_EVALUATION",
            "courier_route_id": courier_route_id,
            "courier_id": courier_id,
            "fair_baseline_total_time_in_seconds": fair_baseline_total_time_in_seconds,
            "candidate_estimated_total_time_in_seconds": candidate_time,
            "improvement_percentage": round(improvement_percentage, 4),
            "threshold_percentage": resequence_improvement_threshold_percent,
            "time_improved": time_improved,
            "sequence_changed": sequence_changed,
            "is_above_threshold": is_above_threshold,
            "decision_route_resequenced": route_resequenced,
            "tabu_tomtom_summary": final_candidate["summary"],
            "greedy_tomtom_summary": greedy_plan["summary"],
            "tabu_estimated_total_distance_in_meters": historical_distance_in_meters + int(tabu_summary["lengthInMeters"]),
            "tabu_estimated_total_time_in_seconds": historical_time_in_seconds + int(tabu_summary["travelTimeInSeconds"]),
            "greedy_estimated_total_distance_in_meters": historical_distance_in_meters + int(greedy_summary["lengthInMeters"]),
            "greedy_estimated_total_time_in_seconds": historical_time_in_seconds + int(greedy_summary["travelTimeInSeconds"]),
            "historical_distance_in_meters": historical_distance_in_meters,
            "historical_time_in_seconds": historical_time_in_seconds,
        })

        final_new_courier_route_id: int | None = None

        if route_resequenced:
            is_initial_route = snapshot["route_version"] == 1
            await self.route_repository.update_route_legs_after_sequence(courier_route_id, current_sequence, is_initial_route=is_initial_route)
            self.route_repository.transition_current_route_leg_for_reoptimization(current_route_leg.id, is_initial_route=is_initial_route)

            candidate_route = list(final_candidate["route"])
            
            raw_full_route = visited_node_indices + candidate_route
            
            full_route_nodes: list[int] = []
            for n in raw_full_route:
                if not full_route_nodes or full_route_nodes[-1] != n:
                    full_route_nodes.append(n)
                    
            if not full_route_nodes or full_route_nodes[0] != 0:
                full_route_nodes.insert(0, 0)
                if full_route_nodes[-1] != 0:
                    full_route_nodes.append(0)
            
            logger.info({
                "event_type": "DEBUG_ROUTE_STITCHING",
                "courier_route_id": courier_route_id,
                "courier_id": courier_id,
                "visited_node_indices": visited_node_indices,
                "candidate_route_from_solver": candidate_route,
                "raw_full_route": visited_node_indices + candidate_route,
                "final_sanitized_route": full_route_nodes
            })

            newest_solution = await self.solution_repository.insert_solution(
                solution=CreateSolution(
                    simulation_id=simulation_id,
                    courier_id=courier_id,
                    demand_in_kilograms=sum(demands) / 1000,
                    routes=full_route_nodes,
                    time_in_seconds=int(final_candidate["estimated_total_time_in_seconds"]),
                    distance_in_meters=int(final_candidate["estimated_total_distance_in_meters"]),
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

            route_resp_val = cast(TomTomResponse, final_candidate["route_response"])
            
            reoptimized_route_legs = self._build_reoptimized_route_legs(
                courier_route_id=newest_courier_route.id,
                current_sequence=current_sequence,
                route_nodes=list(final_candidate["route"]),
                route_response=route_resp_val,
                node_by_matrix_index=node_by_matrix_index,
            )

            if reoptimized_route_legs:
                self.route_repository.bulk_insert_route_legs([duplicate_running_leg] + reoptimized_route_legs)

            final_after_total_distance_in_meters = int(final_candidate["estimated_total_distance_in_meters"])
            final_after_total_time_in_seconds = int(final_candidate["estimated_total_time_in_seconds"])
            final_outcome = ReoptimizationOutcomeEnum.resequence_applied
            final_new_courier_route_id = newest_courier_route.id
        elif sequence_changed and time_improved and not is_above_threshold:
            self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)
            current_route_leg.route_status = RouteStatusEnum.baseline_running if is_baseline else RouteStatusEnum.running
            final_after_total_distance_in_meters = baseline_total_distance_in_meters
            final_after_total_time_in_seconds = baseline_with_delay_total_time_in_seconds
            final_outcome = ReoptimizationOutcomeEnum.improvement_below_threshold
        elif time_improved and not sequence_changed:
            self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)
            current_route_leg.route_status = RouteStatusEnum.baseline_running if is_baseline else RouteStatusEnum.running
            final_after_total_distance_in_meters = baseline_total_distance_in_meters
            final_after_total_time_in_seconds = int(final_candidate["estimated_total_time_in_seconds"])
            final_outcome = ReoptimizationOutcomeEnum.duration_updated
        else:
            self.route_repository.shift_route_legs_after_sequence(courier_route_id, current_sequence + 1, delay_seconds)
            current_route_leg.route_status = RouteStatusEnum.baseline_running if is_baseline else RouteStatusEnum.running
            final_after_total_distance_in_meters = baseline_total_distance_in_meters
            final_after_total_time_in_seconds = baseline_with_delay_total_time_in_seconds
            final_outcome = ReoptimizationOutcomeEnum.no_improvement

        final_optimization_run = self._store_final_reoptimization_run(
            simulation_id=simulation_id,
            congestion_check_id=congestion_check_id,
            before_total_distance_in_meters=baseline_total_distance_in_meters,
            before_total_time_in_seconds=baseline_total_time_in_seconds,
            greedy_candidate=greedy_plan,
            tabu_candidate=tabu_plan,
            selected_algorithm=final_candidate["algorithm"],
            courier_id=courier_id,
            final_outcome=final_outcome,
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
                "greedy_candidate": {
                    "algorithm": greedy_plan["algorithm"],
                    "distance_in_meters": greedy_plan["future_distance_in_meters"],
                    "travel_time_in_seconds": greedy_plan["future_time_in_seconds"],
                    "estimated_total_distance_in_meters": greedy_plan["estimated_total_distance_in_meters"],
                    "estimated_total_time_in_seconds": greedy_plan["estimated_total_time_in_seconds"],
                    "computation_time_in_ms": round(float(greedy_plan["computation_time_in_ms"]), 3),
                    "nodes_explored": greedy_plan["nodes_explored"],
                },
                "tabu_candidate": {
                    "algorithm": tabu_plan["algorithm"],
                    "distance_in_meters": tabu_plan["future_distance_in_meters"],
                    "travel_time_in_seconds": tabu_plan["future_time_in_seconds"],
                    "estimated_total_distance_in_meters": tabu_plan["estimated_total_distance_in_meters"],
                    "estimated_total_time_in_seconds": tabu_plan["estimated_total_time_in_seconds"],
                    "computation_time_in_ms": round(float(tabu_plan["computation_time_in_ms"]), 3),
                    "nodes_explored": tabu_plan["nodes_explored"],
                },
                "selected_algorithm": final_candidate["algorithm"],
                "selected_distance_in_meters": final_after_total_distance_in_meters,
                "selected_travel_time_in_seconds": final_after_total_time_in_seconds,
                "reoptimized_total_time_in_seconds": final_after_total_time_in_seconds,
                "baseline_total_time_in_seconds": baseline_total_time_in_seconds,
                "time_improved": time_improved,
                "sequence_changed": sequence_changed,
                "route_resequenced": route_resequenced,
                "improvement_percentage": round(improvement_percentage, 2),
                "is_above_threshold": is_above_threshold,
                "route_resequenced": route_resequenced,
                "resequence_improvement_threshold_percent": resequence_improvement_threshold_percent,
            }
        )

        return await self._finalize_reoptimization(
            simulation_id=simulation_id,
            courier_route_id=courier_route_id,
            courier_id=courier_id,
            current_route_leg=current_route_leg,
            delay_seconds=delay_seconds,
            congestion_check_id=congestion_check_id,
            route_leg_id=route_leg_id,
            optimization_run_id=final_optimization_run.id,
            algorithm_used=final_candidate["algorithm"],
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
        delay_seconds: int,
        congestion_check_id: int | None,
        route_leg_id: int,
        optimization_run_id: int,
        algorithm_used: AlgorithmLiteral | None,
        outcome: ReoptimizationOutcomeEnum,
        before_total_distance_in_meters: int,
        before_total_time_in_seconds: int,
        after_total_distance_in_meters: int,
        after_total_time_in_seconds: int,
        before_computation_time_in_ms: float,
        is_baseline: bool = False,
        after_route_id: int | None = None,
    ) -> ReoptimizationResult:
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
                reopt_sequence=int(cast(int, getattr(simulation, "total_reoptimized_routes", 0) or 0)) + 1,
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

        new_incidents_count = int(cast(int, getattr(simulation, "total_incidents_affecting_routes", 0) or 0)) + 1

        if not is_baseline:
            initial_total_distance = int(cast(int, getattr(simulation, "initial_total_distance_in_meters", 0) or 0))
            initial_total_duration = int(cast(int, getattr(simulation, "initial_total_duration_in_seconds", 0) or 0))
            distance_delta = after_total_distance_in_meters - before_total_distance_in_meters
            duration_delta = after_total_time_in_seconds - before_total_time_in_seconds
            final_total_distance = initial_total_distance + distance_delta
            final_total_duration = initial_total_duration + duration_delta
    
            schema_payload = UpdateSimulationSchema(
                total_incidents_affecting_routes=new_incidents_count,
                final_total_distance_in_meters=final_total_distance,
                final_total_duration_in_seconds=final_total_duration,
                distance_improvement_in_meters=initial_total_distance - final_total_distance,
                duration_improvement_in_seconds=initial_total_duration - final_total_duration,
                total_reoptimized_routes=int(cast(int, getattr(simulation, "total_reoptimized_routes", 0) or 0)) + 1,
            )
        else:
            schema_payload = UpdateSimulationSchema(
                total_incidents_affecting_routes=new_incidents_count,
            )
            
        await self.simulation_repository.update_simulation(simulation_id, schema_payload)

        metadata_dict: dict[str, str | int | float | None] = {
            "outcome": outcome.value,
            "optimization_run_id": optimization_run_id,
            "congestion_check_id": congestion_check_id,
            "trigger_route_leg_id": route_leg_id,
            "delay_seconds": delay_seconds,
            "before_total_time_in_seconds": before_total_time_in_seconds,
            "after_total_time_in_seconds": after_total_time_in_seconds,
            "algorithm_used": algorithm_used,
        }

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
                metadata=json.dumps(metadata_dict),
            )
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
        greedy_before_distance_in_meters: int,
        greedy_before_time_in_seconds: int,
        greedy_after_distance_in_meters: int,
        greedy_after_time_in_seconds: int,
        tabu_before_distance_in_meters: int,
        tabu_before_time_in_seconds: int,
        tabu_after_distance_in_meters: int,
        tabu_after_time_in_seconds: int,
        is_baseline: bool,
    ) -> OptimizationRun:
        from uuid import UUID

        run_type_val = "baseline_tracking" if is_baseline else "duration_update"
        triggered_time = datetime.now(timezone.utc)

        created_runs = self.optimization_run_repository.bulk_insert_optimization_runs(
            [
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type=run_type_val,
                    algorithm="greedy",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=greedy_after_distance_in_meters,
                    total_travel_time_in_seconds=greedy_after_time_in_seconds,
                    computation_time_in_ms=0.0,
                    total_nodes_explored=0,
                    congestion_check_id=congestion_check_id,
                    before_total_distance_in_meters=greedy_before_distance_in_meters,
                    before_total_travel_time_in_seconds=greedy_before_time_in_seconds,
                    triggered_at=triggered_time,
                    courier_id=courier_id
                ),
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type=run_type_val,
                    algorithm="tabu_search",
                    trigger_type="traffic_incident",
                    total_distance_in_meters=tabu_after_distance_in_meters,
                    total_travel_time_in_seconds=tabu_after_time_in_seconds,
                    computation_time_in_ms=0.0,
                    total_nodes_explored=0,
                    congestion_check_id=congestion_check_id,
                    before_total_distance_in_meters=tabu_before_distance_in_meters,
                    before_total_travel_time_in_seconds=tabu_before_time_in_seconds,
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
        greedy_candidate: CandidatePlan,
        tabu_candidate: CandidatePlan,
        selected_algorithm: AlgorithmLiteral,
        final_outcome: ReoptimizationOutcomeEnum,
    ) -> OptimizationRun:
        from uuid import UUID

        triggered_at = datetime.now(timezone.utc)

        created_runs = self.optimization_run_repository.bulk_insert_optimization_runs(
            [
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="duration_update" if final_outcome != ReoptimizationOutcomeEnum.resequence_applied else "reoptimization",
                    algorithm=greedy_candidate["algorithm"],
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
                    run_type="duration_update" if final_outcome != ReoptimizationOutcomeEnum.resequence_applied else "reoptimization",
                    algorithm=tabu_candidate["algorithm"],
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

        selected_index = 0 if selected_algorithm in ["greedy", "tabu_search"] else 1
        return created_runs[selected_index]

    def _build_reoptimized_route_legs(
        self,
        *,
        courier_route_id: int,
        current_sequence: int,
        route_nodes: list[int],
        route_response: TomTomResponse,
        node_by_matrix_index: dict[int, Node],
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

        log_payload: list[CourierPositionLog] = [
            {
                "courier_id": courier_id,
                "lat": round(latitude, 6),
                "lng": round(longitude, 6),
                "bearing": bearing,
            }
        ]

        return json.dumps(log_payload)

    def _run_manual_solver_only(
        self,
        algorithm: AlgorithmLiteral,
        solver: ManualGreedySolver | ManualTabuSearchSolver,
        problem: ManualSolverProblem,
        selected_node_indices: list[int],
    ) -> SolverResult:
        started_at = datetime.now(timezone.utc)
        _, assignment = solver.solve(problem)
        computation_time_in_ms = max((datetime.now(timezone.utc) - started_at).total_seconds() * 1000, 0.0)

        if assignment is None:
            raise RuntimeError(f"No {algorithm} solution could be found for reoptimization.")

        route_nodes = [selected_node_indices[local_idx] for local_idx in assignment.tour]

        if len(route_nodes) > 1 and route_nodes[-1] != 0:
            route_nodes.append(0)

        return {
            "algorithm": algorithm,
            "route_nodes": route_nodes,
            "internal_time_in_seconds": assignment.total_duration_in_seconds,
            "computation_time_in_ms": computation_time_in_ms,
            "nodes_explored": len(route_nodes),
        }

    def _store_reoptimization_comparison_runs(
        self,
        *,
        simulation_id: str,
        courier_id: int,
        congestion_check_id: int | None,
        before_total_distance_in_meters: int,
        before_total_time_in_seconds: int,
        greedy_candidate: CandidatePlan,
        tabu_candidate: CandidatePlan,
    ) -> list[OptimizationRun]:
        from uuid import UUID

        created_runs = self.optimization_run_repository.bulk_insert_optimization_runs(
            [
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="reoptimization_candidate",
                    algorithm=greedy_candidate["algorithm"],
                    trigger_type="traffic_incident",
                    total_distance_in_meters=int(greedy_candidate["future_distance_in_meters"]),
                    total_travel_time_in_seconds=int(greedy_candidate["future_time_in_seconds"]),
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
                    algorithm=tabu_candidate["algorithm"],
                    trigger_type="traffic_incident",
                    total_distance_in_meters=int(tabu_candidate["future_distance_in_meters"]),
                    total_travel_time_in_seconds=int(tabu_candidate["future_time_in_seconds"]),
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
        return created_runs

    def _parse_solver_route_with_time(
        self,
        manager: object,
        routing: object,
        solution: object,
        selected_node_indices: list[int],
    ) -> tuple[list[int], int]:
        _manager = cast(dict[str, object], manager)
        
        index = routing.Start(0) # type: ignore
        route_nodes: list[int] = []
        route_time = 0

        while not routing.IsEnd(index): # type: ignore
            node_index = manager.IndexToNode(index) # type: ignore
            route_nodes.append(int(selected_node_indices[int(node_index)]))  # type: ignore
            previous_index = index  # type: ignore
            index = solution.Value(routing.NextVar(index)) # type: ignore
            route_time += routing.GetArcCostForVehicle(previous_index, index, 0) # type: ignore

        node_index = manager.IndexToNode(index) # type: ignore
        route_nodes.append(int(selected_node_indices[int(node_index)])) # type: ignore
        return route_nodes, route_time # type: ignore

    def _build_route_points(
        self,
        route_nodes: list[int],
        node_by_matrix_index: dict[int, Node],
    ) -> list[str]:
        route_points: list[str] = []

        for node_index in route_nodes:
            node = node_by_matrix_index.get(node_index)

            if node is not None:
                route_points.append(f"{node.latitude},{node.longitude}")

        return route_points

    def _calculate_route_distance(self, route_nodes: list[int], distance_matrix: list[list[int]]) -> int:
        total_distance = 0
        for i in range(len(route_nodes) - 1):
            origin_index = route_nodes[i]
            destination_index = route_nodes[i + 1]
            total_distance += distance_matrix[origin_index][destination_index]
        return total_distance

    @staticmethod
    def _is_sequence_changed(
        original_node_indices: list[int],
        candidate_route: list[int],
        depot_matrix_index: int,
    ) -> bool:
        interior = [n for n in candidate_route if n != depot_matrix_index]
        return interior != list(original_node_indices)

    def _conversion_demand_to_grams(self, demand: float) -> int:
        return round(demand * 1000)