import uuid

from sqlalchemy import UUID, ForeignKey, Integer, String, DateTime, func
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class SimulationJobUploadedFileError(Base):
    __tablename__ = 'simulation_job_uploaded_file_errors'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    simulation_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_jobs.id"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    invalid_value: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)