# DTOs Module

Data Transfer Objects - Request/Response validation models for API layer.

## Purpose

This module contains Pydantic models for:

- **Request validation** - Validate incoming API request data
- **Response serialization** - Format outgoing API responses
- **Type documentation** - Self-documenting API contracts with JSON schemas
- **Job configuration** - Structured data for job parameters passed to workers

## Architecture Position

```
FastAPI Route (HTTP)
        ↓
Controller (uses DTOs to validate requests)
        ↓
Service (uses DTOs for data structures)
        ↓
Worker (validates DTOs from job params)
        ↓
Redis Queue
```

DTOs form the contract between layers - ensuring type safety across the entire request/response cycle.

## File Organization

```
dtos/
├── __init__.py              # All DTOs exported here
├── api_response_dto.py      # Base response DTOs (already exists)
├── simulation_dto.py        # Simulation-specific DTOs (optional)
├── processing_dto.py        # Processing-specific DTOs (optional)
└── README.md
```

## Creating Request DTOs

Request DTOs validate HTTP input in API routes:

```python
from pydantic import BaseModel, Field
from typing import Optional

class SimulationRequest(BaseModel):
    """Request to enqueue a simulation job."""

    name: str = Field(..., min_length=1, max_length=255, description="Simulation name")
    iterations: int = Field(default=100, ge=1, le=10000, description="Number of iterations")
    timeout: int = Field(default=300, ge=10, le=3600, description="Job timeout in seconds")
    debug: Optional[bool] = Field(default=False, description="Enable debug mode")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "simulation_1",
                "iterations": 1000,
                "timeout": 600,
                "debug": False
            }
        }
```

## Creating Response DTOs

Response DTOs format HTTP output:

```python
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

class SimulationResponse(BaseModel):
    """Response with simulation job information."""

    job_id: str = Field(..., description="RQ job ID")
    status: str = Field(..., description="Job status (queued, started, succeeded, failed)")
    message: str = Field(..., description="Human-readable message")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SimulationResultResponse(BaseModel):
    """Response with simulation result."""

    job_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
```

## Using DTOs in Routes

```python
from fastapi import APIRouter, HTTPException
from app.lib.logging import get_logger
from app.controllers.simulation_controller import SimulationController
from app.dtos import SimulationRequest, SimulationResponse
from app.api.exceptions import APIException

logger = get_logger(__name__)
router = APIRouter(prefix="/simulations", tags=["simulations"])

@router.post("/", response_model=SimulationResponse)
async def enqueue_simulation(request: SimulationRequest) -> SimulationResponse:
    """
    Enqueue a new simulation job.

    - Request is auto-validated by Pydantic
    - Response fields are auto-serialized to JSON
    """
    try:
        logger.info(f"Route: Received simulation request - {request}")

        response = SimulationController.enqueue_simulation(request)

        logger.info(f"Route: Returning response")
        return SimulationResponse(**response)

    except APIException as e:
        logger.error(f"Route: API exception - {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Route: Unexpected error - {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Using DTOs in Controllers

Controllers use request DTOs to validate and pass data to services:

```python
from app.lib.logging import get_logger
from app.dtos import SimulationRequest
from app.services.simulation_service import SimulationService
from app.api.exceptions import ValidationError

logger = get_logger(__name__)

class SimulationController:
    @staticmethod
    def enqueue_simulation(request: SimulationRequest) -> dict:
        """Handle simulation enqueue."""
        try:
            logger.info(f"Controller: Processing request - {request.name}")

            # DTOs guarantee request is valid at this point
            job_id = SimulationService.enqueue_job(
                name=request.name,
                iterations=request.iterations,
                timeout=request.timeout,
                debug=request.debug
            )

            logger.info(f"Controller: Job enqueued - {job_id}")
            return {
                "job_id": job_id,
                "status": "queued",
                "message": f"Simulation {job_id} queued successfully"
            }

        except Exception as e:
            logger.error(f"Controller: Error - {str(e)}")
            raise
```

## Using DTOs in Services

Services use DTOs for structured data and type safety:

```python
from app.lib.logging import get_logger
from app.dtos import SimulationRequest
from app.configs import get_queue

logger = get_logger(__name__)

