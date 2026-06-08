from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    UUID,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.db import Base


class TuningExperiment(Base):
    __tablename__ = "tuning_experiments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_batch_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    dataset_file_path: Mapped[str] = mapped_column(
        "file_path",
        String,
        nullable=False,
    )
    algorithm_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("algorithm_configs.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="running",
        server_default="running",
    )
    base_n_c: Mapped[int] = mapped_column(Integer, nullable=False)
    it_max: Mapped[int] = mapped_column(Integer, nullable=False)
    tab_tenure: Mapped[int] = mapped_column(Integer, nullable=False)
    it_cons: Mapped[int] = mapped_column(Integer, nullable=False)
    it_div: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=42,
        server_default="42",
    )
    early_stop_no_improvement_iterations: Mapped[int | None] = mapped_column(
        Integer
    )
    initial_fitness_score: Mapped[float | None] = mapped_column(Float)
    best_fitness_score: Mapped[float | None] = mapped_column(Float)
    execution_time_ms: Mapped[float | None] = mapped_column(Float)
    convergence_iteration: Mapped[int | None] = mapped_column(Integer)
    improvement_percentage: Mapped[float | None] = mapped_column(Float)
    best_route_payload: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))