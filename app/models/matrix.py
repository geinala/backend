from datetime import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class MatrixTypeEnum(enum.Enum):
    initial = "initial"
    reoptimized = "reoptimized"
    
class MatrixResult(Base):
    __tablename__ = 'matrix_results'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=True)
    courier_id: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_index: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_index: Mapped[int] = mapped_column(Integer, nullable=False)
    length_in_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    travel_time_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    matrix_type: Mapped[MatrixTypeEnum] = mapped_column(
        Enum(MatrixTypeEnum, name="matrix_type_enum"),
        nullable=False
    )
    matrix_stage: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)