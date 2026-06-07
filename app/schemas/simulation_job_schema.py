from datetime import datetime

from pydantic import BaseModel

from app.models.simulation_job import (
    SimulationJobStatusEnum,
    SimulationGeocodingStatusEnum,
    SimulationCalculationStatusEnum,
    SimulationJobFileValidationStatusEnum,
    SimulationJobFileCleaningStatusEnum,
    OptimizationAlgorithmEnum,
)


class SimulationJobUpdateData(BaseModel):
    status: SimulationJobStatusEnum | None = None
    current_step: int | None = None
    started_at: datetime | None = None
    depot_id: int | None = None
    depot_location_address: str | None = None
    depot_location_latitude: float | None = None
    depot_location_longitude: float | None = None
    algorithm: OptimizationAlgorithmEnum | None = None
    computation_time_limit_in_seconds: int | None = None
    random_seed: int | None = None
    enable_resequence: bool | None = None
    enable_aspiration: bool | None = None
    resequence_improvement_threshold_percent: float | None = None
    congestion_delay_threshold_in_seconds: int | None = None
    early_stop_no_improvement_iterations: int | None = None
    tabu_iterations: int | None = None
    tabu_tenure: int | None = None
    max_neighbors_2opt: int | None = None
    diversify_after_iterations: int | None = None
    diversification_strength: int | None = None
    total_demand_in_kilograms: float | None = None
    total_couriers: int | None = None
    total_active_couriers: int | None = None
    total_nodes: int | None = None
    file_path: str | None = None
    file_validation_status: (SimulationJobFileValidationStatusEnum | None) = None
    file_total_rows: int | None = None
    file_valid_rows: int | None = None
    file_invalid_rows: int | None = None
    file_processed_rows: int | None = None
    file_progress_percentage: int | None = None
    file_validation_started_at: datetime | None = None
    file_validation_completed_at: datetime | None = None
    cleaning_status: (SimulationJobFileCleaningStatusEnum | None) = None
    cleaning_total_rows: int | None = None
    cleaning_processed_rows: int | None = None
    cleaning_progress_percentage: int | None = None
    cleaning_started_at: datetime | None = None
    cleaning_completed_at: datetime | None = None
    geocoding_status: SimulationGeocodingStatusEnum | None = None
    geocoding_total_rows: int | None = None
    geocoding_processed_rows: int | None = None
    geocoding_progress_percentage: int | None = None
    geocoding_started_at: datetime | None = None
    geocoded_at: datetime | None = None
    geocoding_estimated_completion_time: datetime | None = None
    calculation_status: (SimulationCalculationStatusEnum | None) = None
    calculation_started_at: datetime | None = None
    calculated_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True