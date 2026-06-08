

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.lib.logging.logging import get_logger
from app.repositories.tuning_experiment_repository import TuningExperimentRepository
from app.services.job_service import enqueue_job
from app.workers.tuning_experiment.data_cleaning_worker import clean_tuning_experiment_uploaded_rows as process_tuning_experiment_cleaning
from app.workers.tuning_experiment.geocode_worker import geocode_tuning_experiment_address as process_geocoding

logger = get_logger(__name__)

class TuningExperimentPreProcessingWorkflowService:
    def __init__(
        self,
        tuning_experiment_repository: TuningExperimentRepository,
    ):
        self.tuning_experiment_repository = tuning_experiment_repository

    async def continue_workflow_after_file_validation(self, tuning_experiment_id: str):
        try:
            tuning_experiment = await self.tuning_experiment_repository.get_tuning_experiment_by_id(tuning_experiment_id)

            if not tuning_experiment:
                return

            cleaning_job = enqueue_job(
                process_tuning_experiment_cleaning,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.TUNING_EXPERIMENT_JOB_CLEANING_DATA,
                tuning_experiment_id=tuning_experiment_id,
            )
            
            logger.info(f"Enqueued cleaning data job {cleaning_job.id} for tuning experiment {tuning_experiment_id} after file validation completion")
            
            geocoding_job = enqueue_job(
                process_geocoding,
                job_type=JobType.LIGHT,
                job_prefix=JOB_PREFIXES_ENUM.TUNING_EXPERIMENT_JOB_GEOCODING,
                tuning_experiment_id=tuning_experiment_id,
                depends_on=cleaning_job,
                advance_current_step=True,
            )
            
            logger.info(f"Enqueued geocoding job {geocoding_job.id} for tuning experiment {tuning_experiment_id} after cleaning completion")
        except Exception as e:
            raise e
    