"""API routes for job management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from rq.job import Job

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


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    try:
        redis = Redis()
        
        """ 
            Ignore type because mypy cannot infer the type of fetch() method correctly.
        """
        job = Job.fetch(job_id, connection=redis) # type: ignore [reportUnknownMemberType]
        
        return JobStatusResponse(
            job_id=job.id,
            status=job.get_status(),
            result=job.result if job.is_finished else None,
            error=str(job.exc_info) if job.is_failed else None
        )
    
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")
