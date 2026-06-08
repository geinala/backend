from ortools.constraint_solver import pywrapcp

from app.services.or_tools_solver.ortools_solver import build_greedy_solver
from app.services.or_tools_solver.types import SolverProblem


class GreedySolver:
    def __init__(self):
        self.strategy = build_greedy_solver()

    def solve(
        self,
        problem: SolverProblem,
    ) -> tuple[pywrapcp.RoutingIndexManager, pywrapcp.RoutingModel, pywrapcp.Assignment | None]:
        return self.strategy.solve(problem)
