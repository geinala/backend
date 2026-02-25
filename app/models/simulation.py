from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Enum
from datetime import datetime, timezone
import enum

from sqlalchemy.orm import Mapped, mapped_column

Base = declarative_base()

class SimulationStatusEnum(enum.Enum):
    pending = 'pending'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
    
class Simulation(Base):
    __tablename__ = 'simulations'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String(300), nullable=False)
    status = Column(Enum(SimulationStatusEnum, native_enum=False), default=SimulationStatusEnum.pending)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    upload_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
class SimulationUploadedFileStatusEnum(enum.Enum):
    uploaded = 'uploaded'
    validating = 'validating'
    failed = 'failed'
    ready = 'ready'

class SimulationUploadedFile(Base):
    __tablename__ = 'simulation_uploaded_files'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_error_path = Column(String, nullable=True)
    total_rows = Column(Integer, nullable=True)
    invalid_rows = Column(Integer, nullable=True)
    processed_rows = Column(Integer, nullable=True)
    progress_percentage = Column(Integer, default=0)
    status = Column(Enum(SimulationUploadedFileStatusEnum, native_enum=False), default=SimulationUploadedFileStatusEnum.uploaded)
    validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
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