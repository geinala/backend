from sqlalchemy.orm import Session

from app.models.tuning_experiment import TuningExperiment
from app.schemas.tuning_experiment_schema import TuningExperimentUpdateSchema

class TuningExperimentRepository:
    def __init__(self, db: Session): 
        self.db = db
        
    async def get_tuning_experiment_by_id(self, tuning_experiment_id: str):
        return self.db.query(TuningExperiment).filter(TuningExperiment.id == tuning_experiment_id).first()
        
    async def update_tuning_experiment(self, tuning_experiment_id: str, update_data: TuningExperimentUpdateSchema) -> TuningExperiment | None:
        try:
            tuning_experiment = self.db.query(TuningExperiment).filter(TuningExperiment.id == tuning_experiment_id).first()

            if not tuning_experiment:
                return None

            for key, value in update_data.model_dump(exclude_unset=True).items():
                setattr(tuning_experiment, key, value)

            self.db.commit()
            self.db.refresh(tuning_experiment)
            return tuning_experiment
        except Exception:
            self.db.rollback()
            raise
        
    async def create_tuning_experiment(self, tuning_experiment: TuningExperiment) -> TuningExperiment:
        try:
            self.db.add(tuning_experiment)
            self.db.commit()
            self.db.refresh(tuning_experiment)
            return tuning_experiment
        except Exception:
            self.db.rollback()
            raise