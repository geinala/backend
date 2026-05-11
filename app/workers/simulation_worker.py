import time
from rq.job import get_current_job

from app.lib.logging.logging import get_logger
from app.lib.db import get_db

logger = get_logger(__name__)

async def process_files(simulation_job_id: str):
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_process_files",
        "job_id": job.id if job else None,
        "simulation_job_id": simulation_job_id,
        "status": "processing",
    }
    
    try:
        from app.services.simulation_service import SimulationService
        from app.services.minio_service import MinioService
        from app.repositories.simulation_job_repository import SimulationJobRepository
        from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
        from app.repositories.node_repository import NodeRepository
        from app.lib.minio import minio_client
        
        db_session = get_db()
        db = next(db_session)
        simulation_job_repository = SimulationJobRepository(db)
        node_repository = NodeRepository(db)
        minio_service = MinioService(minio_client=minio_client)
        simulation_service = SimulationService(
            minio_service=minio_service,
            simulation_job_repository=simulation_job_repository,
            simulation_uploaded_row_repository=SimulationUploadedRowRepository(db),
            node_repository=node_repository
        )
        
        await simulation_service.process_files(simulation_job_id=simulation_job_id)
        
        wide_event["status"] = "success"
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
        from app.services.simulation_service import SimulationService
        from app.services.minio_service import MinioService
        from app.repositories.simulation_job_repository import SimulationJobRepository
        from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
        from app.repositories.node_repository import NodeRepository
        from app.lib.minio import minio_client

        db_session = get_db()
        db = next(db_session)
        simulation_job_repository = SimulationJobRepository(db)
        node_repository = NodeRepository(db)
        minio_service = MinioService(minio_client=minio_client)
        simulation_service = SimulationService(
            minio_service=minio_service,
            simulation_job_repository=simulation_job_repository,
            simulation_uploaded_row_repository=SimulationUploadedRowRepository(db),
            node_repository=node_repository
        )

        result = await simulation_service.clean_uploaded_rows(simulation_job_id=simulation_job_id)

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
