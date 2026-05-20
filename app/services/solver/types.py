from dataclasses import dataclass

from app.models.courier import Courier


@dataclass(slots=True)
class Route:
    courier_id: int
    route: list[int]
    load: int
    time: int


@dataclass(slots=True)
class SolverProblem:
    time_matrix: list[list[int]]
    demands: list[int]
    courier: Courier
    time_limit_seconds: int = 60
    depot_index: int = 0