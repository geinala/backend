import asyncio
from dataclasses import dataclass
import time
import math

from app.lib.logging.logging import get_logger
from app.services.manual_solver.types import (
    ManualSolverProblem,
    Assignment,
    FirstSolutionStrategy,
)
from app.services.manual_solver.manual_solver import GreedySolver, TabuSearchSolver
from app.services.manual_solver.base import BaseManualSolverStrategy

logger = get_logger(__name__)

@dataclass(frozen=True)
class TabuSearchConfig:
    """Hyperparameter config for the Tabu Search solver.

    Passed from the orchestration layer so the execution service stays
    DB-free and independently testable.
    """
    it_max_multiplier: float = 10.0
    tab_tenure_divider: float = 3.0
    it_cons_multiplier: float = 1.0
    it_div_divider: float = 5.0
    
@dataclass(frozen=True)
class SolverResult:
    """Pure-computation result for a single courier route."""
    greedy_assignment: Assignment
    tabu_assignment: Assignment
    greedy_time_ms: float
    tabu_time_ms: float

class SolverExecutionService:
    async def run(
        self,
        distance_matrix: list[list[float]],
        time_matrix: list[list[float]],
        start_index: int,
        end_index: int,
        n_nodes: int,
        tabu_config: TabuSearchConfig,
    ) -> SolverResult:
        problem = ManualSolverProblem(
            distance_matrix=distance_matrix,
            time_matrix=time_matrix,
            start_index=start_index,
            end_index=end_index,
        )

        greedy_solver = GreedySolver(
            first_solution_strategy=FirstSolutionStrategy.NEAREST_NEIGHBOR,
        )
        tabu_solver = self._build_tabu_solver(
            n_nodes=n_nodes,
            config=tabu_config,
        )

        greedy_task = asyncio.to_thread(self._run_timed, greedy_solver, problem)
        tabu_task = asyncio.to_thread(self._run_timed, tabu_solver, problem)

        (greedy_assignment, greedy_time_ms), (tabu_assignment, tabu_time_ms) = (
            await asyncio.gather(greedy_task, tabu_task)
        )

        if greedy_assignment is None or tabu_assignment is None:
            raise RuntimeError(
                "Solver returned no solution. "
                f"matrix_size={len(distance_matrix)}"
            )

        return SolverResult(
            greedy_assignment=greedy_assignment,
            tabu_assignment=tabu_assignment,
            greedy_time_ms=greedy_time_ms,
            tabu_time_ms=tabu_time_ms,
        )

    @staticmethod
    def _run_timed(
        solver: BaseManualSolverStrategy,
        problem: ManualSolverProblem,
    ) -> tuple[Assignment | None, float]:
        start = time.time()
        _, assignment = solver.solve(problem)
        elapsed_ms = (time.time() - start) * 1000
        return assignment, elapsed_ms

    @staticmethod
    def _build_tabu_solver(
        n_nodes: int,
        config: TabuSearchConfig,
    ) -> TabuSearchSolver:
        it_max = max(1, round(config.it_max_multiplier * n_nodes))
        tabu_tenure = (
            max(1, math.floor(n_nodes / config.tab_tenure_divider))
            if config.tab_tenure_divider > 0
            else 1
        )
        it_cons = round(config.it_cons_multiplier * n_nodes)
        it_div = (
            max(1, math.floor(n_nodes / config.it_div_divider))
            if config.it_div_divider > 0
            else 1
        )

        return TabuSearchSolver(
            enable_aspiration=True,
            random_seed=42,
            first_solution_strategy=FirstSolutionStrategy.NEAREST_NEIGHBOR,
            max_local_search_iterations=it_max,
            early_stop_no_improvement_iterations=round(it_max * 0.2),
            tabu_tenure=tabu_tenure,
            diversify_after_iterations=it_cons,
            diversification_strength=it_div,
            optimization_target="time",
            track_iteration_history=True,
            save_intermediate_solutions=True,
        )
