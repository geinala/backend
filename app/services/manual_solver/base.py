from abc import ABC, abstractmethod

from app.services.manual_solver.types import ManualSolverProblem, Assignment
from app.services.manual_solver.routing_model import RoutingModel


class BaseManualSolverStrategy(ABC):
    @abstractmethod
    def solve(
        self,
        problem: ManualSolverProblem,
    ) -> tuple[RoutingModel, Assignment | None]:
        raise NotImplementedError