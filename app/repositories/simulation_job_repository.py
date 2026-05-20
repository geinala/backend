from sqlalchemy.orm import Session

from app.models.simulation_job import SimulationJob
from app.schemas.simulation_job_schema import SimulationJobUpdateData

class SimulationJobRepository:
    def __init__(self, db: Session): 
        self.db = db
        
    async def get_simulation_job_by_id(self, simulation_job_id: str):
        return self.db.query(SimulationJob).filter(SimulationJob.id == simulation_job_id).first()
        
    async def update_simulation_job(self, simulation_job_id: str, update_data: SimulationJobUpdateData):
        try:
            simulation_job = self.db.query(SimulationJob).filter(SimulationJob.id == simulation_job_id).first()

            if not simulation_job:
                return None

            for key, value in update_data.model_dump(exclude_unset=True).items():
                setattr(simulation_job, key, value)

            self.db.commit()
            self.db.refresh(simulation_job)
            return simulation_job
        except Exception:
            self.db.rollback()
            raise
        