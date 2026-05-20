import time

from rq import get_current_job

from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.repositories.courier_repository import CourierRepository
from app.services.pre_optimization.pre_optimization_service import PreOptimizationService

logger = get_logger(__name__)


async def map_couriers(simulation_id: str):
    job = get_current_job()
    start_time = time.time()

    wide_event: dict[str, object] = {
        "event_type": "worker_map_couriers",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "status": "processing",
    }

    try:
        db_session = get_db()
        db = next(db_session)
        pre_optimization_service = PreOptimizationService(
            simulation_job_repository=SimulationJobRepository(db),
            simulation_uploaded_row_repository=SimulationUploadedRowRepository(db),
            courier_repository=CourierRepository(db),
            node_repository=NodeRepository(db),
        )

        wide_event["stage"] = "mapping_couriers"
        result = await pre_optimization_service.map_couriers_to_vehicles(simulation_id)

        wide_event["status"] = "success"
        wide_event["mapped_vehicles"] = result.get("mapped_vehicles")
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