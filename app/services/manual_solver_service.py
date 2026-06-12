from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.lib.logging.logging import get_logger
from app.models.courier import Courier
from app.models.node import Node
from app.repositories.node_repository import NodeRepository
from app.repositories.optimization_iteration_repository import OptimizationIterationRepository
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.repositories.courier_repository import CourierRepository
from app.schemas.optimization_iteration_schema import CreateOptimizationIterationSchema
from app.schemas.optimization_run_schema import CreateOptimizationRun
from app.schemas.simulation_schema import UpdateSimulationSchema
from app.schemas.solution_schema import CreateSolution
from app.services.matrix_service import MatrixService
from app.services.manual_solver.types import (
    Assignment,
    OptimizationEvent,
)

from app.repositories.tabu_search_configuration_repository import TabuSearchConfigurationRepository
from app.repositories.daily_optimization_log_repository import DailyOptimizationLogRepository
from app.schemas.daily_optimization_log_schema import DailyOptimizationLogCreate
from app.services.manual_solver.solver_execution_service import SolverExecutionService, TabuSearchConfig, SolverResult

logger = get_logger(__name__)

@dataclass
class ParsedAssignment:
    courier_id: int
    tour: list[int]
    total_distance_in_meters: int
    total_duration_in_seconds: int


class ManualSolverService:
    def __init__(
        self,
        matrix_service: MatrixService,
        courier_repository: CourierRepository,
        node_repository: NodeRepository,
        solution_repository: SolutionRepository,
        simulation_repository: SimulationRepository,
        optimization_iteration_repository: OptimizationIterationRepository,
        optimization_run_repository: OptimizationRunRepository,
        tabu_search_configuration_repository: TabuSearchConfigurationRepository,
        daily_optimization_log_repository: DailyOptimizationLogRepository,
        solver_execution_service: SolverExecutionService | None = None,
    ) -> None:
        self.matrix_service = matrix_service
        self.courier_repository = courier_repository
        self.node_repository = node_repository
        self.solution_repository = solution_repository
        self.simulation_repository = simulation_repository
        self.optimization_iteration_repository = optimization_iteration_repository
        self.optimization_run_repository = optimization_run_repository
        self.tabu_search_configuration_repository = tabu_search_configuration_repository
        self.daily_optimization_log_repository = daily_optimization_log_repository
        self.solver_execution_service = solver_execution_service or SolverExecutionService()

    async def solve_no_improvement(self, simulation_id: str) -> None:
        await self.solve(simulation_id)

    async def solve_with_improvement(self, simulation_id: str) -> None:
        await self.solve(simulation_id)

    async def solve(
        self,
        simulation_id: str,
    ) -> None:
        logger.info(f"=== [START] Memulai Proses Solve untuk Simulation ID: {simulation_id} ===")
        simulation = await self.simulation_repository.get_simulation_by_id(simulation_id)
        
        if not simulation:
            logger.error(f"Simulation with id {simulation_id} not found.")
            return
        
        couriers = self.courier_repository.get_all_active_couriers_by_simulation_id(simulation_id)
        all_nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)

        depot_node = next((node for node in all_nodes if node.matrix_index == 0), None)
        if not depot_node:
            raise Exception(f"Depot node is missing for simulation {simulation_id}.")
        
        logger.info(f"[INFO] Total Kurir Aktif: {len(couriers)} | Total Keseluruhan Node: {len(all_nodes)}")

        tabu_config = await self._load_tabu_config()
        logger.info(f"[CONFIG] Menggunakan Tabu Config: {tabu_config}")

        total_solutions_inserted = 0
        optimization_runs: list[CreateOptimizationRun] = []

        log_total_nodes = 0
        log_total_greedy_fitness = 0.0
        log_total_tabu_fitness = 0.0
        log_total_execution_ms = 0.0
        
        for courier in couriers:
            logger.info(f"--- Memproses Kurir ID: {courier.id} ({courier.name}) ---")
            courier_nodes = [node for node in all_nodes if getattr(node, "courier_id", None) == courier.id]

            if not courier_nodes:
                logger.info(
                    f"Courier {courier.id} - {courier.name} has no assigned nodes, skipping"
                )
                continue

            total_courier_demand = sum(
                float(node.demand)
                for node in courier_nodes
                if getattr(node, "demand", None) is not None
            )
            
            nodes_for_matrix = [depot_node] + sorted(courier_nodes, key=lambda n: n.matrix_index)
            selected_node_indices = [node.matrix_index for node in nodes_for_matrix]
            
            now = datetime.now(timezone.utc)
            
            time_matrix, distance_matrix = await self.matrix_service.generate_live_distance_matrix_and_time_matrix(
                nodes=nodes_for_matrix,
                departure_time=now
            )
            
            n_nodes = len(selected_node_indices) - 1
            logger.info(f"[Kurir {courier.id}] Memproses {n_nodes} node (termasuk depot). Global Indices: {selected_node_indices}")
            
            node_logs: list[str] = []
            for n in nodes_for_matrix:
                n_id = getattr(n, "id", "N/A")
                n_mat_idx = getattr(n, "matrix_index", "N/A")
                n_demand = getattr(n, "demand", 0)
                n_lat = getattr(n, "latitude", "N/A")
                n_lon = getattr(n, "longitude", "N/A")
                is_depot = " (DEPOT)" if n_mat_idx == 0 else ""
                
                node_logs.append(
                    f"  -> Node ID: {n_id}{is_depot} | MatrixIdx: {n_mat_idx} | "
                    f"Demand: {n_demand}kg | Pos: ({n_lat}, {n_lon})"
                )
            
            logger.info(f"[Kurir {courier.id}] Detail Mapping Node:\n" + "\n".join(node_logs))

            logger.info(
                f"Courier {courier.id} - {courier.name}: "
                f"{n_nodes} nodes"
            )

            result = await self.solver_execution_service.run(
                distance_matrix=[[float(x) for x in row] for row in distance_matrix],
                time_matrix=[[float(x) for x in row] for row in time_matrix],
                start_index=0,
                end_index=0,
                n_nodes=n_nodes,
                tabu_config=tabu_config,
            )

            log_total_nodes += n_nodes
            log_total_greedy_fitness += result.greedy_assignment.total_duration_in_seconds
            log_total_tabu_fitness += result.tabu_assignment.total_duration_in_seconds
            log_total_execution_ms += result.tabu_time_ms

            triggered_at = datetime.now(timezone.utc)

            optimization_runs.extend(
                self._build_optimization_runs(
                    simulation_id=simulation_id,
                    courier_id=courier.id,
                    result=result,
                    triggered_at=triggered_at,
                )
            )

            route = self._parse_assignment(result.tabu_assignment, selected_node_indices, courier)

            solution = await self.solution_repository.insert_solution(
                CreateSolution(
                    routes=route.tour,
                    demand_in_kilograms=total_courier_demand,
                    time_in_seconds=route.total_duration_in_seconds,
                    courier_id=route.courier_id,
                    simulation_id=simulation_id,
                    distance_in_meters=route.total_distance_in_meters,
                )
            )

            if result.tabu_assignment.logs:
                iterations = self._build_iteration_schemas(
                    logs=result.tabu_assignment.logs,
                    solution_id=solution.id,
                    simulation_id=simulation_id,
                    courier_id=solution.courier_id,
                )
                await self.optimization_iteration_repository.bulk_insert_optimization_iterations(
                    iterations
                )
                logger.info(
                    f"  [tabu_search] solution_id={solution.id} | "
                    f"inserted {len(iterations)} iteration logs"
                )

            total_solutions_inserted += 1

        if optimization_runs:
            self.optimization_run_repository.bulk_insert_optimization_runs(optimization_runs)

        await self.simulation_repository.update_simulation(
            simulation_id,
            UpdateSimulationSchema(
                total_couriers=total_solutions_inserted,
                total_active_couriers=total_solutions_inserted,
            ),
        )

        await self._write_daily_log(
            total_couriers=total_solutions_inserted,
            total_nodes=log_total_nodes,
            total_greedy_fitness=log_total_greedy_fitness,
            total_tabu_fitness=log_total_tabu_fitness,
            total_execution_ms=log_total_execution_ms,
        )

    async def _load_tabu_config(self) -> TabuSearchConfig:
        active = await self.tabu_search_configuration_repository.get_active_tabu_search_configuration()
        if not active:
            logger.warning("No active Tabu Search config found! Using paper default coefficients.")
            return TabuSearchConfig()
        
        return TabuSearchConfig(
            it_max_multiplier=active.it_max_multiplier,
            tab_tenure_divider=active.tab_tenure_divider,
            it_cons_multiplier=active.it_cons_multiplier,
            it_div_divider=active.it_div_divider,
        )

    async def _write_daily_log(
        self,
        total_couriers: int,
        total_nodes: int,
        total_greedy_fitness: float,
        total_tabu_fitness: float,
        total_execution_ms: float,
    ) -> None:
        active = await self.tabu_search_configuration_repository.get_active_tabu_search_configuration()
        if not active or total_couriers == 0:
            return

        improvement_pct = 0.0
        if total_greedy_fitness > 0:
            improvement_pct = (
                (total_greedy_fitness - total_tabu_fitness) / total_greedy_fitness
            ) * 100.0

        await self.daily_optimization_log_repository.create_daily_optimization_log(
            data=DailyOptimizationLogCreate(
                config_id=active.id,
                date=datetime.now(timezone.utc),
                total_nodes=total_nodes,
                total_couriers=total_couriers,
                execution_time_ms=total_execution_ms,
                total_fitness_score=total_tabu_fitness,
                improvement_percentage=improvement_pct,
            )
        )
        logger.info(
            f"Daily optimization log created successfully with "
            f"{improvement_pct:.2f}% improvement using config {active.id}"
        )

    @staticmethod
    def _build_optimization_runs(
        simulation_id: str,
        courier_id: int,
        result: SolverResult,
        triggered_at: datetime,
    ) -> list[CreateOptimizationRun]:
        return [
            CreateOptimizationRun(
                simulation_id=UUID(simulation_id),
                run_type="initial",
                algorithm="greedy",
                trigger_type="initial",
                total_distance_in_meters=int(result.greedy_assignment.total_distance_in_meters),
                total_travel_time_in_seconds=int(result.greedy_assignment.total_duration_in_seconds),
                computation_time_in_ms=result.greedy_time_ms,
                total_nodes_explored=len(result.greedy_assignment.tour),
                congestion_check_id=None,
                triggered_at=triggered_at,
                courier_id=courier_id,
            ),
            CreateOptimizationRun(
                simulation_id=UUID(simulation_id),
                run_type="initial",
                algorithm="tabu_search",
                trigger_type="initial",
                total_distance_in_meters=int(result.tabu_assignment.total_distance_in_meters),
                total_travel_time_in_seconds=int(result.tabu_assignment.total_duration_in_seconds),
                computation_time_in_ms=result.tabu_time_ms,
                total_nodes_explored=len(result.tabu_assignment.tour),
                congestion_check_id=None,
                before_total_distance_in_meters=int(result.greedy_assignment.total_distance_in_meters),
                before_total_travel_time_in_seconds=int(result.greedy_assignment.total_duration_in_seconds),
                triggered_at=triggered_at,
                courier_id=courier_id,
            ),
        ]

    def _parse_assignment(
        self,
        assignment: Assignment,
        selected_node_indices: list[int],
        courier: Courier,
    ) -> ParsedAssignment:
        global_tour = [selected_node_indices[local_idx] for local_idx in assignment.tour]

        if len(global_tour) > 1 and global_tour[0] == 0 and global_tour[-1] != 0:
            global_tour.append(0)

        return ParsedAssignment(
            courier_id=courier.id,
            tour=global_tour,
            total_distance_in_meters=int(assignment.total_distance_in_meters),
            total_duration_in_seconds=int(assignment.total_duration_in_seconds),
        )

    def _build_iteration_schemas(
        self,
        logs: list[OptimizationEvent],
        solution_id: int,
        simulation_id: str,
        courier_id: int,
    ) -> list[CreateOptimizationIterationSchema]:
        schemas: list[CreateOptimizationIterationSchema] = []

        for sequence_number, event in enumerate(logs):
            schemas.append(
                CreateOptimizationIterationSchema(
                    solution_id=solution_id,
                    courier_id=courier_id,
                    simulation_id=UUID(simulation_id),
                    iteration=event.get("iteration", sequence_number),
                    event_type=event.get("event_type"),
                    elapsed_ms=event.get("elapsed_ms"),
                    timestamp=event.get("timestamp"),
                    current_distance_in_meters=event.get("current_distance_in_meters"),
                    current_duration_in_seconds=event.get("current_duration_in_seconds"),
                    best_distance_in_meters=event.get("best_distance_in_meters"),
                    best_duration_in_seconds=event.get("best_duration_in_seconds"),
                    distance_improvement_in_meters=event.get("distance_improvement_in_meters"),
                    duration_improvement_in_seconds=event.get("duration_improvement_in_seconds"),
                    improvement_percent=event.get("improvement_percent"),
                    iterations_without_improvement=event.get("iterations_without_improvement"),
                    objective_value=event.get("objective_value"),
                    operator_used=event.get("operator_used"),
                    is_new_best=event.get("is_new_best", False),
                    triggered_diversification=event.get("triggered_diversification", False),
                    used_aspiration_criteria=event.get("used_aspiration_criteria", False),
                    active_routes_count=event.get("active_routes_count"),
                    unassigned_nodes_count=event.get("unassigned_nodes_count"),
                    message=event.get("message"),
                    intermediate_tour=event.get("intermediate_tour"),
                )
            )

        return schemas

    def _build_courier_node_indices(
        self,
        simulation_id: str,
        courier_nodes: list[Node],
        nodes_by_index: dict[int, Node],
    ) -> list[int]:
        if 0 not in nodes_by_index:
            raise Exception(f"Depot node is missing for simulation {simulation_id}.")

        node_indices = [0]
        node_indices.extend(sorted(node.matrix_index for node in courier_nodes))
        return node_indices

    @staticmethod
    def _build_submatrix(
        full_matrix: list[list[int]],
        node_indices: list[int],
    ) -> list[list[int]]:
        return [
            [full_matrix[origin][destination] for destination in node_indices]
            for origin in node_indices
        ]