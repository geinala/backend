import json
from datetime import timedelta
from typing import Any, TypedDict
from uuid import uuid4

from app.configs.worker_configuration import JobType, get_queue_for_job
from app.configs.redis_configuration import get_redis_client
from app.lib.logging.logging import get_logger

EVENTS_CHANNEL_PREFIX = "simulation:events"
GLOBAL_EVENTS_CHANNEL = f"{EVENTS_CHANNEL_PREFIX}:global"

logger = get_logger(__name__)


class CourierArrivalSchedule(TypedDict):
    simulation_id: str
    courier_id: int
    node_id: int
    eta_seconds: int


def get_events_channel(simulation_id: str) -> str:
    return f"{EVENTS_CHANNEL_PREFIX}:{simulation_id}"


def publish_realtime_event(
    event_type: str,
    payload: dict[str, Any],
    simulation_id: str | None = None,
) -> None:
    redis = get_redis_client()
    resolved_simulation_id = simulation_id

    if resolved_simulation_id is None:
        payload_simulation_id = payload.get("simulationId")
        if isinstance(payload_simulation_id, str):
            resolved_simulation_id = payload_simulation_id

    event: dict[str, Any] = {
        "id": f"evt_{uuid4().hex[:8]}",
        "type": event_type,
        "data": payload,
    }

    serialized_event = json.dumps(event)

    # Keep a global stream for backward compatibility and diagnostics.
    redis.publish(GLOBAL_EVENTS_CHANNEL, serialized_event)  # type: ignore[reportUnknownMemberType]

    if resolved_simulation_id:
        redis.publish(  # type: ignore[reportUnknownMemberType]
            get_events_channel(resolved_simulation_id),
            serialized_event,
        )


def schedule_courier_arrival_events(arrivals: list[CourierArrivalSchedule]) -> int:
    if not arrivals:
        return 0

    queue = get_queue_for_job(JobType.LIGHT)
    scheduled_count = 0

    for arrival in arrivals:
        eta_seconds = max(arrival["eta_seconds"], 0)
        queue.enqueue_in(  # type: ignore[reportUnknownMemberType]
            timedelta(seconds=eta_seconds),
            "app.workers.events_worker.emit_vehicle_arrived_event",
            simulation_id=arrival["simulation_id"],
            courier_id=arrival["courier_id"],
            node_id=arrival["node_id"],
        )
        scheduled_count += 1

    logger.info(
        {
            "event_type": "courier_arrival_events_scheduled",
            "scheduled_count": scheduled_count,
        }
    )

    return scheduled_count