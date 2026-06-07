from rq import get_current_job
import time

from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.models.simulation import SimulationStatusEnum
from app.repositories.matrix_repository import MatrixRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.services.matrix_service import MatrixService
from app.services.tomtom_service import TomTomService

logger = get_logger(__name__)

async def generate_matrices(simulation_id: str, start_pair_index: int = 0):
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_generate_matrices",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "status": "processing",
    }
    
    try:
        db_session = get_db()
        db = next(db_session)
        simulation_repository = SimulationRepository(db)
        matrix_service = MatrixService(
            tomtom_service=TomTomService(), 
            matrix_repository=MatrixRepository(db), 
            node_repository=NodeRepository(db),
            simulation_repository=simulation_repository)

        wide_event["stage"] = "submitting_matrix_requests"
        
        await matrix_service.submit_tomtom_matrix_requests(simulation_id, start_pair_index=start_pair_index)
        
        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(wide_event)
        
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.error(wide_event)
        
        try:
            db = next(get_db())
            await SimulationRepository(db=db).update_simulation_status(
                simulation_id, SimulationStatusEnum.failed
            )
        except Exception:
            logger.error(f"Failed to update simulation {simulation_id} status to failed")
        
        raise e
    
async def get_matrix_results(simulation_id: str):
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_get_matrix_results",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "status": "processing",
    }
    
    try:
        db_session = get_db()
        db = next(db_session)
        simulation_repository = SimulationRepository(db)
        matrix_service = MatrixService(
            tomtom_service=TomTomService(), 
            matrix_repository=MatrixRepository(db), 
            node_repository=NodeRepository(db),
            simulation_repository=simulation_repository)

        wide_event["stage"] = "getting_matrix_results"
        
        await matrix_service.get_matrix_results(simulation_id)

        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.info(wide_event)
        
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.error(wide_event)
        
        try:
            db = next(get_db())
            await SimulationRepository(db).update_simulation_status(
                simulation_id, SimulationStatusEnum.failed
            )
        except Exception:
            logger.error(f"Failed to update simulation {simulation_id} status to failed")
        
        raise e
    
async def check_pending_batches(simulation_id: str):
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_check_pending_batches",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "status": "processing",
    }
    
    try:
        db_session = get_db()
        db = next(db_session)
        matrix_service = MatrixService(
            tomtom_service=TomTomService(), 
            matrix_repository=MatrixRepository(db), 
            node_repository=NodeRepository(db),
            simulation_repository=SimulationRepository(db)
        )

        wide_event["stage"] = "checking_pending_batches"
        
        has_pending_batches = await matrix_service.has_pending_batches(simulation_id)

        wide_event["status"] = "success"
        wide_event["has_pending_batches"] = has_pending_batches
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.info(wide_event)
        
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.error(wide_event)
        raise e