import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import UUID, Integer, String, DateTime, Enum
from datetime import datetime, timezone
import enum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.lib.db import Base

if TYPE_CHECKING:
    from app.models.solution import Solution

class SimulationStatusEnum(enum.Enum):
    pending = 'pending'
    processing = 'processing'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
    
class Simulation(Base):
    __tablename__ = 'simulations'
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[SimulationStatusEnum] = mapped_column(Enum(SimulationStatusEnum, native_enum=False), default=SimulationStatusEnum.pending)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    upload_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    solutions: Mapped[list["Solution"]] = relationship("Solution", back_populates="simulation")

class SimulationUploadedFileStatusEnum(enum.Enum):
    uploaded = 'uploaded'
    validating = 'validating'
    validated = 'validated'
    processing = 'processing'
    failed = 'failed'
    ready = 'ready'

class SimulationUploadedFile(Base):
    __tablename__ = 'simulation_uploaded_files'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_error_path: Mapped[str | None] = mapped_column(String, nullable=True)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invalid_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[SimulationUploadedFileStatusEnum] = mapped_column(Enum(SimulationUploadedFileStatusEnum, native_enum=False), default=SimulationUploadedFileStatusEnum.uploaded)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

class SimulationUploadedFileUpdateData(BaseModel):
    file_error_path: str | None = None
    total_rows: int | None = None
    invalid_rows: int | None = None
    processed_rows: int | None = None
    progress_percentage: int | None = None
    status: SimulationUploadedFileStatusEnum | None = None
    validated_at: datetime | None = None
    
    class Config:
        from_attributes = True