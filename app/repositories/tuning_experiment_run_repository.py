from typing import List

from sqlalchemy.orm import Session

from app.models.tuning_experiment_run import TuningExperimentRun
from app.schemas.tuning_experiment_run_schema import TuningExperimentRunCreateSchema

class TuningExperimentRunRepository:
    def __init__(self, db: Session): 
        self.db = db
        
    async def bulk_create_tuning_experiment_runs(self, tuning_experiment_runs: List[TuningExperimentRunCreateSchema]):
        db_tuning_experiment_runs = [
            TuningExperimentRun(**tuning_experiment_run.model_dump()) for tuning_experiment_run in tuning_experiment_runs
        ]
        self.db.bulk_save_objects(db_tuning_experiment_runs)
        self.db.commit()