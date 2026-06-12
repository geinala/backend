
import time
from fastapi.responses import JSONResponse

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.lib.logging.logging import get_logger
from app.lib.response_formatter import ResponseFormatter
from app.services.job_service import enqueue_job
from app.workers.tuning_experiment.data_validation_worker import process_tuning_experiment_files
from app.workers.tuning_parameter_worker import calibrate_parameters
from app.workers.tuning_experiment.workflow_continue_worker import continue_tuning_experiment_workflow as continue_pre_processing_workflow

logger = get_logger(__name__)

class TuningExperimentController:
    async def tune_parameters(self, tuning_experiment_dataset_id: str) -> JSONResponse:
        start_time = time.time()
        wide_event: dict[str, object] = {
            "event_type": "preprocess_request",
            "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
            "status": "processing",
        }
        
        try:
            validate_file_job = enqueue_job(
                process_tuning_experiment_files,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.TUNING_EXPERIMENT_JOB_PROCESSING_DATA,
                tuning_experiment_dataset_id=tuning_experiment_dataset_id
            )
            
            logger.info(f"Enqueued file processing job {validate_file_job.id} for tuning experiment dataset {tuning_experiment_dataset_id}")
            
            enqueue_job(
                continue_pre_processing_workflow,
                job_type=JobType.LIGHT,
                job_prefix=JOB_PREFIXES_ENUM.TUNING_EXPERIMENT_JOB_CLEANING_DATA,
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
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
        
    async def calibrate_parameters(self) -> JSONResponse:
        start_time = time.time()
        wide_event: dict[str, object] = {
            "event_type": "calibrate_parameters_request",
            "status": "processing",
        }
        
        try:
            logger.info("Starting calibration of parameters based on the latest tuning experiments")
            
            job = enqueue_job(
                calibrate_parameters,
                job_type=JobType.TUNING,
                job_prefix=JOB_PREFIXES_ENUM.TUNING_EXPERIMENT_JOB_CALIBRATE_PARAMETERS,
            )
            
            logger.info(f"Enqueued calibration job for tuning experiments")
            
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return ResponseFormatter.success_with_data(
                data={"job_id": str(job.id)},
                message="Calibration job has been enqueued",
                status_code=200
            )
        
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e