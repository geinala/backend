import uuid

from sqlalchemy import UUID, Boolean, ForeignKey, Integer, String, DateTime, Enum, Float, func
from datetime import datetime
import enum

from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class SimulationJobStatusEnum(enum.Enum):
    uploaded = 'uploaded'
    processing = 'processing'
    completed = 'completed'
    failed = 'failed'
    
class SimulationGeocodingStatusEnum(enum.Enum):
    pending = 'pending'
    in_progress = 'in_progress'
    needed_review = 'needed_review'
    completed = 'completed'
    failed = 'failed'
    
class SimulationCalculationStatusEnum(enum.Enum):
    pending = 'pending'
    in_progress = 'in_progress'
    completed = 'completed'
    failed = 'failed'
    
class SimulationJobFileValidationStatusEnum(enum.Enum):
    uploaded = 'uploaded'
    validating = 'validating'
    validated = 'validated'
    needed_review = 'needed_review'
    completed = 'completed'
    failed = 'failed'

class SimulationJobFileCleaningStatusEnum(enum.Enum):
    pending = 'pending'
    in_progress = 'in_progress'
    completed = 'completed'
    needed_review = 'needed_review'
    failed = 'failed'
    
class OptimizationAlgorithmEnum(enum.Enum):
    manual_without_optimization = "manual_without_optimization"
    manual_with_optimization = "manual_with_optimization"
    google_or_tools = "google_or_tools"

class SimulationJob(Base):
    __tablename__ = "simulation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(300), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[SimulationJobStatusEnum] = mapped_column(Enum(SimulationJobStatusEnum, native_enum=False), nullable=False, default=SimulationJobStatusEnum.uploaded, index=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    depot_id: Mapped[int] = mapped_column(Integer, ForeignKey("depots.id"), nullable=False, index=True)
    depot_location_address: Mapped[str] = mapped_column(String, nullable=False)
    depot_location_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    depot_location_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    algorithm: Mapped[OptimizationAlgorithmEnum] = mapped_column(Enum(OptimizationAlgorithmEnum, native_enum=False), nullable=False, default=OptimizationAlgorithmEnum.google_or_tools)
    computation_time_limit_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    enable_resequence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enable_aspiration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    resequence_improvement_threshold_percent: Mapped[float | None] = mapped_column(Float, nullable=True, default=5)
    congestion_delay_threshold_in_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True, default=300)
    early_stop_no_improvement_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True, default=100)
    tabu_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tabu_tenure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_neighbors_2opt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diversify_after_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diversification_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_demand_in_kilograms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_couriers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_active_couriers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_validation_status: Mapped[SimulationJobFileValidationStatusEnum] = mapped_column(Enum(SimulationJobFileValidationStatusEnum, native_enum=False), nullable=False, default=SimulationJobFileValidationStatusEnum.uploaded)
    file_total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_processed_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_validation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_validation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleaning_status: Mapped[SimulationJobFileCleaningStatusEnum] = mapped_column(Enum(SimulationJobFileCleaningStatusEnum, native_enum=False), nullable=False, default=SimulationJobFileCleaningStatusEnum.pending)
    cleaning_total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleaning_processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleaning_progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleaning_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleaning_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    geocoding_status: Mapped[SimulationGeocodingStatusEnum] = mapped_column(Enum(SimulationGeocodingStatusEnum, native_enum=False), nullable=False, default=SimulationGeocodingStatusEnum.pending)
    geocoding_total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    geocoding_processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    geocoding_progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    geocoding_estimated_completion_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    geocoding_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculation_status: Mapped[SimulationCalculationStatusEnum] = mapped_column(Enum(SimulationCalculationStatusEnum, native_enum=False), nullable=False, default=SimulationCalculationStatusEnum.pending)
    calculation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)