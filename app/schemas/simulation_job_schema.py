
from pydantic import BaseModel
from datetime import datetime

from app.models.simulation_job import SimulationGeocodingStatusEnum, SimulationJobFileValidationStatusEnum, SimulationJobStatusEnum, SimulationCalculationStatusEnum


class SimulationJobUpdateData(BaseModel):
    status: SimulationJobStatusEnum | None = None
    current_step: int | None = None
    file_validation_status: SimulationJobFileValidationStatusEnum | None = None
    total_rows: int | None = None
    valid_rows: int | None = None
    invalid_rows: int | None = None
    processed_rows: int | None = None
    progress_percentage: int | None = None
    validation_started_at: datetime | None = None
    validation_completed_at: datetime | None = None
    geocoding_status: SimulationGeocodingStatusEnum | None = None
    geocoding_started_at: datetime | None = None
    geocoded_at: datetime | None = None
    calculation_status: SimulationCalculationStatusEnum | None = None
    calculation_started_at: datetime | None = None
    calculated_at: datetime | None = None
    total_vehicles: int | None = None
    total_nodes: int | None = None
    updated_at: datetime | None = None
    
    class Config:
        from_attributes = True