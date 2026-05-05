import uuid

from sqlalchemy import UUID, Integer, String, DateTime, Float, func
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class SimulationUploadedRow(Base):
    __tablename__ = 'simulation_uploaded_rows'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    nosi: Mapped[str | None] = mapped_column(String, nullable=True)
    courier: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    error_details: Mapped[str | None] = mapped_column(String, nullable=True)  # Store error details as JSON string