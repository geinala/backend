import time
from datetime import datetime, timezone

from rq import get_current_job

from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.repositories.route_repository import DueArrivalEvent, RouteRepository
from app.workers.events_worker import emit_vehicle_arrived_event

logger = get_logger(__name__)


def process_running_simulation_arrivals() -> dict[str, int]:
    job = get_current_job()
    start_time = time.time()

    wide_event: dict[str, object] = {
        "event_type": "worker_process_running_simulation_arrivals",
        "job_id": job.id if job else None,
        "status": "processing",
    }

    db_session = get_db()
    db = next(db_session)

    try:
        route_repository = RouteRepository(db)
        due_arrivals = route_repository.get_due_arrival_events_for_running_simulations(
            datetime.now(timezone.utc)
        )

        transitioned_arrivals: list[DueArrivalEvent] = []

        for arrival in due_arrivals:
            updated = route_repository.mark_route_leg_as_visited(arrival["route_leg_id"])
            if not updated:
                continue

            transitioned_arrivals.append(arrival)
            route_repository.promote_next_route_leg_to_in_progress(
                vehicle_route_id=arrival["vehicle_route_id"],
                current_sequence=arrival["sequence"],
            )

        db.commit()

        emitted_count = 0
        for arrival in transitioned_arrivals:
            if arrival["node_id"] < 0:
                continue

            emit_vehicle_arrived_event(
                simulation_id=arrival["simulation_id"],
                vehicle_id=arrival["vehicle_id"],
                node_id=arrival["node_id"],
            )
            emitted_count += 1

        wide_event["status"] = "success"
        wide_event["due_arrival_count"] = len(due_arrivals)
        wide_event["transitioned_count"] = len(transitioned_arrivals)
        wide_event["emitted_count"] = emitted_count
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.info(wide_event)

        return {
            "due_arrival_count": len(due_arrivals),
            "transitioned_count": len(transitioned_arrivals),
            "emitted_count": emitted_count,
        }
    except Exception as e:
        db.rollback()
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(wide_event)
        raise
    finally:
        db.close()
