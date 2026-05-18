import enum
import uuid

from sqlalchemy import UUID, Enum, Integer, String, DateTime, Float, func
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class ResolutionStatusEnum(enum.Enum):
    pending = 'pending'
    auto_solved = 'auto_solved'
    manual_override = 'manual_override'
    needed_review = 'needed_review'
    failed = 'failed'
    
class SimulationUploadedRow(Base):
    __tablename__ = 'simulation_uploaded_rows'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    nosi: Mapped[str | None] = mapped_column(String, nullable=True)
    courier: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_address: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_address: Mapped[str | None] = mapped_column(String, nullable=True)
    final_address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_ignored: Mapped[bool] = mapped_column(nullable=False, default=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocode_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocode_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    geocode_response: Mapped[str | None] = mapped_column(String, nullable=True)  # Store geocode response as JSON string
    resolution_status: Mapped[ResolutionStatusEnum] = mapped_column(Enum(ResolutionStatusEnum, native_enum=False), nullable=False, default=ResolutionStatusEnum.pending)
    resolution_source: Mapped[str | None] = mapped_column(String, nullable=True) # e.g., "SYSTEM" or "USER"
    start_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    error_details: Mapped[str | None] = mapped_column(String, nullable=True)  # Store error details as JSON string
