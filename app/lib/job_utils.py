from rq.job import JobStatus as RQJobStatus
from typing import Optional
from app.configs.worker_configuration import JobType
from app.dtos.responses.job_response_dto import AppJobStatus

def map_rq_status(status: Optional[RQJobStatus]) -> AppJobStatus:
    if status is None:
        return AppJobStatus.NOT_FOUND

    if status in {RQJobStatus.QUEUED, RQJobStatus.SCHEDULED}:
        return AppJobStatus.QUEUED

    if status in {RQJobStatus.STARTED, RQJobStatus.DEFERRED}:
        return AppJobStatus.PROCESSING

    if status == RQJobStatus.FINISHED:
        return AppJobStatus.SUCCESS

    if status == RQJobStatus.FAILED:
        return AppJobStatus.FAILED

    if status == RQJobStatus.CANCELED:
        return AppJobStatus.CANCELED

    return AppJobStatus.FAILED

def get_job_type_from_job_id(job_id: str) -> Optional[JobType]:
    if job_id.startswith("light-"):
        return JobType.LIGHT
    elif job_id.startswith("default-"):
        return JobType.DEFAULT
    else:
        return None