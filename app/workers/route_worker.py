import time
from rq import get_current_job

from app.lib.db import get_db
from app.services.route_service import RouteService
from app.services.tomtom_service import TomTomService
from app.repositories.solution_repository import SolutionRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.repositories.route_repository import RouteRepository
from app.lib.logging.logging import get_logger

logger = get_logger()

async def generate_routes(simulation_id: str, depart_at: str | None = None):
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_generate_routes",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "status": "processing",
    }
    
    try:
        db_session = get_db()
        db = next(db_session)
        route_service = RouteService(
            tomtom_service=TomTomService(), 
            solution_repository=SolutionRepository(db), 
            node_repository=NodeRepository(db),
            vehicle_repository=VehicleRepository(db),
            route_repository=RouteRepository(db))

        wide_event["stage"] = "generating_routes"
        
        await route_service.generate_routes(simulation_id, depart_at)
        
        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.info(wide_event)
        
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(wide_event)