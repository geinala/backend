from datetime import datetime, timezone

from rq import get_current_job

from app.lib.db import get_db
from app.repositories.node_repository import NodeRepository
from app.repositories.route_leg_congestion_check_repository import RouteLegCongestionCheckRepository
from app.repositories.route_repository import RouteRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.traffic_incident_repository import TrafficIncidentRepository
from app.services.simulation_progress_service import SimulationProgressService
from app.services.tomtom_service import TomTomService

def process_running_simulation_arrivals() -> dict[str, int]:
    job = get_current_job()

    db_session = get_db()
    db = next(db_session)

    service = SimulationProgressService(
        route_repository=RouteRepository(db),
        route_leg_congestion_check_repository=RouteLegCongestionCheckRepository(db),
        node_repository=NodeRepository(db),
        simulation_repository=SimulationRepository(db),
        traffic_incident_repository=TrafficIncidentRepository(db),
        tomtom_service=TomTomService(),
    )

    try:
        result = service.process_running_simulation_arrivals(
            reference_time=datetime.now(timezone.utc),
            job_id=job.id if job else None,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


