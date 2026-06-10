import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DailyOptimizationLogBase(BaseModel):
    config_id: uuid.UUID
    date: datetime
    total_nodes: int
    total_couriers: int
    execution_time_ms: float
    total_fitness_score: float
    improvement_percentage: float


class DailyOptimizationLogCreate(DailyOptimizationLogBase):
    pass


class DailyOptimizationLogUpdate(BaseModel):
    config_id: Optional[uuid.UUID] = None
    date: Optional[datetime] = None
    total_nodes: Optional[int] = None
    total_couriers: Optional[int] = None
    execution_time_ms: Optional[float] = None
    total_fitness_score: Optional[float] = None
    improvement_percentage: Optional[float] = None


class DailyOptimizationLogSchema(DailyOptimizationLogBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)