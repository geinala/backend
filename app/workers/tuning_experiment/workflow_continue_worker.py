
from app.lib.db import get_db
from app.services.tuning_experiment.pre_processing_workflow_service import TuningExperimentPreProcessingWorkflowService
from app.repositories.tuning_experiment_repository import TuningExperimentRepository


async def continue_tuning_experiment_workflow(tuning_experiment_id: str):
    try:
        db_session = get_db()
        db = next(db_session)
        pre_processing_workflow_service = TuningExperimentPreProcessingWorkflowService(
            tuning_experiment_repository=TuningExperimentRepository(db)
        )
        
        await pre_processing_workflow_service.continue_workflow_after_file_validation(tuning_experiment_id=tuning_experiment_id)
    except Exception as e:
        raise e