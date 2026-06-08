import uuid

from sqlalchemy import UUID, Integer, String, DateTime, Float, func
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base
    
class TuningExperimentUploadedRow(Base):
    __tablename__ = 'tuning_experiment_uploaded_rows'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tuning_experiment_dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    nosi: Mapped[str | None] = mapped_column(String, nullable=True)
    courier: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_address: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_address: Mapped[str | None] = mapped_column(String, nullable=True)
    final_address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocode_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocode_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    geocode_response: Mapped[str | None] = mapped_column(String, nullable=True)  # Store geocode response as JSON string
    start_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
