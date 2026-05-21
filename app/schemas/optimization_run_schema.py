import uuid
from typing import Literal

from pydantic import BaseModel

class CreateOptimizationRun(BaseModel):
    simulation_id: uuid.UUID
    courier_route_id: int
    run_type: Literal["initial", "reoptimization"]
    algorithm: Literal["greedy", "tabu_search"]
    trigger_type: str # e.g., "initial", "periodic", "traffic_update", etc.
    total_distance_in_meters: int
    total_travel_time_in_seconds: int
    computation_time_in_ms: float
    total_nodes_explored: int
    class Config:
        from_attributes = True