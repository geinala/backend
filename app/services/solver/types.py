from dataclasses import dataclass

from app.models.vehicle import Vehicle


@dataclass(slots=True)
class Route:
    vehicle_id: int
    route: list[int]
    load: int
    time: int


@dataclass(slots=True)
class SolverProblem:
    time_matrix: list[list[int]]
    demands: list[int]
    vehicle_capacities: list[int]
    vehicles: list[Vehicle]
    time_limit_seconds: int = 60
    depot_index: int = 0

    @property
    def num_vehicles(self) -> int:
        return len(self.vehicles)
