from typing import Any, Optional
from uuid import uuid4
from rq.job import Job, JobStatus
from app.configs.worker_configuration import get_queue_for_job, JobType
from app.dtos.responses.job_response_dto import AppJobStatus
from app.lib.job_utils import map_rq_status
from app.lib.logging.logging import get_logger
from app.lib.logging.wide_event_logger import wide_event

logger = get_logger(__name__)

class JobService:
    @staticmethod
    def validate_job_by_job_id(job_id: str, job_type: JobType = JobType.DEFAULT) -> bool:
        queue = get_queue_for_job(job_type)
        job = queue.fetch_job(job_id)
        
        if not job:
            return False
        
        return True
    
    @staticmethod
    def get_job_status(job_id: str, job_type: JobType = JobType.DEFAULT) -> Optional[JobStatus]:
        with wide_event("get_job_status", job_id=job_id, job_type=job_type.value) as event:
            queue = get_queue_for_job(job_type)
            job = queue.fetch_job(job_id)
            
            if job:
                job_status = job.get_status()
                event["job_status"] = job_status
                return job_status
            
            event["status"] = "not_found"
            return None
    
    @staticmethod
    def enqueue_job(
        function_path: str,
        job_type: JobType = JobType.DEFAULT,
        job_prefix: Optional[str] = None,
        *args: Any,
        **kwargs: Any
    ) -> Job:
        with wide_event(
            "enqueue_job",
            function_path=function_path,
            job_type=job_type.value,
            job_prefix=job_prefix,
        ) as event:
            queue = get_queue_for_job(job_type)
            
            if job_prefix:
                custom_job_id = f"{job_prefix}-{str(uuid4())[:8]}"
            else:
                custom_job_id = None
            
            job = queue.enqueue( # type: ignore [reportUnknownMemberType]
                function_path,
                *args,
                job_id=custom_job_id,
                **kwargs
            ) 
            
            event["job_id"] = job.id
            event["queue_name"] = queue.name
            
            return job


def enqueue_job(
    function_path: str,
    job_type: JobType = JobType.DEFAULT,
    job_prefix: Optional[str] = None,
    *args: Any,
    **kwargs: Any
) -> Job:
    return JobService.enqueue_job(function_path, job_type, job_prefix, *args, **kwargs)

def get_job_status(job_id: str, job_type: JobType = JobType.DEFAULT) -> AppJobStatus:
    rq_job_status = JobService.get_job_status(job_id, job_type)
    return map_rq_status(rq_job_status)

def get_jobs_statuses(job_ids: list[str], job_type: JobType = JobType.DEFAULT) -> dict[str, AppJobStatus]:
    statuses: dict[str, AppJobStatus] = {}
    
    for job_id in job_ids:
        statuses[job_id] = map_rq_status(JobService.get_job_status(job_id, job_type))
        
    return statuses

def validate_job_by_job_id(job_id: str, job_type: JobType = JobType.DEFAULT) -> bool:
    return JobService.validate_job_by_job_id(job_id, job_type)