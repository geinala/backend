import time
from rq.job import get_current_job

from app.lib.logging.logging import get_logger
from app.lib.db import get_db

logger = get_logger(__name__)

async def validate_dataset(simulation_id: str):
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_validate_dataset",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "status": "processing",
    }
    
    try:
        from app.services.simulation_service import SimulationService
        from app.services.minio_service import MinioService
        from app.repositories.simulation_repository import SimulationRepository
        from app.lib.minio import minioClient
        
        db_session = get_db()
        simulation_repository = SimulationRepository(next(db_session))
        minio_service = MinioService(minio_client=minioClient)
        simulation_service = SimulationService(minio_service, simulation_repository)
        
        await simulation_service.validate_dataset(simulation_id)
        
        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(wide_event)
        
        return {"status": "success", "simulation_id": simulation_id}
        
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.error(wide_event)
        raise e