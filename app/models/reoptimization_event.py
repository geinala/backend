import enum
import uuid

from app.lib.db import Base
from sqlalchemy import Integer, String, ForeignKey, DateTime, Float, func, UUID
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class ReoptimizationOutcomeEnum(enum.Enum):
    resequence = "resequence"
    duration_updated = "duration_updated"

class ReoptimizationEvent(Base):
    __tablename__ = 'reoptimization_events'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    courier_route_id: Mapped[int] = mapped_column(Integer, ForeignKey('courier_routes.id'), nullable=False)
    traffic_incident_id: Mapped[int] = mapped_column(Integer, ForeignKey('traffic_incidents.id'), nullable=True)
    reopt_sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # Urutan reoptimasi yang terjadi pada route ini (1 untuk reopt pertama, 2 untuk reopt kedua, dst.)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # Kapan reoptimasi ini dipicu
    before_route_id: Mapped[int] = mapped_column(Integer, ForeignKey('courier_routes.id'), nullable=True)  # Route sebelum reoptimasi
    before_total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    before_total_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    after_route_id: Mapped[int] = mapped_column(Integer, ForeignKey('courier_routes.id'), nullable=True)  # Route setelah reoptimasi
    after_total_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    after_total_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    improvement_in_distance_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)  # Selisih jarak (m): before - after. Positif = re-opt berhasil mempersingkat rute.
    improvement_in_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)  # Selisih waktu (s): before - after. Positif = re-opt berhasil menghemat waktu.
    courier_position: Mapped[str] = mapped_column(String, nullable=False)  # Posisi kurir saat reoptimasi dipicu, format: { latitude: number, longitude: number }
    distance_saved_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)  # Jarak yang berhasil dihemat dari reoptimasi ini
    time_saved_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)  # Waktu yang berhasil dihemat dari reoptimasi ini
    algorithm_used: Mapped[str] = mapped_column(String, nullable=False)  # Algoritma yang digunakan untuk reoptimasi ini
    computation_time_in_ms: Mapped[float] = mapped_column(Float, nullable=False)  # Waktu yang dibutuhkan untuk melakukan reoptimasi ini
    incident_category: Mapped[int] = mapped_column(Integer, nullable=True)  # Kategori insiden yang memicu reoptimasi ini, jika ada
    incident_delay_in_seconds: Mapped[int] = mapped_column(Integer, nullable=True)  # Perkiraan delay yang disebabkan oleh insiden yang memicu reoptimasi ini, jika ada
    incident_details: Mapped[str] = mapped_column(String, nullable=True)  # Detail insiden yang memicu reoptimasi ini, jika ada
    incident_description: Mapped[str] = mapped_column(String, nullable=True)  # Deskripsi insiden yang memicu reoptimasi ini, jika ada
    outcome: Mapped[str] = mapped_column(String, nullable=True)  # Hasil dari reoptimasi ini, misalnya "resequence", "duration_updated", "failed", dll.
    trigger_route_leg_id: Mapped[int] = mapped_column(Integer, ForeignKey('route_legs.id'), nullable=True)  # Route leg yang memicu reoptimasi ini, jika ada
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
