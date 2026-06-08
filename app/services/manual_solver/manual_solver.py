from app.services.manual_solver.base import BaseManualSolverStrategy
from app.services.manual_solver.types import (
    ManualSolverProblem,
    Assignment,
    RoutingSearchParameters,
    FirstSolutionStrategy,
    LocalSearchMetaheuristic,
    LocalImprovementStrategy,
)
from app.services.manual_solver.routing_model import RoutingModel


class ManualSolverStrategy(BaseManualSolverStrategy):

    def __init__(
        self,
        *,
        params: RoutingSearchParameters,
    ) -> None:
        self.params = params

    def solve(
        self,
        problem: ManualSolverProblem,
    ) -> tuple[RoutingModel, Assignment | None]:
        model = RoutingModel(problem)
        try:
            assignment = model.SolveWithParameters(self.params)
            return model, assignment
        except Exception:
            return model, None

class GreedySolver(BaseManualSolverStrategy):
    def __init__(
        self,
        *,
        first_solution_strategy: FirstSolutionStrategy = FirstSolutionStrategy.AUTOMATIC,
        optimization_target: str = "time",
        use_two_opt: bool = False,
        max_improvement_iterations: int = 1000,
        max_execution_time_seconds: float = 30.0,
    ) -> None:
        self.params = RoutingSearchParameters(
            first_solution_strategy=first_solution_strategy,
            local_search_metaheuristic=LocalSearchMetaheuristic.NONE,
            local_improvement_strategy=(
                LocalImprovementStrategy.TWO_OPT if use_two_opt else LocalImprovementStrategy.NONE
            ),
            optimization_target=optimization_target,
            max_improvement_iterations=max_improvement_iterations,
            max_execution_time_seconds=max_execution_time_seconds,
        )

    def solve(
        self,
        problem: ManualSolverProblem,
    ) -> tuple[RoutingModel, Assignment | None]:
        model = RoutingModel(problem)
        try:
            assignment = model.SolveWithParameters(self.params)
            return model, assignment
        except Exception:
            return model, None

class TabuSearchSolver(BaseManualSolverStrategy):
    def __init__(
        self,
        *,
        first_solution_strategy: FirstSolutionStrategy = FirstSolutionStrategy.AUTOMATIC,
        optimization_target: str = "time",
        max_local_search_iterations: int = 500,
        max_execution_time_seconds: float = 60.0,
        early_stop_no_improvement_iterations: int = 150,
        tabu_tenure: int | None = None,
        enable_aspiration: bool = True,
        use_oropt_neighborhood: bool = True,
        max_neighbors_2opt: int = 30,
        max_neighbors_oropt: int = 20,
        diversify_after_iterations: int = 50,
        diversification_strength: int = 1,
        use_two_opt_post: bool = False,
        max_improvement_iterations: int = 1000,
        random_seed: int = 42,
        track_iteration_history: bool = True,
        save_intermediate_solutions: bool = False,
    ) -> None:
        self.params = RoutingSearchParameters(
            first_solution_strategy=first_solution_strategy,
            local_search_metaheuristic=LocalSearchMetaheuristic.TABU_SEARCH,
            local_improvement_strategy=(
                LocalImprovementStrategy.TWO_OPT if use_two_opt_post else LocalImprovementStrategy.NONE
            ),
            optimization_target=optimization_target,
            max_local_search_iterations=max_local_search_iterations,
            max_execution_time_seconds=max_execution_time_seconds,
            early_stop_no_improvement_iterations=early_stop_no_improvement_iterations,
            tabu_tenure=tabu_tenure,
            enable_aspiration=enable_aspiration,
            use_oropt_neighborhood=use_oropt_neighborhood,
            max_neighbors_2opt=max_neighbors_2opt,
            max_neighbors_oropt=max_neighbors_oropt,
            diversify_after_iterations=diversify_after_iterations,
            diversification_strength=diversification_strength,
            max_improvement_iterations=max_improvement_iterations,
            random_seed=random_seed,
            track_iteration_history=track_iteration_history,
            save_intermediate_solutions=save_intermediate_solutions,
        )

    def solve(
        self,
        problem: ManualSolverProblem,
    ) -> tuple[RoutingModel, Assignment | None]:
        model = RoutingModel(problem)
        try:
            assignment = model.SolveWithParameters(self.params)
            return model, assignment
        except Exception:
            return model, None