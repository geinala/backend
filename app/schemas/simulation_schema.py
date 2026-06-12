from datetime import datetime
from pydantic import BaseModel

from app.models.simulation import SimulationStatusEnum


class UpdateSimulationSchema(BaseModel):
    title: str | None = None
    status: SimulationStatusEnum | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    is_with_adaptive_parameters: bool | None = None
    resequence_improvement_threshold_percent: float | None = None
    congestion_delay_threshold_in_seconds: int | None = None
    depot_id: int | None = None
    depot_location_address: str | None = None
    depot_location_latitude: float | None = None
    depot_location_longitude: float | None = None
    total_demand_in_kilograms: float | None = None
    total_couriers: int | None = None
    total_active_couriers: int | None = None
    total_completed_nodes: int | None = None
    total_nodes: int | None = None
    initial_total_distance_in_meters: int | None = None
    initial_total_duration_in_seconds: int | None = None
    final_total_distance_in_meters: int | None = None
    final_total_duration_in_seconds: int | None = None
    distance_improvement_in_meters: int | None = None
    duration_improvement_in_seconds: int | None = None
    total_reoptimized_routes: int | None = None
    total_incidents_affecting_routes: int | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True