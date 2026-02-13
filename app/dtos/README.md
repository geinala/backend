# DTOs Module

Data Transfer Objects - Request/Response validation models for API endpoints.

## Purpose

This module contains Pydantic models for:

- **Request validation** - Validate incoming API request data
- **Response serialization** - Format outgoing API responses
- **Type documentation** - Self-documenting API contracts
- **Job configuration** - Structured data for job parameters

## Available DTOs

### SimulationConfig

Configuration DTO for simulation job requests:

```python
from app.dtos import SimulationConfig

config = SimulationConfig(
    name="test_sim_001",
    parameters={"iterations": 1000, "precision": 0.01},
    timeout=600
)

# Access validated data
print(config.name)         # "test_sim_001"
print(config.parameters)   # {"iterations": 1000, "precision": 0.01}
print(config.timeout)      # 600
```

**Fields:**

- `name` (str) - Simulation identifier
- `parameters` (dict, optional) - Simulation parameters
- `timeout` (int, optional) - Job timeout in seconds (default: 300)

### JobResult

Result DTO from completed jobs:

```python
from app.dtos import JobResult
from datetime import datetime

result = JobResult(
    status="success",
    result={"output": "simulation data"},
    error=None,
    job_id="abc123",
    timestamp=datetime.utcnow().isoformat()
)
```

**Fields:**

- `status` (str) - "success", "failed", or "timeout"
- `result` (dict, optional) - Job result data
- `error` (str, optional) - Error message if failed
- `job_id` (str, optional) - RQ job ID
- `timestamp` (str) - ISO format timestamp

## Using DTOs

### In API Routes

```python
from fastapi import APIRouter
from app.dtos import SimulationConfig, JobResult

@router.post("/simulations", response_model=JobResult)
async def enqueue_simulation(config: SimulationConfig):
    """Request is auto-validated by Pydantic."""
    # config is guaranteed to be valid
    q = get_queue()
    job = q.enqueue(
        'app.workers.simulation.process_simulation',
        config.dict()
    )
    return JobResult(
        job_id=job.id,
        status="queued",
        result=None,
        error=None,
        timestamp=datetime.utcnow().isoformat()
    )
```

### In Job Handlers

```python
from app.dtos import SimulationConfig
from pydantic import ValidationError

def process_simulation(config_dict: dict) -> dict:
    """Validate config before processing."""
    try:
        config = SimulationConfig(**config_dict)
    except ValidationError as e:
        return {
            "status": "failed",
            "error": str(e)
        }

    # Use validated config
    iterations = config.parameters.get('iterations', 100)
    for i in range(iterations):
        # Process...
        pass

    return {
        "status": "success",
        "result": {...}
    }
```

## Creating New DTOs

### Request DTO

```python
from pydantic import BaseModel, Field
from typing import Optional

class MyJobRequest(BaseModel):
    """Request to enqueue my job."""

    name: str = Field(..., description="Job name")
    iterations: int = Field(default=100, ge=1, le=10000, description="Number of iterations")
    debug: Optional[bool] = Field(default=False, description="Enable debug mode")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "my_job",
                "iterations": 1000,
                "debug": False
            }
        }
```

### Response DTO

```python
from typing import Optional, Any

class MyJobResponse(BaseModel):
    """Response with job information."""

    job_id: str = Field(..., description="RQ job ID")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Human-readable message")
    result: Optional[Any] = Field(default=None, description="Job result")
```

## Using in Routes

```python
from fastapi import APIRouter
from app.dtos import MyJobRequest, MyJobResponse

router = APIRouter()

@router.post("/my-job", response_model=MyJobResponse)
async def enqueue_my_job(request: MyJobRequest) -> MyJobResponse:
    """
    Enqueue a new job with the given parameters.

    - Request is auto-validated by Pydantic
    - Response is auto-serialized to JSON
    """
    q = get_queue()
    job = q.enqueue(
        'app.workers.my_module.my_job',
        {
            'name': request.name,
            'iterations': request.iterations,
            'debug': request.debug
        },
        job_timeout='30m'
    )

    return MyJobResponse(
        job_id=job.id,
        status="queued",
        message=f"Job {job.id} queued successfully"
    )
```

## Validation Features

### Type Checking

```python
# ❌ This will raise ValidationError
config = SimulationConfig(
    name=123,  # Expected str, got int
    parameters={"iterations": 1000}
)

# ✅ This is valid
config = SimulationConfig(
    name="my_sim",
    parameters={"iterations": 1000}
)
```

### Constraints

```python
from pydantic import BaseModel, Field

class ConfigWithLimits(BaseModel):
    """Job config with validation constraints."""

    iterations: int = Field(ge=1, le=10000, description="1 to 10000")
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
```

### Default Values & Optional

```python
class ConfigWithDefaults(BaseModel):
    name: str                                      # Required
    timeout: int = 300                             # Default 300 seconds
    debug: bool = False                            # Default False
    tags: list = Field(default_factory=list)       # Default empty list
    description: Optional[str] = None              # Optional (can be None)
```

## Testing DTOs

```python
from app.dtos import SimulationConfig
import pytest
from pydantic import ValidationError

def test_simulation_config_valid():
    config = SimulationConfig(
        name="test",
        parameters={"iterations": 100}
    )
    assert config.name == "test"
    assert config.timeout == 300  # Default value

def test_simulation_config_invalid():
    with pytest.raises(ValidationError):
        SimulationConfig(
            name=123,  # Should be str
            parameters={}
        )

def test_simulation_config_serialization():
    config = SimulationConfig(
        name="test",
        parameters={"iterations": 100}
    )
    # Serialize to dict for job inquiry
    data = config.dict()
    assert data['name'] == "test"
```

## Best Practices

✅ **Always validate API inputs**

```python
@router.post("/jobs")
async def enqueue_job(config: MyJobConfig):  # Auto-validated
    ...
```

✅ **Use Field() for documentation**

```python
name: str = Field(..., description="Job name")
iterations: int = Field(default=100, ge=1, le=10000)
```

✅ **Add example data**

```python
class Config:
    json_schema_extra = {"example": {...}}
```

✅ **Separate request and response models**

```python
# Request (input)
class MyRequest(BaseModel):
    config: str

# Response (output)
class MyResponse(BaseModel):
    job_id: str
    status: str
```

❌ **Don't skip validation**

```python
# Bad - No validation
@router.post("/jobs")
def enqueue_job(data: dict):
    iterations = data['iterations']  # KeyError risk, no type safety

# Good - Use DTO
@router.post("/jobs")
def enqueue_job(config: MyJobConfig):
    iterations = config.iterations  # Type-safe, validated
```

## Difference: DTOs vs Models

- **DTOs** (`app/dtos/`) - For API request/response serialization
- **Models** (`app/models/`) - For database entities and domain objects

DTOs are for JSON serialization, Models are for persistence.

## References

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pydantic Field Validation](https://docs.pydantic.dev/latest/concepts/fields/)
- [FastAPI Request Body](https://fastapi.tiangolo.com/tutorial/body/)
- [FastAPI Response Model](https://fastapi.tiangolo.com/tutorial/response_model/)
