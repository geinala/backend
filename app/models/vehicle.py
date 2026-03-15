import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import UUID, Boolean, Float, ForeignKey, String, Integer
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

class CreateVehicleRoute(BaseModel):
    solution_id: int
    vehicle_id: int
    route_version: int
    is_active: bool
    total_distance_in_meters: int
    total_time_in_seconds: int