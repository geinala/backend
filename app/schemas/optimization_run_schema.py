import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

class CreateOptimizationRun(BaseModel):
    simulation_id: uuid.UUID
    run_type: Literal["initial", "reoptimization", "reoptimization_candidate", "baseline_tracking", "duration_update"]
    courier_id: int
    algorithm: Literal["greedy_or_tools", "tabu_search_or_tools", "greedy_with_2opt", "greedy_without_2opt", "tabu_search_with_2opt", "tabu_search_without_2opt"]
    trigger_type: str # e.g., "initial", "periodic", "traffic_update", etc.
    total_distance_in_meters: int
    total_travel_time_in_seconds: int
    computation_time_in_ms: float
    total_nodes_explored: int
    triggered_at: datetime
    congestion_check_id: int | None = None
    before_total_distance_in_meters: int | None = None
    before_total_travel_time_in_seconds: int | None = None

    class Config:
        from_attributes = True