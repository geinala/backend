"""Core utilities and Redis client setup."""

from redis import Redis
from rq import Queue
from app.core.config import get_settings


def get_redis_connection() -> Redis:
    """Get Redis connection instance."""
    settings = get_settings()
    return Redis.from_url(settings.redis_url)


def get_queue(queue_name: str = None) -> Queue:
    """Get RQ Queue instance."""
    settings = get_settings()
    queue_name = queue_name or settings.RQ_QUEUE
    redis_conn = get_redis_connection()
    return Queue(queue_name, connection=redis_conn)
