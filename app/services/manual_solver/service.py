import asyncio
import time
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
from app.services.manual_solver.types import ManualSolverProblem, Assignment, OptimizationEvent, FirstSolutionStrategy, ComparisonScenario
from app.services.manual_solver.manual_solver import GreedySolver, TabuSearchSolver
from app.services.manual_solver.base import BaseManualSolverStrategy

logger = get_logger(__name__)

@dataclass(frozen=True)
class _SolverSpec:
    greedy: BaseManualSolverStrategy
    tabu_search: BaseManualSolverStrategy


def _build_solver_specs(scenario: ComparisonScenario) -> _SolverSpec:
    use_two_opt = scenario == "with_improvement"

    return _SolverSpec(
        greedy=GreedySolver(
            first_solution_strategy=FirstSolutionStrategy.NEAREST_NEIGHBOR,
            use_two_opt=use_two_opt
        ),
        
        tabu_search=TabuSearchSolver(use_two_opt_post=use_two_opt),
    )

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
    ) -> None:
        self.matrix_service = matrix_service
        self.courier_repository = courier_repository
        self.node_repository = node_repository
        self.solution_repository = solution_repository
        self.simulation_repository = simulation_repository
        self.optimization_iteration_repository = optimization_iteration_repository
        self.optimization_run_repository = optimization_run_repository

    def _run_solver_with_time(
        self, 
        solver: BaseManualSolverStrategy, 
        problem: ManualSolverProblem
    ) -> tuple[Assignment | None, float]:
        start_time = time.time()
        _, assignment = solver.solve(problem)
        computation_time_in_ms = (time.time() - start_time) * 1000
        return assignment, computation_time_in_ms

    async def solve(
        self,
        simulation_id: str,
        scenario: ComparisonScenario = "no_improvement",
    ) -> None:
        specs = _build_solver_specs(scenario)

        time_matrix = await self.matrix_service.build_time_matrix(simulation_id)
        distance_matrix = await self.matrix_service.build_distance_matrix(simulation_id)

        couriers = self.courier_repository.get_all_active_couriers_by_simulation_id(simulation_id)
        all_nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        nodes_by_index: dict[int, Node] = {node.matrix_index: node for node in all_nodes}

        total_solutions_inserted = 0
        optimization_runs: list[CreateOptimizationRun] = []

        for courier in couriers:
            courier_nodes = self.node_repository.get_nodes_by_simulation_id_and_courier_id(
                simulation_id, courier.id
            )

            if not courier_nodes:
                logger.info(
                    f"Courier {courier.id} - {courier.name} has no assigned nodes, skipping"
                )
                continue

            selected_node_indices = self._build_courier_node_indices(
                simulation_id, courier_nodes, nodes_by_index
            )
            time_submatrix = self._build_submatrix(time_matrix, selected_node_indices)
            distance_submatrix = self._build_submatrix(distance_matrix, selected_node_indices)

            logger.info(
                f"Courier {courier.id} - {courier.name}: "
                f"{len(selected_node_indices) - 1} nodes | scenario={scenario}"
            )

            problem = ManualSolverProblem(
                distance_matrix=[[float(x) for x in row] for row in distance_submatrix],
                time_matrix=[[float(x) for x in row] for row in time_submatrix],
                depot=0,
            )

            greedy_task = asyncio.to_thread(self._run_solver_with_time, specs.greedy, problem)
            tabu_task = asyncio.to_thread(self._run_solver_with_time, specs.tabu_search, problem)

            (greedy_assignment, greedy_time_ms), (tabu_assignment, tabu_time_ms) = await asyncio.gather(greedy_task, tabu_task)

            if greedy_assignment is None or tabu_assignment is None:
                raise Exception(f"No solution found for courier {courier.id} in simulation {simulation_id}.")

            triggered_at = datetime.now(timezone.utc)

            optimization_runs.extend([
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="initial",
                    algorithm="greedy_with_2opt" if scenario == "with_improvement" else "greedy_without_2opt",
                    trigger_type="initial",
                    total_distance_in_meters=int(greedy_assignment.total_distance_in_meters),
                    total_travel_time_in_seconds=int(greedy_assignment.total_duration_in_seconds),
                    computation_time_in_ms=greedy_time_ms,
                    total_nodes_explored=len(greedy_assignment.tour),
                    congestion_check_id=None,
                    triggered_at=triggered_at,
                    courier_id=courier.id,
                ),
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="initial",
                    algorithm="tabu_search_with_2opt" if scenario == "with_improvement" else "tabu_search_without_2opt",
                    trigger_type="initial",
                    total_distance_in_meters=int(tabu_assignment.total_distance_in_meters),
                    total_travel_time_in_seconds=int(tabu_assignment.total_duration_in_seconds),
                    computation_time_in_ms=tabu_time_ms,
                    total_nodes_explored=len(tabu_assignment.tour),
                    congestion_check_id=None,
                    before_total_distance_in_meters=int(greedy_assignment.total_distance_in_meters),
                    before_total_travel_time_in_seconds=int(greedy_assignment.total_duration_in_seconds),
                    triggered_at=triggered_at,
                    courier_id=courier.id,
                )
            ])

            for solver_label, assignment in (
                ("greedy", greedy_assignment),
                ("tabu_search", tabu_assignment),
            ):
                route = self._parse_assignment(assignment, selected_node_indices, courier)

                solution = await self.solution_repository.insert_solution(
                    CreateSolution(
                        routes=route.tour,
                        demand_in_kilograms=0.0,
                        time_in_seconds=route.total_duration_in_seconds,
                        courier_id=route.courier_id,
                        simulation_id=simulation_id,
                        distance_in_meters=route.total_distance_in_meters,
                    )
                )

                if assignment.logs:
                    iterations = self._build_iteration_schemas(
                        logs=assignment.logs,
                        solution_id=solution.id,
                        simulation_id=simulation_id,
                        courier_id=solution.courier_id,
                    )
                    await self.optimization_iteration_repository.bulk_insert_optimization_iterations(
                        iterations
                    )
                    logger.info(
                        f"  [{solver_label}] solution_id={solution.id} | "
                        f"inserted {len(iterations)} iteration logs"
                    )

                total_solutions_inserted += 1

        if optimization_runs:
            self.optimization_run_repository.bulk_insert_optimization_runs(optimization_runs)

        await self.simulation_repository.update_simulation(
            simulation_id,
            UpdateSimulationSchema(
                total_couriers=total_solutions_inserted // 2,
                total_active_couriers=total_solutions_inserted // 2,
            ),
        )

    async def solve_no_improvement(self, simulation_id: str) -> None:
        await self.solve(simulation_id, scenario="no_improvement")

    async def solve_with_improvement(self, simulation_id: str) -> None:
        await self.solve(simulation_id, scenario="with_improvement")

    def _parse_assignment(
        self,
        assignment: Assignment,
        selected_node_indices: list[int],
        courier: Courier,
    ) -> ParsedAssignment:
        global_tour = [selected_node_indices[local_idx] for local_idx in assignment.tour]

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

    def _build_submatrix(
        self,
        full_matrix: list[list[int]],
        node_indices: list[int],
    ) -> list[list[int]]:
        return [
            [full_matrix[origin][destination] for destination in node_indices]
            for origin in node_indices
        ]