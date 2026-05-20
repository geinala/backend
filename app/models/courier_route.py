from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base
    
class CourierRoute(Base):
    __tablename__ = 'courier_routes'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solution_id: Mapped[int] = mapped_column(Integer, ForeignKey('solutions.id'), nullable=False)
    courier_id: Mapped[int] = mapped_column(Integer, ForeignKey('couriers.id'), nullable=False)
    route_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    total_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    reoptimized_from_route_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey('courier_routes.id'),
        nullable=True,
    )
    trigger_node_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('nodes.id'), nullable=True)
    triggered_by_traffic: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)