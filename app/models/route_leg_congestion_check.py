from app.lib.db import Base
from sqlalchemy import Integer, String, ForeignKey, DateTime, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class RouteLegCongestionCheck(Base):
    __tablename__ = "route_leg_congestion_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    simulation_id: Mapped[str] = mapped_column(String, ForeignKey("simulations.id"), nullable=False)
    route_leg_id: Mapped[int] = mapped_column(Integer, ForeignKey("route_legs.id"), nullable=False)
    courier_id: Mapped[int] = mapped_column(Integer, ForeignKey("couriers.id"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    bbox_min_lng: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_min_lat: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_max_lng: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_max_lat: Mapped[float] = mapped_column(Float, nullable=False)

    incidents_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Jumlah insiden yang ditemukan dalam bounding box pada saat pengecekan
    accepted_incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Jika ada insiden yang ditemukan dan dianggap relevan, simpan ID-nya di sini

    match_details: Mapped[str | None] = mapped_column(String, nullable=True)  # Detail tentang bagaimana insiden yang ditemukan cocok dengan rute leg ini, termasuk alasan mengapa insiden tersebut dianggap relevan atau tidak relevan

