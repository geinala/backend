
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, Integer, String, ForeignKey, DateTime, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.db import Base

if TYPE_CHECKING:
    from app.models.courier_route import CourierRoute
    from app.models.simulation import Simulation

class OptimizationRun(Base):
    __tablename__ = 'optimization_runs'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=False)
    traffic_incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    courier_route_id: Mapped[int] = mapped_column(Integer, ForeignKey('courier_routes.id'), nullable=False)
    run_type: Mapped[str] = mapped_column(String, nullable=False)
    algorithm: Mapped[str] = mapped_column(String, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String, nullable=False)
    total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    total_travel_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    computation_time_in_ms: Mapped[float] = mapped_column(Float, nullable=False)
    total_nodes_explored: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    before_total_distance_in_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_total_travel_time_in_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_computation_time_in_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    before_total_nodes_explored: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    simulation: Mapped["Simulation"] = relationship("Simulation")
    courier_route: Mapped["CourierRoute"] = relationship("CourierRoute")