from datetime import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from app.lib.db import Base, enum_values

class MatrixBatchStatusEnum(enum.Enum):
    SUBMITTED = "submitted"
    VALIDATED = "validated"
    COMPLETED = "completed"
    FAILED = "failed"

class MatrixBatch(Base):
    __tablename__ = 'matrix_batches'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    origin_start_index: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_end_index: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_start_index: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_end_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tomtom_job_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[MatrixBatchStatusEnum] = mapped_column(
        Enum(
            MatrixBatchStatusEnum, 
            name="matrix_batch_status_enum", 
            values_callable=enum_values
            ),
        default=MatrixBatchStatusEnum.SUBMITTED, 
        nullable=False
        )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
class MatrixResult(Base):
    __tablename__ = 'matrix_results'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    origin_index: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_index: Mapped[int] = mapped_column(Integer, nullable=False)
    length_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    travel_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    traffic_delay_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    matrix_batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('matrix_batches.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
class CreateMatrixBatchData(BaseModel):
    simulation_id: str
    origin_start_index: int
    origin_end_index: int
    destination_start_index: int
    destination_end_index: int
    tomtom_job_id: str
    status: MatrixBatchStatusEnum = MatrixBatchStatusEnum.SUBMITTED
    
class UpdateMatrixBatchStatusData(BaseModel):
    status: MatrixBatchStatusEnum
    completed_at: datetime | None = None
    
class CreateMatrixResultData(BaseModel):
    simulation_id: str
    origin_index: int
    destination_index: int
    length_in_meters: int
    travel_time_in_seconds: int
    traffic_delay_in_seconds: int
    matrix_batch_id: int