import time
from rq.job import get_current_job

from app.lib.logging.logging import get_logger
from app.lib.db import get_db

logger = get_logger(__name__)

async def clean_uploaded_rows(simulation_job_id: str):
    job = get_current_job()
    start_time = time.time()

    wide_event: dict[str, object] = {
        "event_type": "worker_clean_uploaded_rows",
        "job_id": job.id if job else None,
        "simulation_job_id": simulation_job_id,
        "status": "processing",
    }

    try:
        from app.repositories.simulation_job_repository import SimulationJobRepository
        from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
        from app.services.pre_processing.data_cleaning_service import DataCleaningService
        
        db_session = get_db()
        db = next(db_session)
        simulation_job_repository = SimulationJobRepository(db)
        simulation_uploaded_row_repository = SimulationUploadedRowRepository(db)
        data_cleaning_service = DataCleaningService(
            simulation_job_repository=simulation_job_repository,
            simulation_uploaded_row_repository=simulation_uploaded_row_repository
        )

        result = await data_cleaning_service.run(simulation_job_id=simulation_job_id)

        wide_event["status"] = "success"
        wide_event["processed_rows"] = result["processed_rows"]
        wide_event["duration_ms"] = (time.time() - start_time) * 1000

        logger.info(wide_event)

        return {"status": "success", "simulation_job_id": simulation_job_id}

    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000

        logger.error(wide_event)
        raise e
