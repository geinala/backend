"""Worker and queue configuration for different job types.

Supports multiple queue types with different processing characteristics:
- Heavy: CPU-intensive, long-running tasks (e.g., simulations, data processing)
- Light: Quick tasks, low resource usage (e.g., validation, notifications)
- Default: Standard priority tasks
"""

from enum import Enum
from typing import Optional
from rq import Queue
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
        """Initialize worker configuration from environment settings."""
        self.settings = get_environment_configuration()
        self._queues: dict[str, Queue] = {}
    
    def get_queue(self, job_type: JobType = JobType.DEFAULT) -> Queue:
        """Get or create queue for specific job type.
        
        Args:
            job_type: Type of job (HEAVY, LIGHT, DEFAULT)
            
        Returns:
            RQ Queue instance configured for the job type
            
        Examples:
            >>> config = WorkerConfiguration()
            
            # Get heavy processing queue
            >>> heavy_q = config.get_queue(JobType.HEAVY)
            >>> job = heavy_q.enqueue('app.workers.simulation.run_simulation')
            
            # Get light processing queue
            >>> light_q = config.get_queue(JobType.LIGHT)
            >>> job = light_q.enqueue('app.workers.validation.validate_data')
            
            # Get default queue
            >>> default_q = config.get_queue()
        """
        if job_type.value in self._queues:
            return self._queues[job_type.value]
        
        queue = self._create_queue(job_type)
        self._queues[job_type.value] = queue
        return queue
    
    def _create_queue(self, job_type: JobType) -> Queue:
        """Create queue with settings specific to job type."""
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
        
        else:  # DEFAULT
            return Queue(
                name=self.settings.RQ_QUEUE,
                connection=redis_client,
                job_timeout=self.settings.RQ_JOB_TIMEOUT,
                result_ttl=self.settings.RQ_RESULT_TTL,
                default_result_ttl=self.settings.RQ_RESULT_TTL,
            )
    
    def get_queue_info(self) -> dict[str, dict[str, object]]:
        """Get information about all configured queues.
        
        Returns:
            Dictionary with queue configuration details
            
        Example:
            >>> config = WorkerConfiguration()
            >>> info = config.get_queue_info()
            >>> print(info)
            {
                'heavy': {
                    'queue_name': 'heavy',
                    'job_timeout': '30m',
                    'workers': 2,
                    'job_count': 5
                },
                'light': {
                    'queue_name': 'light',
                    'job_timeout': '5m',
                    'workers': 4,
                    'job_count': 12
                },
                'default': {
                    'queue_name': 'default',
                    'job_timeout': '10m',
                    'workers': 1,
                    'job_count': 3
                }
            }
        """
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


# Global singleton instance
_worker_config: Optional[WorkerConfiguration] = None


def get_worker_config() -> WorkerConfiguration:
    """Get or create singleton worker configuration instance.
    
    Returns:
        WorkerConfiguration singleton
        
    Examples:
        >>> config = get_worker_config()
        >>> heavy_q = config.get_queue(JobType.HEAVY)
    """
    global _worker_config
    if _worker_config is None:
        _worker_config = WorkerConfiguration()
    return _worker_config


def get_queue_for_job(job_type: JobType) -> Queue:
    """Get queue for specific job type.
    
    Convenience function that wraps get_worker_config().get_queue()
    
    Args:
        job_type: Type of job (HEAVY, LIGHT, DEFAULT)
        
    Returns:
        RQ Queue instance
        
    Examples:
        # Enqueue heavy processing job
        >>> q_heavy = get_queue_for_job(JobType.HEAVY)
        >>> job = q_heavy.enqueue('app.workers.simulation.run_simulation')
        
        # Enqueue light processing job
        >>> q_light = get_queue_for_job(JobType.LIGHT)
        >>> job = q_light.enqueue('app.workers.notification.send_email')
    """
    return get_worker_config().get_queue(job_type)


def enqueue_job(
    function_path: str,
    job_type: JobType = JobType.DEFAULT,
    *args, # type: ignore [reportUnusedVariable]
    **kwargs # type: ignore [reportUnusedVariable]
):
    """Enqueue job to appropriate queue based on job type.
    
    Args:
        function_path: Dotted path to job function (e.g., 'app.workers.simulation.process')
        job_type: Type of job (HEAVY, LIGHT, DEFAULT)
        *args: Positional arguments to pass to job function
        **kwargs: Keyword arguments to pass to job function
        
    Returns:
        RQ Job instance
        
    Examples:
        # Enqueue heavy simulation job
        >>> job = enqueue_job(
        ...     'app.workers.simulation.run_large_simulation',
        ...     job_type=JobType.HEAVY,
        ...     iterations=10000,
        ...     params={'algorithm': 'monte_carlo'}
        ... )
        >>> print(f"Job {job.id} enqueued to heavy queue")
        
        # Enqueue quick validation job
        >>> job = enqueue_job(
        ...     'app.workers.validation.validate_config',
        ...     job_type=JobType.LIGHT,
        ...     config={'name': 'test'}
        ... )
        >>> print(f"Job {job.id} enqueued to light queue")
    """
    queue = get_queue_for_job(job_type)
    job = queue.enqueue(function_path, *args, **kwargs) # type: ignore [reportUnknownMemberType]
    return job
