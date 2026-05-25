from pydantic import BaseModel


class CreateSolution(BaseModel):
    simulation_id: str
    courier_id: int
    routes: list[int]
    demand_in_kilograms: float
    time_in_seconds: int
