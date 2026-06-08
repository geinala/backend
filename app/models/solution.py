import uuid

from sqlalchemy import Integer, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.lib.db import Base

class Solution(Base):
    __tablename__ = "solutions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=False)
    courier_id: Mapped[int] = mapped_column(Integer, ForeignKey("couriers.id"), nullable=False)
    routes: Mapped[list[int]] = mapped_column(JSONB, nullable=False)  # Array of node indices representing the route
    demand_in_kilograms: Mapped[float] = mapped_column(Float, nullable=False)  # Total demand served by this vehicle
    time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)  # Total time for this route
    distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)  # Total distance for this route
    
    simulation = relationship("Simulation", back_populates="solutions")
    courier = relationship("Courier", back_populates="solutions")