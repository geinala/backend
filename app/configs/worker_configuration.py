"""Worker and queue configuration for different job types.

Supports multiple queue types with different processing characteristics:
- Heavy: CPU-intensive, long-running tasks (e.g., simulations, data processing)
- Light: Quick tasks, low resource usage (e.g., validation, notifications)
- Default: Standard priority tasks
"""

from enum import Enum
from typing import Any, Optional
from rq import Queue
from rq.job import Job
from app.configs.redis_configuration import get_redis_client
from app.configs.environment_configuration import get_environment_configuration


class JobType(Enum):
    """Job type enumeration for routing to appropriate queue."""
    
    HEAVY = "heavy"      # CPU-intensive, long-running jobs
    LIGHT = "light"      # Quick, low-resource jobs
    DEFAULT = "default"  # Standard priority jobs


class WorkerConfiguration:
    """Configuration for worker instances managing different job queues."""
    
    def __init__(self):
        self.settings = get_environment_configuration()
        self._queues: dict[str, Queue] = {}
    
    def get_queue(self, job_type: JobType = JobType.DEFAULT) -> Queue:
        if job_type.value in self._queues:
            return self._queues[job_type.value]
        
        queue = self._create_queue(job_type)
        self._queues[job_type.value] = queue
        return queue
    
    def _create_queue(self, job_type: JobType) -> Queue:
        redis_client = get_redis_client()
        
        if job_type == JobType.HEAVY:
            return Queue(
                name=self.settings.RQ_HEAVY_QUEUE,
                connection=redis_client,
                job_timeout=self.settings.RQ_HEAVY_JOB_TIMEOUT,
                result_ttl=self.settings.RQ_HEAVY_RESULT_TTL,
                default_result_ttl=self.settings.RQ_HEAVY_RESULT_TTL,
            )
        
        elif job_type == JobType.LIGHT:
            return Queue(
                name=self.settings.RQ_LIGHT_QUEUE,
                connection=redis_client,
                job_timeout=self.settings.RQ_LIGHT_JOB_TIMEOUT,
                result_ttl=self.settings.RQ_LIGHT_RESULT_TTL,
                default_result_ttl=self.settings.RQ_LIGHT_RESULT_TTL,
            )
        
        else:
            return Queue(
                name=self.settings.RQ_QUEUE,
                connection=redis_client,
                job_timeout=self.settings.RQ_JOB_TIMEOUT,
                result_ttl=self.settings.RQ_RESULT_TTL,
                default_result_ttl=self.settings.RQ_RESULT_TTL,
            )
    
    def get_queue_info(self) -> dict[str, dict[str, object]]:
        return {
            'heavy': {
                'queue_name': self.settings.RQ_HEAVY_QUEUE,
                'job_timeout': self.settings.RQ_HEAVY_JOB_TIMEOUT,
                'result_ttl': self.settings.RQ_HEAVY_RESULT_TTL,
                'workers': self.settings.RQ_HEAVY_WORKERS,
                'job_count': len(self.get_queue(JobType.HEAVY)),
            },
            'light': {
                'queue_name': self.settings.RQ_LIGHT_QUEUE,
                'job_timeout': self.settings.RQ_LIGHT_JOB_TIMEOUT,
                'result_ttl': self.settings.RQ_LIGHT_RESULT_TTL,
                'workers': self.settings.RQ_LIGHT_WORKERS,
                'job_count': len(self.get_queue(JobType.LIGHT)),
            },
            'default': {
                'queue_name': self.settings.RQ_QUEUE,
                'job_timeout': self.settings.RQ_JOB_TIMEOUT,
                'result_ttl': self.settings.RQ_RESULT_TTL,
                'workers': 1,
                'job_count': len(self.get_queue(JobType.DEFAULT)),
            }
        }


_worker_config: Optional[WorkerConfiguration] = None


def get_worker_config() -> WorkerConfiguration:
    global _worker_config
    if _worker_config is None:
        _worker_config = WorkerConfiguration()
    return _worker_config


def get_queue_for_job(job_type: JobType) -> Queue:
    return get_worker_config().get_queue(job_type)


def enqueue_job(
    function_path: str,
    job_type: JobType = JobType.DEFAULT,
    *args: Any,
    **kwargs: Any
) -> Job:
    queue = get_queue_for_job(job_type)
    job = queue.enqueue(function_path, *args, **kwargs) # type: ignore [reportUnknownMemberType]
    return job
