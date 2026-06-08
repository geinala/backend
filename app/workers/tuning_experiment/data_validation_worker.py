import time
from rq.job import get_current_job

from app.lib.logging.logging import get_logger
from app.lib.db import get_db
from app.repositories.tuning_experiment_dataset_repository import TuningExperimentDatasetRepository

logger = get_logger(__name__)

async def process_tuning_experiment_files(tuning_experiment_dataset_id: str) -> dict[str, object]:
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_process_files",
        "job_id": job.id if job else None,
        "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
        "status": "processing",
    }
    
    try:
        from app.services.tuning_experiment.data_validation_service import TuningExperimentDataValidationService
        from app.services.minio_service import MinioService
        from app.repositories.tuning_experiment_repository import TuningExperimentRepository
        from app.repositories.tuning_experiment_uploaded_row_repository import TuningExperimentUploadedRowRepository
        from app.lib.minio import minio_client
        
        db_session = get_db()
        db = next(db_session)
        data_validation_service = TuningExperimentDataValidationService(
            minio_service=MinioService(minio_client=minio_client),
            tuning_experiment_repository=TuningExperimentRepository(db),
            tuning_experiment_uploaded_row_repository=TuningExperimentUploadedRowRepository(db),
            tuning_experiment_dataset_repository=TuningExperimentDatasetRepository(db)
        )
        
        await data_validation_service.run(tuning_experiment_dataset_id=tuning_experiment_dataset_id)
        
        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(wide_event)
        
        return {"status": "success", "tuning_experiment_dataset_id": tuning_experiment_dataset_id}
        
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.error(wide_event)
        raise e