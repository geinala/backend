import uuid
from typing import TYPE_CHECKING
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import UUID, Boolean, Float, ForeignKey, String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.lib.db import Base

if TYPE_CHECKING:
    from app.models.solution import Solution


class Vehicle(Base):
    __tablename__ = 'vehicles'
    
    id: Mapped[int] = mapped_column (Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('simulations.id'), nullable=False)
    name: Mapped[str] = mapped_column(String    , nullable=False)
    max_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    solutions: Mapped[list["Solution"]] = relationship("Solution", back_populates="vehicle")
    
class VehicleRoute(Base):
    __tablename__ = 'vehicle_routes'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solution_id: Mapped[int] = mapped_column(Integer, ForeignKey('solutions.id'), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(Integer, ForeignKey('vehicles.id'), nullable=False)
    route_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    total_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    reoptimized_from_route_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey('vehicle_routes.id'),
        nullable=True,
    )
    trigger_node_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('nodes.id'), nullable=True)
    triggered_by_traffic: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class CreateVehicleRoute(BaseModel):
    solution_id: int
    vehicle_id: int
    route_version: int
    is_active: bool
    total_distance_in_meters: int
    total_time_in_seconds: int
    reoptimized_from_route_id: int | None = None
    trigger_node_id: int | None = None
    triggered_by_traffic: bool = False