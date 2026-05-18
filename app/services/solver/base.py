from abc import ABC, abstractmethod

from ortools.constraint_solver import pywrapcp

from app.services.solver.types import SolverProblem


class BaseSolverStrategy(ABC):
    @abstractmethod
    def solve(
        self,
        problem: SolverProblem,
    ) -> tuple[pywrapcp.RoutingIndexManager, pywrapcp.RoutingModel, pywrapcp.Assignment | None]:
        raise NotImplementedError
