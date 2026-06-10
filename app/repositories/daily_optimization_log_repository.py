from sqlalchemy.orm import Session

from app.models.daily_optimization_log import DailyOptimizationLog
from app.schemas.daily_optimization_log_schema import (
    DailyOptimizationLogCreate,
)

class DailyOptimizationLogRepository:
    def __init__(self, db: Session):
        self.db = db

    async def create_daily_optimization_log(
        self,
        data: DailyOptimizationLogCreate,
    ) -> DailyOptimizationLog:
        log = DailyOptimizationLog(
            **data.model_dump()
        )

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        return log
