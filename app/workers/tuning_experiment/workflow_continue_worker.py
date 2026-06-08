
from app.lib.db import get_db
from app.repositories.tuning_experiment_dataset_repository import TuningExperimentDatasetRepository
from app.services.tuning_experiment.pre_processing_workflow_service import TuningExperimentPreProcessingWorkflowService


async def continue_tuning_experiment_workflow(tuning_experiment_dataset_id: str):
    try:
        db_session = get_db()
        db = next(db_session)
        pre_processing_workflow_service = TuningExperimentPreProcessingWorkflowService(
            tuning_experiment_dataset_repository=TuningExperimentDatasetRepository(db)
        )
        
        await pre_processing_workflow_service.continue_workflow_after_file_validation(tuning_experiment_dataset_id=tuning_experiment_dataset_id)
    except Exception as e:
        raise e