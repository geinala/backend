from typing import TYPE_CHECKING

from app.lib.db import Base
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

if TYPE_CHECKING:
    from app.models.route_leg_congestion_check import RouteLegCongestionCheck
    from app.models.traffic_incident import TrafficIncident


class RouteLegCongestionCheckIncident(Base):
    __tablename__ = "route_leg_congestion_check_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    congestion_check_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_leg_congestion_checks.id"),
        nullable=False,
        index=True,
    )
    traffic_incident_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("traffic_incidents.id"),
        nullable=True,
        index=True,
    )
    delay_in_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overlap_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejected_reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)  # JSON array of reasons why this incident was rejected, e.g. ["not_in_bbox", "direction_mismatch", "insufficient_overlap", etc.]
    route_intersects: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # Apakah rute leg ini berpotongan dengan area insiden
    is_valid_congestion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    direction_matches: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    route_point_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incident_point_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cluster_group: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chosen_for_reopt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delay_contribution_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Perkiraan berapa banyak delay yang disebabkan oleh insiden ini untuk rute leg ini, berdasarkan overlap dan severity insiden
    delay_threshold_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)  # Threshold untuk menentukan apakah delay dari insiden ini cukup signifikan untuk memicu re-optimisasi
    overlap_threshold: Mapped[float] = mapped_column(Float, nullable=False)  # Threshold untuk menentukan apakah overlap antara rute dan insiden cukup signifikan untuk memicu re-optimisasi
    proximity_threshold_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)  # Threshold untuk menentukan apakah jarak antara rute dan insiden cukup dekat untuk memicu
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    congestion_check: Mapped["RouteLegCongestionCheck"] = relationship(
        "RouteLegCongestionCheck",
        back_populates="incidents",
    )
    traffic_incident: Mapped["TrafficIncident | None"] = relationship("TrafficIncident")
