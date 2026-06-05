import asyncio
import time

from rq import get_current_job

from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.repositories.courier_route_repository import CourierRouteRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.repositories.route_repository import RouteRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.matrix_repository import MatrixRepository
from app.repositories.solution_repository import SolutionRepository
from app.services.dvrp_reoptimization_service import DVRPReoptimizationService
from app.services.matrix_service import MatrixService
from app.services.tomtom_service import TomTomService

logger = get_logger(__name__)


async def _process_congestion_reoptimization(
    simulation_id: str,
    route_leg_id: int,
    courier_route_id: int,
    courier_id: int,
    current_sequence: int,
    delay_seconds: int,
    traffic_incident_id: int | None = None,
    congestion_check_id: int | None = None,
    force_duration_update_only: bool = False,
):
    job = get_current_job()
    start_time = time.time()

    wide_event: dict[str, object] = {
        "event_type": "worker_dvrp_reoptimization",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "courier_route_id": courier_route_id,
        "status": "processing",
    }

    db_session = get_db()
    db = next(db_session)

    try:
        service = DVRPReoptimizationService(
            route_repository=RouteRepository(db),
            node_repository=NodeRepository(db),
            simulation_repository=SimulationRepository(db),
            matrix_service=MatrixService(
                matrix_repository=MatrixRepository(db),
                node_repository=NodeRepository(db),
                tomtom_service=TomTomService(),
                simulation_repository=SimulationRepository(db),
            ),
            tomtom_service=TomTomService(),
            optimization_run_repository=OptimizationRunRepository(db),
            courier_route_repository=CourierRouteRepository(db),
            solution_repository=SolutionRepository(db),
        )

        wide_event["stage"] = "reoptimizing"
        result = await service.handle_congestion(
            simulation_id=simulation_id,
            congestion_check_id=congestion_check_id,
            route_leg_id=route_leg_id,
            courier_route_id=courier_route_id,
            courier_id=courier_id,
            current_sequence=current_sequence,
            delay_seconds=delay_seconds,
            traffic_incident_id=traffic_incident_id,
            force_duration_update_only=force_duration_update_only,
        )

        db.commit()
        wide_event["status"] = "success"
        wide_event["outcome"] = result.get("outcome")
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.info(wide_event)

        return result
    except Exception as exc:
        db.rollback()
        wide_event["status"] = "failed"
        wide_event["error"] = str(exc)
        wide_event["error_type"] = type(exc).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(wide_event)
        raise
    finally:
        db.close()


def process_congestion_reoptimization(
    simulation_id: str,
    route_leg_id: int,
    courier_route_id: int,
    courier_id: int,
    current_sequence: int,
    delay_seconds: int,
    traffic_incident_id: int | None = None,
    congestion_check_id: int | None = None,
    force_duration_update_only: bool = False,
):
    return asyncio.run(
        _process_congestion_reoptimization(
            simulation_id=simulation_id,
            route_leg_id=route_leg_id,
            courier_route_id=courier_route_id,
            courier_id=courier_id,
            current_sequence=current_sequence,
            delay_seconds=delay_seconds,
            traffic_incident_id=traffic_incident_id,
            congestion_check_id=congestion_check_id,
            force_duration_update_only=force_duration_update_only,
        )
    )
