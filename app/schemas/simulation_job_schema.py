
from pydantic import BaseModel
from datetime import datetime

from app.models.simulation_job import SimulationGeocodingStatusEnum, SimulationJobFileCleaningStatusEnum, SimulationJobFileValidationStatusEnum, SimulationJobStatusEnum, SimulationCalculationStatusEnum


class SimulationJobUpdateData(BaseModel):
    status: SimulationJobStatusEnum | None = None
    current_step: int | None = None
    file_validation_status: SimulationJobFileValidationStatusEnum | None = None
    file_total_rows: int | None = None
    file_valid_rows: int | None = None
    file_invalid_rows: int | None = None
    file_processed_rows: int | None = None
    file_progress_percentage: int | None = None
    file_validation_started_at: datetime | None = None
    file_validation_completed_at: datetime | None = None
    cleaning_progress_percentage: int | None = None
    geocoding_status: SimulationGeocodingStatusEnum | None = None
    geocoding_started_at: datetime | None = None
    geocoded_at: datetime | None = None
    geocoding_total_rows: int | None = None
    geocoding_processed_rows: int | None = None
    geocoding_progress_percentage: int | None = None
    geocoding_estimated_completion_time: datetime | None = None
    calculation_status: SimulationCalculationStatusEnum | None = None
    calculation_started_at: datetime | None = None
    calculated_at: datetime | None = None
    total_vehicles: int | None = None
    total_nodes: int | None = None
    updated_at: datetime | None = None
    cleaning_status: SimulationJobFileCleaningStatusEnum | None = None
    cleaning_started_at: datetime | None = None
    cleaning_completed_at: datetime | None = None

    class Config:
        from_attributes = True