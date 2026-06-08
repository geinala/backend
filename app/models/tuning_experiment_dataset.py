from datetime import datetime
import enum
from uuid import uuid4

from sqlalchemy import (
    UUID,
    DateTime,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.db import Base

class TuningExperimentDatasetStatusEnum(enum.Enum):
    uploaded = 'uploaded'
    validating = 'validating'
    validated = 'validated'
    cleaning = 'cleaning'
    cleaned = 'cleaned'
    geocoding = 'geocoding'
    geocoded = 'geocoded'
    completed = 'completed'
    failed = 'failed'

class TuningExperimentDataset(Base):
    __tablename__ = "tuning_experiment_datasets"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_file_path: Mapped[str] = mapped_column(
        "file_path",
        String,
        nullable=False,
    )
    status: Mapped[TuningExperimentDatasetStatusEnum] = mapped_column(
        "status",
        String,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)