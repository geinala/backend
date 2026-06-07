import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.db import Base
from app.models.simulation_job import OptimizationAlgorithmEnum

if TYPE_CHECKING:
    from app.models.solution import Solution


class SimulationStatusEnum(enum.Enum):
    pending = "pending"
    stopped = "stopped"
    optimizing = "optimizing"
    running = "running"
    completed = "completed"
    failed = "failed"


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    simulation_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_jobs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[SimulationStatusEnum] = mapped_column(Enum(SimulationStatusEnum, native_enum=False), nullable=False, default=SimulationStatusEnum.optimizing, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    algorithm: Mapped[OptimizationAlgorithmEnum] = mapped_column(Enum(OptimizationAlgorithmEnum, native_enum=False), nullable=False)
    computation_time_limit_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    enable_resequence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enable_aspiration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    resequence_improvement_threshold_percent: Mapped[float | None] = mapped_column(Float, nullable=True, default=5)
    congestion_delay_threshold_in_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True, default=300)
    early_stop_no_improvement_iterations: Mapped[int | None] = mapped_column(       Integer, nullable=True, default=100)
    tabu_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tabu_tenure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_neighbors_2opt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_neighbors_oropt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diversify_after_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diversification_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depot_id: Mapped[int] = mapped_column(Integer, ForeignKey("depots.id"), nullable=False, index=True)
    depot_location_address: Mapped[str] = mapped_column(String, nullable=False)
    depot_location_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    depot_location_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    total_demand_in_kilograms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_couriers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_active_couriers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_completed_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    initial_total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    initial_total_duration_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    final_total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    final_total_duration_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distance_improvement_in_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_improvement_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_reoptimized_routes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_incidents_affecting_routes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    solutions: Mapped[list["Solution"]] = relationship(
        "Solution",
        back_populates="simulation",
    )