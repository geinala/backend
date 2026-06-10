import uuid
from datetime import datetime

from sqlalchemy import Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class DailyOptimizationLog(Base):
    __tablename__ = "daily_optimization_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_nodes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_couriers: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_time_ms: Mapped[float] = mapped_column(Integer, nullable=False)
    total_fitness_score: Mapped[float] = mapped_column(Integer, nullable=False)
    improvement_percentage: Mapped[float] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
