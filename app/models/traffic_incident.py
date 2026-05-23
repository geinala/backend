import datetime
from datetime import datetime
import uuid

from sqlalchemy import DateTime, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class TrafficIncident(Base):
    __tablename__ = "traffic_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tomtom_incident_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    delay_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    length_in_meters: Mapped[int] = mapped_column(Integer, nullable=True)
    from_address: Mapped[str] = mapped_column(String, nullable=True)
    to_address: Mapped[str] = mapped_column(String, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    