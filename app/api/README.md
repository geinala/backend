# API Module

FastAPI routes for job management and health checks.

## Purpose

This module provides HTTP endpoints to:

- **Enqueue jobs** - Submit tasks to the Redis queue
- **Check job status** - Get job progress and results
- **Health checks** - Monitor worker and Redis connectivity

## Files

### `routes.py`

Main FastAPI router with job management endpoints.

## Available Endpoints

### Enqueue Hello World Job

```http
POST /jobs/hello-world
```

Request:

```json
{}
```

Response (202 Accepted):

```json
{
  "job_id": "abc123",
  "status": "queued",
  "message": "Job abc123 queued successfully"
}
```

### Get Job Status

```http
GET /jobs/status/{job_id}
```

Response:

```json
{
  "job_id": "abc123",
  "status": "started",
  "result": null,
  "error": null
}
```

Possible status values:

- `queued` - Waiting in queue
- `started` - Currently running
- `succeeded` - Completed successfully
- `failed` - Job failed
- `stopped` - Job was stopped
- `scheduled` - Scheduled for later

## Creating New Endpoints

### 1. Define Request/Response Models

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

### 2. Create Route Handler

```python
from fastapi import APIRouter, HTTPException
from rq import Queue
from redis import Redis

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/my-job", response_model=MyJobResponse)
async def enqueue_my_job(request: MyJobRequest):
    try:
        redis = Redis()
        q = Queue(connection=redis)

        # Enqueue job with parameters
        job = q.enqueue(
            'app.workers.my_module.my_job',
            {'param1': request.param1, 'param2': request.param2},
            job_timeout='30m'
        )

        return MyJobResponse(
            job_id=job.id,
            status="queued",
            message=f"Job {job.id} queued successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. Best Practices

✅ **Always use config for Redis**

```python
from app.configs import get_redis_client, get_queue

redis = get_redis_client()
queue = get_queue()
```

✅ **Use type hints and Pydantic models**

```python
class MyRequest(BaseModel):
    name: str
    timeout: Optional[int] = 300
```

✅ **Handle errors gracefully**

```python
try:
    job = q.enqueue(...)
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

✅ **Document with docstrings**

```python
@router.post("/my-job")
async def enqueue_my_job(request: MyJobRequest):
    """Enqueue a new my job with the given parameters."""
    ...
```

❌ **Avoid direct Redis calls**

```python
# Bad - Don't do this
redis = Redis(host='localhost', port=6379)

# Good - Use config
from app.configs import get_redis_client
redis = get_redis_client()
```

## Error Handling

### Job Not Found

```python
from rq.job import Job, NoSuchJobError

try:
    job = Job.fetch(job_id, connection=redis)
except NoSuchJobError:
    raise HTTPException(status_code=404, detail="Job not found")
```

### Invalid Parameters

```python
from pydantic import ValidationError

try:
    config = MyModel(**params)
except ValidationError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

## Testing

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_enqueue_hello_world():
    response = client.post("/jobs/hello-world")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"

def test_get_job_status():
    response = client.get("/jobs/status/invalid-id")
    assert response.status_code == 404
```

## Integration with Workers

When enqueuing a job, the path must match the worker function:

```python
# Route: app/api/routes.py
job = q.enqueue('app.workers.simulation.process_simulation', {...})

# Worker: app/workers/simulation.py
def process_simulation(config: dict) -> dict:
    ...
```

## Architecture

```
FastAPI Routes (HTTP)
        ↓
Pydantic Models (Validation)
        ↓
RQ Queue (Enqueuing)
        ↓
Redis (Message Broker)
        ↓
RQ Worker (Execution)
```

**Request flow:**

1. Client sends HTTP request with JSON
2. Pydantic validates request data
3. Route handler enqueues job to Redis
4. Returns job ID and status
5. Client can poll `/status/{job_id}` for progress
