# API Module

FastAPI routes for job management and health checks.

## Purpose

This module provides HTTP endpoints to:

- **Enqueue jobs** - Submit tasks to the Redis queue via controllers
- **Check job status** - Retrieve job progress and results
- **Handle errors** - Return appropriate HTTP responses with structured error data

## Creating New Endpoints

### Architecture Flow

```
FastAPI Route (HTTP)
        ↓
Controller (Orchestration + Validation)
        ↓
Service (Business Logic)
        ↓
Worker (Background Execution via RQ)
        ↓
Redis Queue
```

### Step 1: Define Request/Response Models

Create DTOs in `app/dtos/`:

```python
from pydantic import BaseModel
from typing import Optional

class MyJobRequest(BaseModel):
    """Request to enqueue my job."""
    param1: str
    param2: int = 10

class MyJobResponse(BaseModel):
    """Response with job information."""
    job_id: str
    status: str
    message: str
```

### Step 2: Create Custom Exception (if needed)

In `app/exceptions/base.py`:

```python
from fastapi import status

class JobException(Exception):
    """Base exception for job-related errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class JobNotFoundError(JobException):
    """Raised when job is not found."""
    def __init__(self, job_id: str):
        super().__init__(
            f"Job {job_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
```

### Step 3: Create Service

In `app/services/job_service.py`:

```python
from app.lib.logging import get_logger
from app.configs import get_queue, get_redis_client
from rq.job import Job, NoSuchJobError

logger = get_logger(__name__)

class JobService:
    """Business logic for job operations."""

    @staticmethod
    def enqueue_my_job(param1: str, param2: int) -> str:
        """Enqueue a new job and return job ID."""
        try:
            logger.info(f"Enqueuing job with param1={param1}, param2={param2}")

            queue = get_queue()
            job = queue.enqueue(
                'app.workers.my_module.my_job',
                param1=param1,
                param2=param2,
                job_timeout='30m'
            )

            logger.info(f"Job enqueued successfully: {job.id}")
            return job.id
        except Exception as e:
            logger.error(f"Failed to enqueue job: {str(e)}")
            raise

    @staticmethod
    def get_job_status(job_id: str) -> dict:
        """Get job status and result."""
        try:
            logger.info(f"Fetching status for job: {job_id}")

            redis = get_redis_client()
            job = Job.fetch(job_id, connection=redis)

            return {
                "job_id": job.id,
                "status": job.get_status(),
                "result": job.result,
                "error": job.exc_info
            }
        except NoSuchJobError:
            logger.warning(f"Job not found: {job_id}")
            raise
        except Exception as e:
            logger.error(f"Error fetching job status: {str(e)}")
            raise
```

### Step 4: Create Controller

In `app/controllers/job_controller.py`:

```python
from app.lib.logging import get_logger
from app.services.job_service import JobService
from app.dtos import MyJobRequest, MyJobResponse
from app.api.exceptions import JobNotFoundError
from rq.job import NoSuchJobError

logger = get_logger(__name__)

class JobController:
    """Orchestrate job operations between routes and services."""

    @staticmethod
    def enqueue_my_job(request: MyJobRequest) -> dict:
        """Handle enqueue job request."""
        try:
            logger.info(f"Controller: Processing enqueue job request - {request}")

            job_id = JobService.enqueue_my_job(
                param1=request.param1,
                param2=request.param2
            )

            logger.info(f"Controller: Job enqueued successfully - {job_id}")
            return {
                "job_id": job_id,
                "status": "queued",
                "message": f"Job {job_id} queued successfully"
            }
        except Exception as e:
            logger.error(f"Controller: Error enqueuing job - {str(e)}")
            raise

    @staticmethod
    def get_job_status(job_id: str) -> dict:
        """Handle get job status request."""
        try:
            logger.info(f"Controller: Fetching job status - {job_id}")

            status_data = JobService.get_job_status(job_id)

            logger.info(f"Controller: Job status retrieved - {job_id}")
            return status_data
        except NoSuchJobError:
            logger.warning(f"Controller: Job not found - {job_id}")
            raise JobNotFoundError(job_id)
        except Exception as e:
            logger.error(f"Controller: Error getting job status - {str(e)}")
            raise
```

### Step 5: Create Route Handler

In `app/api/jobs.py`:

```python
from fastapi import APIRouter, HTTPException
from app.lib.logging import get_logger
from app.controllers.job_controller import JobController
from app.dtos import MyJobRequest, MyJobResponse
from app.api.exceptions.base import JobException

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/my-job", response_model=MyJobResponse)
async def enqueue_my_job(request: MyJobRequest):
    """Enqueue a new my job with the given parameters."""
    try:
        logger.info("Route: Received enqueue my job request")

        response = JobController.enqueue_my_job(request)

        logger.info(f"Route: Returning response - {response}")
        return MyJobResponse(**response)
    except JobException as e:
        logger.error(f"Route: Job exception - {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Route: Unexpected error - {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 6: Create Worker

In `app/workers/my_module.py`:

```python
from app.lib.logging import get_logger
from rq import current_job

logger = get_logger(__name__)

def my_job(param1: str, param2: int) -> dict:
    """Execute my job in background."""
    job = current_job()

    try:
        logger.info(f"Worker: Starting job {job.id} with param1={param1}, param2={param2}")

        # Simulate work
        result = {"param1": param1, "param2": param2, "computed": param2 * 2}

        logger.info(f"Worker: Job {job.id} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Worker: Job {job.id} failed - {str(e)}")
        raise
```

## Best Practices

✅ **Always implement the full layer chain: Route → Controller → Service → Worker**

- Routes validate HTTP input
- Controllers orchestrate business logic
- Services contain reusable business logic
- Workers execute long-running tasks

✅ **Use logging at every layer**

```python
logger = get_logger(__name__)
logger.info(f"Layer: Action - Details")
```

✅ **Use type hints and Pydantic models**

```python
from pydantic import BaseModel

class Request(BaseModel):
    field: str
    value: int = 10
```

✅ **Use config for infrastructure**

```python
from app.configs import get_redis_client, get_queue
redis = get_redis_client()
queue = get_queue()
```

✅ **Create custom exceptions for domain errors**

```python
from app.api.exceptions import JobException, JobNotFoundError
```

✅ **Handle errors gracefully with appropriate HTTP status codes**

```python
from fastapi import HTTPException, status

try:
    result = service.operation()
except CustomError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

❌ **Avoid mixing concerns**

```python
# Bad - Business logic in routes
@router.post("/job")
def create_job(config: dict):
    redis = Redis()
    queue = Queue(connection=redis)
    queue.enqueue('worker.task', config)

# Good - Separate layers
@router.post("/job")
async def create_job(request: JobRequest):
    return JobController.create_job(request)
```

❌ **Avoid hardcoded values**

```python
# Bad
job = q.enqueue('worker.task', timeout='30m')

# Good
job = q.enqueue(
    'worker.task',
    job_timeout=settings.RQ_JOB_TIMEOUT
)
```
