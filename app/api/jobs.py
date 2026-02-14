"""Routes for job management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from redis import Redis
from rq import Queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


class HelloWorldRequest(BaseModel):
    pass


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: dict[str, object] | None = None
    error: str | None = None


@router.post("/hello-world", response_model=JobResponse)
async def enqueue_hello_world():
    try:
        redis = Redis()
        q = Queue(connection=redis)
        
        """ 
            Ignore type because mypy cannot infer the type of enqueue() method correctly.
        """
        job = q.enqueue( # type: ignore [reportUnknownMemberType]
            'app.workers.hello_world.hello_world'
        ) 
        
        return JobResponse(
            job_id=job.id,
            status="queued",
            message=f"Job {job.id} queued successfully"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
