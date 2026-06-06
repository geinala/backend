import enum
import uuid
from typing import TYPE_CHECKING

from app.lib.db import Base
from sqlalchemy import Integer, String, ForeignKey, DateTime, Float, func, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

if TYPE_CHECKING:
    from app.models.optimization_run import OptimizationRun
    from app.models.route_leg_congestion_check import RouteLegCongestionCheck

class ReoptimizationOutcomeEnum(enum.Enum):
    resequence_applied = "resequencing_applied"
    duration_updated = "duration_updated"
    no_improvement = "no_improvement"

class ReoptimizationEvent(Base):
    __tablename__ = 'reoptimization_events'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    optimization_run_id: Mapped[int] = mapped_column(Integer, ForeignKey('optimization_runs.id'), nullable=False)
    congestion_check_id: Mapped[int] = mapped_column(Integer, ForeignKey('route_leg_congestion_checks.id'), nullable=True)  # Link ke congestion check yang memicu reoptimasi ini, jika ada
    reopt_sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # Urutan reoptimasi yang terjadi pada route ini (1 untuk reopt pertama, 2 untuk reopt kedua, dst.)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # Kapan reoptimasi ini dipicu
    before_route_id: Mapped[int] = mapped_column(Integer, ForeignKey('courier_routes.id'), nullable=True)  # Route sebelum reoptimasi
    before_total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    before_total_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    after_route_id: Mapped[int] = mapped_column(Integer, ForeignKey('courier_routes.id'), nullable=True)  # Route setelah reoptimasi
    after_total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    after_total_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_saved_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)  # Jarak yang berhasil dihemat dari reoptimasi ini
    time_saved_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)  # Waktu yang berhasil dihemat dari reoptimasi ini
    courier_position: Mapped[str] = mapped_column(String, nullable=False)  # Posisi kurir saat reoptimasi dipicu, format JSON array: [{"courier_id": number, "lat": number, "lng": number, "bearing": number}]
    algorithm_used: Mapped[str] = mapped_column(String, nullable=True)  # Algoritma yang digunakan untuk reoptimasi ini
    computation_time_in_ms: Mapped[float] = mapped_column(Float, nullable=False)  # Waktu yang dibutuhkan untuk melakukan reoptimasi ini
    total_incident_delay_in_seconds: Mapped[int] = mapped_column(Integer, nullable=True)  # Total delay yang disebabkan oleh insiden yang memicu reoptimasi ini, jika ada
    outcome: Mapped[str] = mapped_column(String, nullable=True)  # Hasil dari reoptimasi ini, misalnya "resequence", "duration_updated", "failed", dll.
    trigger_route_leg_id: Mapped[int] = mapped_column(Integer, ForeignKey('route_legs.id'), nullable=True)  # Route leg yang memicu reoptimasi ini, jika ada
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    optimization_run: Mapped["OptimizationRun"] = relationship("OptimizationRun")
    congestion_check: Mapped["RouteLegCongestionCheck | None"] = relationship("RouteLegCongestionCheck")
