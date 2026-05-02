from datetime import datetime, timezone
from typing import Any, Iterable, cast

from rq.job import Job
from rq_scheduler import Scheduler

from app.configs.environment_configuration import get_environment_configuration
from app.configs.redis_configuration import get_redis_raw_client
from app.lib.logging.logging import get_logger
from app.workers import simulation_progress_worker_process_running_simulation_arrivals

logger = get_logger(__name__)

SIMULATION_ARRIVAL_CHECK_SCHEDULE_ID = "simulation-arrival-check-every-1-minutes"
SIMULATION_ARRIVAL_CHECK_DEFAULT_INTERVAL_SECONDS = 60


def _find_scheduled_job(scheduler: Scheduler, job_id: str) -> Job | None:
    scheduler_any = cast(Any, scheduler)
    jobs = cast(Iterable[Job], scheduler_any.get_jobs())

    for job in jobs:
        if job.id == job_id:
            return job

    return None


def ensure_simulation_arrival_check_schedule(
    interval_seconds: int = SIMULATION_ARRIVAL_CHECK_DEFAULT_INTERVAL_SECONDS,
    queue_name: str | None = None,
) -> str:
    settings = get_environment_configuration()
    selected_queue = queue_name or settings.RQ_LIGHT_QUEUE

    scheduler = Scheduler(
        connection=get_redis_raw_client(),
        queue_name=selected_queue,
    )

    existing_job = _find_scheduled_job(scheduler, SIMULATION_ARRIVAL_CHECK_SCHEDULE_ID)
    if existing_job is not None:
        logger.info(
            {
                "event_type": "simulation_arrival_check_schedule_already_exists",
                "schedule_id": SIMULATION_ARRIVAL_CHECK_SCHEDULE_ID,
                "queue": selected_queue,
            }
        )
        return SIMULATION_ARRIVAL_CHECK_SCHEDULE_ID

    scheduler_any = cast(Any, scheduler)
    scheduler_any.schedule(
        scheduled_time=datetime.now(timezone.utc),
        func=simulation_progress_worker_process_running_simulation_arrivals,
        interval=interval_seconds,
        repeat=None,
        id=SIMULATION_ARRIVAL_CHECK_SCHEDULE_ID,
        queue_name=selected_queue,
    )

    logger.info(
        {
            "event_type": "simulation_arrival_check_schedule_created",
            "schedule_id": SIMULATION_ARRIVAL_CHECK_SCHEDULE_ID,
            "queue": selected_queue,
            "interval_seconds": interval_seconds,
        }
    )

    return SIMULATION_ARRIVAL_CHECK_SCHEDULE_ID


if __name__ == "__main__":
    ensure_simulation_arrival_check_schedule()
