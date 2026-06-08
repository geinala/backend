from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateOptimizationIterationSchema(BaseModel):
    simulation_id: UUID | None = None
    courier_id: int | None = None
    solution_id: int | None = None
    event_type: str | None = None
    iteration: int
    elapsed_ms: float | None = None
    timestamp: datetime | None = None
    current_distance_in_meters: float | None = None
    current_duration_in_seconds: float | None = None
    best_distance_in_meters: float | None = None
    best_duration_in_seconds: float | None = None
    distance_improvement_in_meters: float | None = None
    duration_improvement_in_seconds: float | None = None
    improvement_percent: float | None = None
    iterations_without_improvement: int | None = None
    objective_value: float | None = None
    operator_used: str | None = None
    is_new_best: bool = False
    triggered_diversification: bool = False
    used_aspiration_criteria: bool = False
    active_routes_count: int | None = None
    unassigned_nodes_count: int | None = None
    message: str | None = None
    intermediate_tour: list[int] | None = None
    model_config = ConfigDict(from_attributes=True)