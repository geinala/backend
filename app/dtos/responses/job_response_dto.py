from enum import Enum

from pydantic import BaseModel

class JobStatusEnum(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class JobResponseDTO(BaseModel):
    job_id: str
    status: JobStatusEnum
    message: str