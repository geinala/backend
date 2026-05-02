from app.configs.environment_configuration import get_environment_configuration
from app.lib.logging.logging import get_logger
from app.schedulers.simulation_arrival_scheduler import (
    SIMULATION_ARRIVAL_CHECK_DEFAULT_INTERVAL_SECONDS,
    ensure_simulation_arrival_check_schedule,
)

logger = get_logger(__name__)


def register_all_schedules() -> list[str]:
    settings = get_environment_configuration()
    registered_schedule_ids: list[str] = []

    if settings.ENABLE_SIMULATION_ARRIVAL_CHECK_SCHEDULE:
        schedule_id = ensure_simulation_arrival_check_schedule(
            interval_seconds=settings.SIMULATION_ARRIVAL_CHECK_SCHEDULE_INTERVAL_SECONDS,
            queue_name=settings.SIMULATION_ARRIVAL_CHECK_SCHEDULE_QUEUE,
        )
        registered_schedule_ids.append(schedule_id)
    else:
        logger.info(
            {
                "event_type": "schedule_disabled",
                "schedule_name": "simulation_arrival_check",
            }
        )

    logger.info(
        {
            "event_type": "scheduler_bootstrap_completed",
            "registered_schedule_count": len(registered_schedule_ids),
            "registered_schedule_ids": registered_schedule_ids,
            "defaults": {
                "simulation_arrival_check_interval_seconds": SIMULATION_ARRIVAL_CHECK_DEFAULT_INTERVAL_SECONDS,
            },
        }
    )

    return registered_schedule_ids


if __name__ == "__main__":
    register_all_schedules()
