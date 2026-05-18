
import time
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.lib.logging.logging import get_logger
from app.lib.response_formatter import ResponseFormatter
from app.services.job_service import enqueue_job
from app.workers.pre_processing.data_validation_worker import process_files as process_simulation_files
from app.workers.pre_processing.geocode_worker import geocode_address as process_geocoding
from app.workers.pre_processing.workflow_continue_worker import continue_workflow as continue_pre_processing_workflow

logger = get_logger(__name__)

class SimulationJobController:
    def __init__(self, db: Session):
        self.db = db
        
    async def preprocess_simulation_job(self, simulation_job_id: str) -> JSONResponse:
        start_time = time.time()
        wide_event: dict[str, object] = {
            "event_type": "preprocess_request",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }
        
        try:
            # Enqueue file validation and processing job with a unique job prefix for better traceability in logs and monitoring
            validate_file_job = enqueue_job(
                process_simulation_files,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.SIMULATION_JOB_PROCESSING_DATA,
                simulation_job_id=simulation_job_id
            )
            
            logger.info(f"Enqueued file processing job {validate_file_job.id} for simulation {simulation_job_id}")
            
            # Enqueue cleaning data job that depends on the completion of the file validation job, ensuring proper sequencing of tasks
            enqueue_job(
                continue_pre_processing_workflow,
                job_type=JobType.LIGHT,
                job_prefix=JOB_PREFIXES_ENUM.SIMULATION_JOB_CLEANING_DATA,
                simulation_job_id=simulation_job_id,
                depends_on=validate_file_job
            )
                
            wide_event["status"] = "success"
            wide_event["job_id"] = validate_file_job.id
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return ResponseFormatter.success_with_data(
                data={"job_id": str(validate_file_job.id)},
                message="File processing has been enqueued for processing",
                status_code=200
            )
        
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e

    async def revalidate_simulation_job(self, simulation_job_id: str) -> JSONResponse:
        start_time = time.time()
        wide_event: dict[str, object] = {
            "event_type": "revalidate_request",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }

        try:
            job = enqueue_job(
                process_geocoding,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.SIMULATION_JOB_REVALIDATION,
                simulation_job_id=simulation_job_id,
                resolution_status="manual_override",
                geocoded_resolution_status="manual_override",
                advance_current_step=True,
            )

            logger.info(f"Enqueued revalidation job {job.id} for simulation {simulation_job_id}")

            wide_event["status"] = "success"
            wide_event["job_id"] = job.id
            wide_event["duration_ms"] = (time.time() - start_time) * 1000

            logger.info(wide_event)

            return ResponseFormatter.success_with_data(
                data={"job_id": str(job.id)},
                message="Revalidation has been enqueued for processing",
                status_code=200,
            )

        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000

            logger.error(wide_event)
            raise e