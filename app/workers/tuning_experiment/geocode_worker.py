import time
from rq.job import get_current_job

from app.lib.logging.logging import get_logger
from app.lib.db import get_db
from app.services.tuning_experiment.geocode_service import TuningExperimentGeocodeService

logger = get_logger(__name__)

async def geocode_tuning_experiment_address(
    tuning_experiment_id: str,
):
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_geocode_process",
        "job_id": job.id if job else None,
        "tuning_experiment_id": tuning_experiment_id,
        "status": "processing",
    }
    
    try:
        from app.services.tomtom_service import TomTomService
        from app.repositories.tuning_experiment_uploaded_row_repository import TuningExperimentUploadedRowRepository
        from app.repositories.tuning_experiment_repository import TuningExperimentRepository
        
        db_session = get_db()
        db = next(db_session)
        geocode_service = TuningExperimentGeocodeService(
            tomtom_service=TomTomService(),
            tuning_experiment_uploaded_row_repository=TuningExperimentUploadedRowRepository(db),
            tuning_experiment_repository=TuningExperimentRepository(db)
        )
        
        result = await geocode_service.run(
            tuning_experiment_id=tuning_experiment_id
        )
        
        wide_event["status"] = "success"
        wide_event["processed_rows"] = len(result) if result else 0
        wide_event["duration_ms"] = (time.time() - start_time) * 1000

        logger.info(wide_event)

        return {"status": "success", "tuning_experiment_id": tuning_experiment_id}
    except Exception as e:
        raise e
    
    