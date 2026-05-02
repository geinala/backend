import enum

from pydantic import BaseModel

from app.lib.db import Base
from sqlalchemy import Integer, String, ForeignKey, DateTime, Enum, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class RouteStatusEnum(enum.Enum):
    planned = "planned"
    running = "running"
    completed = "completed"
    cancelled = "cancelled"

class RouteLeg(Base):
    __tablename__ = 'route_legs'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_route_id: Mapped[int] = mapped_column(Integer, ForeignKey('vehicle_routes.id'), nullable=False)
    origin_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    origin_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    destination_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    destination_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # To maintain the order of legs in the route
    encoded_polyline: Mapped[str] = mapped_column(String, nullable=False)  # To store the encoded polyline for this leg
    encoded_polyline_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # Precision of the encoded polyline
    distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    travel_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    traffic_delay_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    traffic_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    no_traffic_travel_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    historic_traffic_travel_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    live_traffic_incidents_travel_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    route_status: Mapped[RouteStatusEnum] = mapped_column(
        Enum(RouteStatusEnum, name="route_status_enum", native_enum=False),
        nullable=False,
        default=RouteStatusEnum.planned,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
class CreateRouteLeg(BaseModel):
    vehicle_route_id: int
    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    sequence: int
    encoded_polyline: str
    encoded_polyline_precision: int
    distance_in_meters: int
    travel_time_in_seconds: int
    traffic_delay_in_seconds: int
    traffic_distance_in_meters: int
    departure_time: datetime
    arrival_time: datetime
    no_traffic_travel_time_in_seconds: int
    historic_traffic_travel_time_in_seconds: int
    live_traffic_incidents_travel_time_in_seconds: int
    route_status: RouteStatusEnum = RouteStatusEnum.planned