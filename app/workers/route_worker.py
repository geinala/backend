import time
from rq import get_current_job

from app.lib.db import get_db
from app.repositories.courier_route_repository import CourierRouteRepository
from app.repositories.matrix_repository import MatrixRepository
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.repositories.simulation_repository import SimulationRepository
from app.services.route_service import RouteService
from app.services.matrix_service import MatrixService
from app.services.tomtom_service import TomTomService
from app.repositories.solution_repository import SolutionRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.courier_repository import CourierRepository
from app.repositories.route_repository import RouteRepository
from app.lib.logging.logging import get_logger
from app.services.realtime_event_service import schedule_courier_arrival_events
from app.workers.events_worker import emit_route_initialized_event, emit_vehicle_departed_depot_event

logger = get_logger()

async def generate_routes(simulation_id: str):
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
            matrix_service=MatrixService(
                matrix_repository=MatrixRepository(db),
                node_repository=NodeRepository(db),
                tomtom_service=TomTomService(),
                simulation_repository=SimulationRepository(db),
            ),
            solution_repository=SolutionRepository(db), 
            node_repository=NodeRepository(db),
            courier_repository=CourierRepository(db),
            route_repository=RouteRepository(db),
            simulation_repository=SimulationRepository(db),
            courier_route_repository=CourierRouteRepository(db),
            optimization_run_repository=OptimizationRunRepository(db),
            )

        wide_event["stage"] = "generating_routes"
        
        arrival_schedules = await route_service.generate_routes(simulation_id)

        seen_courier_route_ids: set[int] = set()
        for arrival in arrival_schedules:
            courier_route_id = arrival["courier_route_id"]

            if courier_route_id in seen_courier_route_ids:
                continue

            seen_courier_route_ids.add(courier_route_id)
            emit_vehicle_departed_depot_event(
                simulation_id=arrival["simulation_id"],
                courier_route_id=courier_route_id,
                courier_id=arrival["courier_id"],
            )

        scheduled_count = schedule_courier_arrival_events(arrival_schedules)
        emit_route_initialized_event(simulation_id, scheduled_count)
        
        wide_event["status"] = "success"
        wide_event["arrival_events_scheduled"] = scheduled_count
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.info(wide_event)
        
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(wide_event)