class SimulationService:
    @staticmethod
    def enqueue_job(name: str, iterations: int, timeout: int, debug: bool) -> str:
        """Enqueue simulation job."""
        try:
            logger.info(f"Service: Enqueueing job - {name}")

            q = get_queue()
            job = q.enqueue(
                'app.workers.simulation.process_simulation',
                name=name,
                iterations=iterations,
                timeout=timeout,
                debug=debug,
                job_timeout=f"{timeout}s"
            )

            logger.info(f"Service: Job created - {job.id}")
            return job.id

        except Exception as e:
            logger.error(f"Service: Error - {str(e)}")
            raise
```

## Using DTOs in Workers

Workers receive job parameters and can re-validate with DTOs:

```python
from app.lib.logging import get_logger
from app.dtos import SimulationRequest
from pydantic import ValidationError
from rq import current_job

logger = get_logger(__name__)

def process_simulation(name: str, iterations: int, timeout: int, debug: bool) -> dict:
    \"\"\"Execute simulation job.\"\"\"
    job = current_job()

    try:
        logger.info(f"Worker: Job {job.id} - Starting {name}")

        # Optional: Re-validate with DTO
        # request = SimulationRequest(name=name, iterations=iterations, timeout=timeout, debug=debug)

        # Process simulation...

        result = {"status": "success", "computed": iterations * 2}
        logger.info(f"Worker: Job {job.id} - Completed")
        return result

    except Exception as e:
        logger.error(f"Worker: Job {job.id} - Failed: {str(e)}")
        raise
```

## Validation Features

### Type Checking

```python
# ❌ This raises ValidationError (type mismatch)
request = SimulationRequest(
    name=123,              # Expected str, got int
    iterations=1000
)

# ✅ Valid request
request = SimulationRequest(
    name="simulation_1",
    iterations=1000
)
```

### Field Constraints

```python
from pydantic import Field

class ConfigDTO(BaseModel):
    iterations: int = Field(ge=1, le=10000, description="1 to 10000")
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
```

### Default Values & Optional

```python
from typing import Optional

class ConfigDTO(BaseModel):
    name: str                                    # Required
    timeout: int = 300                          # Default value
    debug: bool = False                         # Default false
    tags: list = Field(default_factory=list)    # Empty list default
    description: Optional[str] = None           # Optional (can be None)
```

## Testing DTOs

```python
from app.dtos import SimulationRequest
import pytest
from pydantic import ValidationError

def test_simulation_request_valid():
    """Test valid request."""
    request = SimulationRequest(
        name="test",
        iterations=100
    )
    assert request.name == "test"
    assert request.timeout == 300  # Default value

def test_simulation_request_invalid_type():
    """Test type validation."""
    with pytest.raises(ValidationError) as exc:
        SimulationRequest(name=123)  # Should be string
    errors = exc.value.errors()
    assert errors[0]['type'] == 'string_type'

def test_simulation_request_constraint():
    \"\"\"Test field constraints.\"\"\"
    with pytest.raises(ValidationError) as exc:
        SimulationRequest(iterations=50000)  # Max is 10000
    errors = exc.value.errors()
    assert 'less than or equal to' in str(errors)
```

## Common Patterns

### Nested DTOs

```python
from typing import List

class ProcessorConfig(BaseModel):
    name: str
    threads: int = 4

class SimulationRequest(BaseModel):
    name: str
    processors: List[ProcessorConfig]
```

### Union Types

```python
from typing import Union

class JobRequest(BaseModel):
    # Accept either string path or list of parameters
    config: Union[str, List[dict]]
```

### Custom Validators

```python
from pydantic import field_validator

class SimulationRequest(BaseModel):
    name: str
    iterations: int

    @field_validator('name')
    def name_must_be_lowercase(cls, v):
        if v != v.lower():
            raise ValueError('Must be lowercase')
        return v
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

## See Also

- [API Module](../api/README.md) - Complete endpoint creation with DTOs
- [Controllers Module](../controllers/README.md) - Using DTOs in orchestration
- [Services Module](../services/README.md) - Using DTOs in business logic
- [Workers Module](../workers/README.md) - Using DTOs in job handlers

## References

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pydantic Field Validation](https://docs.pydantic.dev/latest/concepts/fields/)
- [FastAPI Request Body](https://fastapi.tiangolo.com/tutorial/body/)
- [FastAPI Response Model](https://fastapi.tiangolo.com/tutorial/response_model/)
