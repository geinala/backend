import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, cast

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from app.configs.redis_configuration import get_redis_raw_client
from app.lib.logging.logging import get_logger
from app.services.realtime_event_service import GLOBAL_EVENTS_CHANNEL, get_events_channel

logger = get_logger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])

@router.get(path="/stream", summary="Stream events in real-time")
async def stream_events(
    simulation_id: str | None = Query(default=None),
) -> StreamingResponse:
    redis = get_redis_raw_client()
    pubsub: Any = redis.pubsub()  # type: ignore[reportUnknownMemberType]
    channel = (
        get_events_channel(simulation_id)
        if simulation_id
        else GLOBAL_EVENTS_CHANNEL
    )
    pubsub.subscribe(channel)

    async def event_generator() -> AsyncIterator[str]:
        try:
            while True:
                message = cast(
                    dict[str, object] | None,
                    await asyncio.to_thread(
                    pubsub.get_message,
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                    ),
                )

                if not message or message.get("type") != "message":
                    yield ": keep-alive\n\n"
                    await asyncio.sleep(1)
                    continue

                raw_data = message.get("data")

                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")

                if not isinstance(raw_data, str):
                    continue

                try:
                    event = cast(dict[str, Any], json.loads(raw_data))
                except json.JSONDecodeError:
                    continue

                event_id = event.get("id", "evt_unknown")
                event_type = event.get("type", "MESSAGE")
                payload = json.dumps(event.get("data", {}))

                yield f"id: {event_id}\n"
                yield f"event: {event_type}\n"
                yield f"data: {payload}\n\n"
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )