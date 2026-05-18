import time
from rq.job import get_current_job

from app.lib.logging.logging import get_logger
from app.lib.db import get_db
from app.services.pre_processing.geocode_service import GeocodeService

logger = get_logger(__name__)

async def geocode_address(
    simulation_job_id: str,
    resolution_status: str = "auto_solved",
    geocoded_resolution_status: str = "auto_solved",
    advance_current_step: bool = False,
):
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_geocode_process",
        "job_id": job.id if job else None,
        "simulation_job_id": simulation_job_id,
        "status": "processing",
        "resolution_status": resolution_status,
        "geocoded_resolution_status": geocoded_resolution_status,
        "advance_current_step": advance_current_step,
    }
    
    try:
        from app.services.tomtom_service import TomTomService
        from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
        from app.repositories.simulation_job_repository import SimulationJobRepository
        
        db_session = get_db()
        db = next(db_session)
        geocode_service = GeocodeService(
            tomtom_service=TomTomService(),
            simulation_uploaded_row_repository=SimulationUploadedRowRepository(db),
            simulation_job_repository=SimulationJobRepository(db)
        )
        
        result = await geocode_service.run(
            simulation_job_id=simulation_job_id,
            resolution_status=resolution_status,
            geocoded_resolution_status=geocoded_resolution_status,
            advance_current_step=advance_current_step,
        )
        
        wide_event["status"] = "success"
        wide_event["processed_rows"] = len(result) if result else 0
        wide_event["duration_ms"] = (time.time() - start_time) * 1000

        logger.info(wide_event)

        return {"status": "success", "simulation_job_id": simulation_job_id}
    except Exception as e:
        raise e
    
    