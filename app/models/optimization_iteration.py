import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.db import Base

if TYPE_CHECKING:
    from app.models.simulation import Simulation


class OptimizationIteration(Base):
    __tablename__ = "optimization_iterations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=True, index=True)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    current_distance_in_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_duration_in_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_distance_in_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_duration_in_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_improvement_in_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_improvement_in_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    improvement_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    iterations_without_improvement: Mapped[int | None] = mapped_column(Integer, nullable=True)
    objective_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    operator_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_new_best: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    triggered_diversification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_aspiration_criteria: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_routes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unassigned_nodes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    intermediate_tour: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    simulation: Mapped["Simulation"] = relationship(
        "Simulation", back_populates="optimization_iterations")