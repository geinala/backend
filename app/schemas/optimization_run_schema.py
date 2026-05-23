import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

class CreateOptimizationRun(BaseModel):
    simulation_id: uuid.UUID
    courier_route_id: int
    traffic_incident_id: int | None = None
    run_type: Literal["initial", "reoptimization"]
    algorithm: Literal["greedy", "tabu_search"]
    trigger_type: str # e.g., "initial", "periodic", "traffic_update", etc.
    total_distance_in_meters: int
    total_travel_time_in_seconds: int
    computation_time_in_ms: float
    total_nodes_explored: int
    triggered_at: datetime
    before_total_distance_in_meters: int | None = None
    before_total_travel_time_in_seconds: int | None = None
    before_computation_time_in_ms: float | None = None
    before_total_nodes_explored: int | None = None

    class Config:
        from_attributes = True