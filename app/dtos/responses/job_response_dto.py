from enum import Enum
from pydantic import BaseModel

class AppJobStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"
    NOT_FOUND = "not_found"

class JobResponseDTO(BaseModel):
    job_id: str
    status: AppJobStatus
    message: str