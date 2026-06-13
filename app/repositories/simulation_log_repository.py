from sqlalchemy.orm import Session

from app.models.simulation_log import SimulationLog
from app.schemas.simulation_log_schema import SimulationLogCreate


class SimulationLogRepository:
    def __init__(self, db: Session):
        self.db = db

    async def create_log(self, log_data: SimulationLogCreate) -> SimulationLog:
        try:
            log_obj = SimulationLog(
                **log_data.model_dump(exclude_none=True)
            )

            self.db.add(log_obj)
            self.db.commit()
            self.db.refresh(log_obj)

            return log_obj

        except Exception:
            self.db.rollback()
            raise
