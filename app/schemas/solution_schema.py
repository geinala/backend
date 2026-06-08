from pydantic import BaseModel, ConfigDict


class CreateSolution(BaseModel):
    simulation_id: str
    courier_id: int
    routes: list[int]
    demand_in_kilograms: float
    time_in_seconds: int
    distance_in_meters: int
    model_config = ConfigDict(from_attributes=True)