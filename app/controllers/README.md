# Controllers Module

Orchestration layer that bridges API routes and business services.

This module handles request orchestration and validation between your HTTP layer and business logic:

- **Orchestration** - Coordinate multiple services for complex workflows
- **Validation** - Validate and transform request data
- **Error Mapping** - Convert business exceptions to API exceptions
- **Logging** - Track request flow through controllers

## Architecture Flow

Follow this architecture when creating controllers:

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

## When to Use Controllers

Use controllers when you have:

- **Complex multi-step workflows** with multiple services involved that need orchestration and error handling across services
- **Business validation** including domain-specific validation, configuration processing, and data transformation
- **Shared logic across routes** used by multiple endpoints, CLI commands, or health checks

Don't use controllers for simple jobs. Instead, enqueue directly from routes:

```python
# Good for simple cases
from app.api.jobs import router
from app.configs import get_queue

@router.post("/hello-world")
async def enqueue_hello_world():
    q = get_queue()
    job = q.enqueue('app.workers.hello_world.hello_world')
    return JobResponse(job_id=job.id, status="queued", message="OK")
```

## Complete Example with Logging

Follow this example to implement controllers with proper logging:

### Step 1: Create Service

Create your business logic in `app/services/simulation_service.py`:

```python
from app.lib import get_logger
from app.configs import get_queue

logger = get_logger(__name__)

class SimulationService:
    """Business logic for simulation operations."""

    @staticmethod
    def validate_config(config: dict) -> bool:
        """Validate simulation configuration."""
        logger.info(f"Service: Validating config - {config}")

        required_fields = ['name', 'iterations', 'timeout']
        if not all(field in config for field in required_fields):
            logger.error("Service: Missing required configuration fields")
            return False

        logger.info("Service: Configuration validated successfully")
        return True

    @staticmethod
    def enqueue_simulation(config: dict) -> str:
        """Enqueue simulation job and return job ID."""
        try:
            logger.info(f"Service: Enqueueing simulation with config - {config}")

            q = get_queue()
            job = q.enqueue(
                'app.workers.simulation.process_simulation',
                config=config,
                job_timeout='30m'
            )

            logger.info(f"Service: Simulation enqueued successfully - Job ID: {job.id}")
            return job.id
        except Exception as e:
            logger.error(f"Service: Failed to enqueue simulation - {str(e)}")
            raise
```

### Step 2: Create Controller

In `app/controllers/simulation_controller.py`:

```python
from app.lib import get_logger
from app.services.simulation_service import SimulationService
from app.api.exceptions import ValidationError, JobEnqueueError
from app.dtos import SimulationRequest

logger = get_logger(__name__)

class SimulationController:
    """Orchestrate simulation operations between routes and services."""

    @staticmethod
    def enqueue_simulation(request: SimulationRequest) -> dict:
        """
        Handle simulation enqueue request with full orchestration.

        Args:
            request: Simulation request DTO

        Returns:
            dict with job_id and status

        Raises:
            ValidationError: If configuration invalid
            JobEnqueueError: If enqueueing fails
        """
        try:
            logger.info(f"Controller: Processing simulation request - {request}")

            # Step 1: Validate configuration
            config = request.dict()
            if not SimulationService.validate_config(config):
                logger.error("Controller: Configuration validation failed")
                raise ValidationError(
                    "Invalid simulation configuration",
                    fields={"config": "Missing required fields"}
                )

            # Step 2: Enqueue job
            logger.info("Controller: Configuration valid, enqueueing job")
            job_id = SimulationService.enqueue_simulation(config)

            # Step 3: Return response
            response = {
                'job_id': job_id,
                'status': 'queued',
                'message': f'Simulation {job_id} queued successfully'
            }

            logger.info(f"Controller: Simulation request processed - {response}")
            return response

        except ValidationError as e:
            logger.warning(f"Controller: Validation error - {e.message}")
            raise
        except Exception as e:
            logger.error(f"Controller: Unexpected error - {str(e)}")
            raise JobEnqueueError("Failed to enqueue simulation", str(e))
```

