"""Redis configuration with singleton pattern for client and queue instances."""

from typing import Optional
from threading import Lock
from redis import Redis
from rq import Queue
from app.configs.environment_configuration import get_environment_configuration


class RedisConfiguration:
    _instance: Optional["RedisConfiguration"] = None
    _lock: Lock = Lock()
    _redis_client: Optional[Redis] = None
    _queue_client: Optional[Queue] = None

    def __new__(cls) -> "RedisConfiguration":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        settings = get_environment_configuration()
        
        self._redis_client = Redis.from_url( # type: ignore [reportUnknownMemberType]
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
        ) 
        
        try:
            assert self._redis_client is not None
            
            self._redis_client.ping() # type: ignore [reportUnknownMemberType]
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e

    @property
    def redis(self) -> Redis:
        if self._redis_client is None:
            self._initialize()
        assert self._redis_client is not None, "Redis client should be initialized"
        return self._redis_client

    @property
    def queue(self) -> Queue:
        if self._queue_client is None:
            settings = get_environment_configuration()
            self._queue_client = Queue(
                name=settings.RQ_QUEUE,
                connection=self.redis,
                job_timeout=settings.RQ_JOB_TIMEOUT,
                result_ttl=settings.RQ_RESULT_TTL
            )
        return self._queue_client

    def close(self) -> None:
        if self._redis_client is not None:
            self._redis_client.close()
            self._redis_client = None
            self._queue_client = None

    def is_connected(self) -> bool:
        try:
            
            result: bool | object = self.redis.ping() # type: ignore [reportUnknownMemberType]
            return isinstance(result, bool) and result
        except Exception:
            return False


def get_redis_config() -> RedisConfiguration:
    return RedisConfiguration()


def get_redis_client() -> Redis:
    return get_redis_config().redis


def get_queue(queue_name: Optional[str] = None) -> Queue:
    if queue_name is None:
        return get_redis_config().queue

    settings = get_environment_configuration()
    return Queue(
        name=queue_name,
        connection=get_redis_client(),
        job_timeout=settings.RQ_JOB_TIMEOUT,
        result_ttl=settings.RQ_RESULT_TTL
    )
