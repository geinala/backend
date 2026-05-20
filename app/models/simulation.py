import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, Integer, String, DateTime, Enum, Float, func
from datetime import datetime
import enum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.lib.db import Base

if TYPE_CHECKING:
    from app.models.solution import Solution

class SimulationStatusEnum(enum.Enum):
    optimizing = 'optimizing'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
    
class Simulation(Base):
    __tablename__ = 'simulations'
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[SimulationStatusEnum] = mapped_column(
        Enum(SimulationStatusEnum, native_enum=False),
        default=SimulationStatusEnum.optimizing,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    computation_time_limit_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    total_demand_in_kilograms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_couriers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_active_couriers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_completed_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_nodes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    simulation_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    solutions: Mapped[list["Solution"]] = relationship("Solution", back_populates="simulation")
