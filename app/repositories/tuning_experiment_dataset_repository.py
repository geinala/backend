from sqlalchemy.orm import Session

from app.models.tuning_experiment_dataset import TuningExperimentDataset, TuningExperimentDatasetStatusEnum

class TuningExperimentDatasetRepository:
    def __init__(self, db: Session): 
        self.db = db
        
    async def get_tuning_experiment_dataset_by_id(self, tuning_experiment_dataset_id: str) -> TuningExperimentDataset | None:
        return self.db.query(TuningExperimentDataset).filter(TuningExperimentDataset.id == tuning_experiment_dataset_id).first()
    
    async def get_tuning_experiment_dataset_by_id_and_status(self, tuning_experiment_dataset_id: str, status: TuningExperimentDatasetStatusEnum) -> TuningExperimentDataset | None:
        return self.db.query(TuningExperimentDataset).filter(
            TuningExperimentDataset.id == tuning_experiment_dataset_id,
            TuningExperimentDataset.status == status
        ).first()
        
    async def update_tuning_experiment_dataset_status(self, tuning_experiment_dataset_id: str, new_status: TuningExperimentDatasetStatusEnum) -> TuningExperimentDataset | None:
        dataset = self.db.query(TuningExperimentDataset).filter(TuningExperimentDataset.id == tuning_experiment_dataset_id).first()
        if dataset:
            dataset.status = new_status
            self.db.commit()
            self.db.refresh(dataset)
        return dataset