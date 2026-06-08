from ortools.constraint_solver import pywrapcp

from app.services.or_tools_solver.ortools_solver import build_tabu_search_solver
from app.services.or_tools_solver.types import SolverProblem


class TabuSearchSolver:
    def __init__(self):
        self.strategy = build_tabu_search_solver()

    def solve(
        self,
        problem: SolverProblem,
    ) -> tuple[pywrapcp.RoutingIndexManager, pywrapcp.RoutingModel, pywrapcp.Assignment | None]:
        return self.strategy.solve(problem)
