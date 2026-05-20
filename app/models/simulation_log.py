
import uuid

from app.lib.db import Base
from sqlalchemy import UUID, Integer, String, ForeignKey, DateTime, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class SimulationLog(Base):
    __tablename__ = 'simulation_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=False)
    courier_route_id: Mapped[int] = mapped_column(Integer, ForeignKey("courier_routes.id"), nullable=True)
    courier_id: Mapped[int] = mapped_column(Integer, ForeignKey("couriers.id"), nullable=True)
    log_level: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    log_metadata: Mapped[str] = mapped_column("metadata", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
