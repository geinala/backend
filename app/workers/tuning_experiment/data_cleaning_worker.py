import time
from rq.job import get_current_job

from app.lib.logging.logging import get_logger
from app.lib.db import get_db

logger = get_logger(__name__)

async def clean_tuning_experiment_uploaded_rows(tuning_experiment_dataset_id: str):
    job = get_current_job()
    start_time = time.time()

    wide_event: dict[str, object] = {
        "event_type": "worker_clean_tuning_experiment_uploaded_rows",
        "job_id": job.id if job else None,
        "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
        "status": "processing",
    }

    try:
        from app.repositories.tuning_experiment_dataset_repository import TuningExperimentDatasetRepository
        from app.repositories.tuning_experiment_uploaded_row_repository import TuningExperimentUploadedRowRepository
        from app.services.tuning_experiment.data_cleaning_service import TuningExperimentDataCleaningService
        
        db_session = get_db()
        db = next(db_session)
        tuning_experiment_dataset_repository = TuningExperimentDatasetRepository(db)
        tuning_experiment_uploaded_row_repository = TuningExperimentUploadedRowRepository(db)
        data_cleaning_service = TuningExperimentDataCleaningService(
            tuning_experiment_dataset_repository=tuning_experiment_dataset_repository,
            tuning_experiment_uploaded_row_repository=tuning_experiment_uploaded_row_repository
        )

        result = await data_cleaning_service.run(tuning_experiment_dataset_id=tuning_experiment_dataset_id)

        wide_event["status"] = "success"
        wide_event["processed_rows"] = result["processed_rows"] if result else None
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