### Step 3: Use in Routes

In `app/api/simulations.py`:

```python
from fastapi import APIRouter, HTTPException
from app.lib import get_logger
from app.controllers.simulation_controller import SimulationController
from app.dtos import SimulationRequest, SimulationResponse
from app.api.exceptions import APIException

logger = get_logger(__name__)
router = APIRouter(prefix="/simulations", tags=["simulations"])

@router.post("/", response_model=SimulationResponse)
async def enqueue_simulation(request: SimulationRequest):
    """Enqueue a new simulation job."""
    try:
        logger.info("Route: Received simulation enqueue request")

        response = SimulationController.enqueue_simulation(request)

        logger.info(f"Route: Returning simulation response - {response}")
        return SimulationResponse(**response)

    except APIException as e:
        logger.error(f"Route: API exception - {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Route: Unexpected error - {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

## File Organization

```
controllers/
├── __init__.py                      # Controller exports
├── simulation_controller.py         # Simulation orchestration
├── processing_controller.py         # Processing orchestration
└── README.md
```

`app/controllers/__init__.py`:

```python
"""Controllers for API request orchestration."""

from app.controllers.simulation_controller import SimulationController
from app.controllers.processing_controller import ProcessingController

__all__ = [
    "SimulationController",
    "ProcessingController",
]
```

## Best Practices

✅ **Use logging at every step**

```python
logger = get_logger(__name__)
logger.info(f"Controller: Step description - Details")
logger.warning(f"Controller: Warning - Details")
logger.error(f"Controller: Error - Details")
```

✅ **Map domain exceptions to API exceptions**

```python
from app.api.exceptions import ValidationError, JobEnqueueError

try:
    SimulationService.process()
except InvalidConfigError:
    raise ValidationError("Invalid configuration")
except Exception as e:
    raise JobEnqueueError("Processing failed", str(e))
```

✅ **Separate concerns - one controller per domain**

```python
# Good - Each domain has its own controller
class SimulationController: ...
class ProcessingController: ...
class ReportingController: ...

# Bad - One controller for everything
class MainController: ...
```

✅ **Use DTOs for validation**

```python
from pydantic import BaseModel

class SimulationRequest(BaseModel):
    """Request validation for simulation enqueue."""
    name: str
    iterations: int
    timeout: int = 300
```

✅ **Implement error handling strategy**

```python
try:
    # Orchestration steps
    logger.info("Step 1: Validate data")
    logger.info("Step 2: Process data")
    logger.info("Step 3: Enqueue job")
except SpecificError as e:
    logger.warning(f"Expected error: {e}")
    raise APIError(...)
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise ServerError(...)
```

❌ **Avoid mixing HTTP concerns**

```python
# Bad - HTTP in controller
class BadController:
    @staticmethod
    def process(response: Response):
        response.status_code = 201
        return response

# Good - Only business logic
class GoodController:
    @staticmethod
    def process(data: dict) -> dict:
        return {'result': data}
```

❌ **Avoid calling get_queue/Redis directly**

```python
# Bad - Infrastructure in controller
job = get_queue().enqueue('task')

# Good - Use service layer
job_id = SimulationService.enqueue_job(config)
```

## Integration Points

**With Routes:**

- Routes call controller methods
- Routes handle HTTP exceptions
- Routes format responses

**With Services:**

- Controllers call service methods
- Controllers handle service exceptions
- Controllers orchestrate multi-step workflows

**With Workers:**

- Services enqueue jobs to workers
- Controllers don't directly call workers
- Job execution happens asynchronously

## See Also

- [API Module Documentation](../api/README.md) - Full endpoint creation guide
- [Services Documentation](../services/README.md) - Business logic patterns
- [Exceptions Documentation](../api/exceptions/README.md) - Error handling
