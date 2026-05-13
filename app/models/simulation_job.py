import uuid

from sqlalchemy import UUID, Integer, String, DateTime, Enum, Float, func
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
    cleaning = 'cleaning'
    completed = 'completed'
    needed_review = 'needed_review'
    failed = 'failed'

class SimulationJob(Base):
    __tablename__ = 'simulation_jobs'
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    depot_location_address: Mapped[str] = mapped_column(String, nullable=False)
    depot_location_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    depot_location_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    max_computation_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SimulationJobStatusEnum] = mapped_column(Enum(SimulationJobStatusEnum, native_enum=False), default=SimulationJobStatusEnum.uploaded, nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_validation_status: Mapped[SimulationJobFileValidationStatusEnum] = mapped_column(Enum(SimulationJobFileValidationStatusEnum, native_enum=False), default=SimulationJobFileValidationStatusEnum.uploaded, nullable=False)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_cleaning_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleaning_status: Mapped[SimulationJobFileCleaningStatusEnum] = mapped_column(Enum(SimulationJobFileCleaningStatusEnum, native_enum=False), default=SimulationJobFileCleaningStatusEnum.pending, nullable=False)
    cleaning_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleaning_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    geocoding_status: Mapped[SimulationGeocodingStatusEnum] = mapped_column(Enum(SimulationGeocodingStatusEnum, native_enum=False), default=SimulationGeocodingStatusEnum.pending, nullable=False)
    geocoding_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_geocoding_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_completion_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculation_status: Mapped[SimulationCalculationStatusEnum] = mapped_column(Enum(SimulationCalculationStatusEnum, native_enum=False), default=SimulationCalculationStatusEnum.pending, nullable=False)
    calculation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_vehicles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)