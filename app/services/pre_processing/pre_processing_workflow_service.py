

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.lib.logging.logging import get_logger
from app.models.simulation_job import SimulationJobFileValidationStatusEnum
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.services.job_service import enqueue_job
from app.workers.pre_processing.data_cleaning_worker import clean_uploaded_rows as process_simulation_cleaning
from app.workers.pre_processing.geocode_worker import geocode_address as process_geocoding

logger = get_logger(__name__)

class PreProcessingWorkflowService:
    def __init__(
        self,
        simulation_job_repository: SimulationJobRepository,
        ):
        self.simulation_job_repository = simulation_job_repository
    
    async def continue_workflow_after_file_validation(self, simulation_job_id: str):
        try:
            simulation_job = await self.simulation_job_repository.get_simulation_job_by_id(simulation_job_id)
            
            if not simulation_job:
                return
            
            if simulation_job.file_validation_status != SimulationJobFileValidationStatusEnum.completed:
                return
            
            cleaning_job = enqueue_job(
                process_simulation_cleaning,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.SIMULATION_JOB_CLEANING_DATA,
                simulation_job_id=simulation_job_id,
            )
            
            logger.info(f"Enqueued cleaning data job {cleaning_job.id} for simulation {simulation_job_id} after file validation completion")
            
            geocoding_job = enqueue_job(
                process_geocoding,
                job_type=JobType.LIGHT,
                job_prefix=JOB_PREFIXES_ENUM.SIMULATION_JOB_GEOCODING,
                simulation_job_id=simulation_job_id,                
                depends_on=cleaning_job,
                advance_current_step=True,
            )
            
            logger.info(f"Enqueued geocoding job {geocoding_job.id} for simulation {simulation_job_id} after cleaning completion")
        except Exception as e:
            raise e
    