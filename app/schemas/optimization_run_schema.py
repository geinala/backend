import uuid
from pydantic import BaseModel

class CreateOptimizationRun(BaseModel):
    simulation_id: uuid.UUID
    courier_route_id: int
    run_type: str
    algorithm: str
    trigger_type: str
    total_distance_in_meters: int
    total_travel_time_in_seconds: int
    computation_time_in_ms: float