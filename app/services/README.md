# Services Module

Reusable business logic layer for shared operations between controllers and workers.

## Purpose

This module provides:

- **Shared business logic** - Code used by both workers and controllers
- **External integrations** - Third-party API calls, email, notifications
- **Data transformations** - Complex processing independent of HTTP/workers
- **Service orchestration** - Coordinating multiple reusable operations
- **Abstraction** - Hide implementation details behind clean interfaces

## Architecture Position

```
FastAPI Route (HTTP)
        ↓
Controller (orchestration + logging)
        ↓
Service (business logic + logging) ← Reusable by both Controller & Worker
        ↓
Worker (execution + logging)
        ↓
Redis Queue
```

Services contain pure business logic that can be called from multiple layers.

## When to Use Services

✅ **Use services for:**

- Logic shared between controllers and workers
- Complex data transformations and calculations
- Business rule validations
- External API integrations (payment, email, SMS, etc.)
- Database queries via repositories
- Multi-step workflows

❌ **Don't use services for:**

- HTTP concerns (keep in routes/controllers)
- Job enqueueing (keep in controllers)
- RQ job context access (keep in workers)
- Infrastructure setup (keep in configs)

## Service Patterns

### 1. Validation Service (Recommended)

```python
# app/services/simulation_service.py

from app.lib.logging import get_logger
from app.dtos import SimulationRequest

logger = get_logger(__name__)

class SimulationService:
    """Service for simulation operations."""

    @staticmethod
    def validate_config(request: SimulationRequest) -> bool:
        """Validate simulation configuration."""
        logger.info(f"Service: Validating config - {request.name}")

        if request.iterations < 1 or request.iterations > 10000:
            logger.error("Service: Invalid iteration count")
            return False

        if request.timeout < 10 or request.timeout > 3600:
            logger.error("Service: Invalid timeout")
            return False

        logger.info("Service: Configuration valid")
        return True

    @staticmethod
    def calculate_metrics(data: dict) -> dict:
        """Calculate metrics from result data."""
        logger.info(f"Service: Computing metrics from {len(data)} items")

        try:
            values = list(data.values())
            result = {
                'mean': sum(values) / len(values) if values else 0,
                'min': min(values) if values else 0,
                'max': max(values) if values else 0,
                'count': len(values)
            }

            logger.info(f"Service: Metrics computed - mean: {result['mean']}")
            return result

        except Exception as e:
            logger.error(f"Service: Error computing metrics - {str(e)}")
            raise
```

### 2. External Integration Service

```python
# app/services/notification_service.py

from app.lib.logging import get_logger

logger = get_logger(__name__)

class NotificationService:
    """Service for external notifications."""

    @staticmethod
    def send_job_status(job_id: str, status: str, email: str) -> bool:
        """Send job status notification."""
        logger.info(f"Service: Sending notification - Job {job_id} status {status}")

        try:
            # TODO: Implement email sending
            # send_email(email, subject, body)

            logger.info(f"Service: Notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Service: Failed to send notification - {str(e)}")
            raise
```

### 3. Data Transformation Service

```python
# app/services/processing_service.py

from app.lib.logging import get_logger
from app.dtos import SimulationRequest

logger = get_logger(__name__)

class ProcessingService:
    """Service for data processing."""

    @staticmethod
    def prepare_job_params(request: SimulationRequest) -> dict:
        """Transform request DTO to job parameters."""
        logger.info(f"Service: Preparing job params - {request.name}")

        params = {
            'name': request.name,
            'iterations': request.iterations,
            'timeout': request.timeout,
            'debug': request.debug
        }

        logger.info(f"Service: Parameters prepared")
        return params

    @staticmethod
    def process_result(job_result: dict, metadata: dict) -> dict:
        """Process and enrich job result."""
        logger.info(f"Service: Processing job result")

        return {
            'final_result': job_result,
            'processed_at': metadata.get('timestamp'),
            'duration': metadata.get('duration')
        }
```

## Using Services in Controllers

```python
# app/controllers/simulation_controller.py

from app.lib.logging import get_logger
from app.services.simulation_service import SimulationService
from app.services.processing_service import ProcessingService
from app.dtos import SimulationRequest
from app.api.exceptions import ValidationError

logger = get_logger(__name__)

class SimulationController:
    """Orchestrate simulation operations."""

    @staticmethod
    def enqueue_simulation(request: SimulationRequest) -> dict:
        """Handle simulation enqueue request."""
        try:
            logger.info(f"Controller: Processing enqueue request")

            # Step 1: Validate using service
            if not SimulationService.validate_config(request):
                logger.error("Controller: Validation failed")
                raise ValidationError("Invalid simulation configuration")

            # Step 2: Prepare parameters using service
            params = ProcessingService.prepare_job_params(request)

            # Step 3: Enqueue to appropriate queue based on job type
            logger.info(f"Controller: Enqueueing job")
            
            # Use JobType to route to correct worker pool
            from app.configs import JobType, enqueue_job
            
            # For heavy processing (large simulations)
            if request.iterations > 5000:
                logger.info(f"Controller: Routing to heavy queue (high iteration count)")
                job = enqueue_job(
                    'app.workers.simulation.process_simulation',
                    job_type=JobType.HEAVY,
                    **params
                )
            # For light processing (quick simulations)
            else:
                logger.info(f"Controller: Routing to light queue")
                job = enqueue_job(
                    'app.workers.simulation.process_simulation',
                    job_type=JobType.LIGHT,
                    **params
                )

            logger.info(f"Controller: Job enqueued - {job.id}")
            return {
                'job_id': job.id,
                'status': 'queued',
                'message': f"Simulation {job.id} queued"
            }

        except Exception as e:
            logger.error(f"Controller: Error - {str(e)}")
            raise
```
```

## Using Services in Workers

```python
# app/workers/simulation.py

from app.lib.logging import get_logger
from app.services.simulation_service import SimulationService
from app.services.processing_service import ProcessingService
from pydantic import ValidationError
from rq import current_job

logger = get_logger(__name__)

def process_simulation(name: str, iterations: int, timeout: int, debug: bool) -> dict:
    """Execute simulation job using services."""
    job = current_job()

    try:
        logger.info(f"Worker: Job {job.id} - Starting simulation {name}")

        # Use services for business logic
        metrics_data = {}
        for i in range(iterations):
            if debug:
                logger.debug(f"Worker: Iteration {i}")
            # Simulate work...
            metrics_data[f'iteration_{i}'] = i * 2

        # Calculate metrics using service
        metrics = SimulationService.calculate_metrics(metrics_data)

        # Process result using service
        result = ProcessingService.process_result(
            metrics,
            {'timestamp': str(now), 'duration': duration}
        )

        logger.info(f"Worker: Job {job.id} - Completed successfully")
        return {'status': 'success', 'result': result}

    except Exception as e:
        logger.error(f"Worker: Job {job.id} - Failed: {str(e)}")
        raise
```

## File Organization

```
services/
├── __init__.py                      # Service exports
├── simulation_service.py            # Simulation business logic
├── processing_service.py            # Data processing
├── notification_service.py          # External notificationsand integrations
└── README.md
```

`app/services/__init__.py`:

```python
"""Business logic services layer."""

from app.services.simulation_service import SimulationService
from app.services.processing_service import ProcessingService
from app.services.notification_service import NotificationService

__all__ = [
    "SimulationService",
    "ProcessingService",
    "NotificationService",
]
```

## Layer Responsibilities

| Layer          | Responsibility                    | Uses DTOs | Uses Logging | Uses Config |
| -------------- | --------------------------------- | --------- | ------------ | ----------- |
| **Route**      | HTTP input/output                 | ✅        | ✅           | -           |
| **Controller** | Orchestration + error mapping     | ✅        | ✅           | ✅          |
| **Service**    | Reusable business logic           | ✅        | ✅           | ✅          |
| **Worker**     | Job execution + progress tracking | ✅        | ✅           | ✅          |

## Logging Pattern

Services should log at important steps:

```python
from app.lib.logging import get_logger

logger = get_logger(__name__)

class MyService:
    @staticmethod
    def do_work(data: dict) -> dict:
        logger.info(f"Service: Starting work - {data.get('id')}")

        try:
            # Process...
            logger.info(f"Service: Work completed")
            return result

        except Exception as e:
            logger.error(f"Service: Error - {str(e)}")
            raise
```

## Testing Services

Services are easy to test because they're stateless:

```python
from app.services import SimulationService
from app.dtos import SimulationRequest
import pytest

def test_validate_config_valid():
    """Test config validation passes."""
    request = SimulationRequest(
        name="test",
        iterations=100,
        timeout=300
    )
    assert SimulationService.validate_config(request) is True

def test_validate_config_invalid_iterations():
    """Test config validation fails."""
    request = SimulationRequest(
        name="test",
        iterations=50000,  # Too high
        timeout=300
    )
    assert SimulationService.validate_config(request) is False

def test_calculate_metrics():
    """Test metrics calculation."""
    data = {'a': 10, 'b': 20, 'c': 30}
    metrics = SimulationService.calculate_metrics(data)

    assert metrics['mean'] == 20
    assert metrics['min'] == 10
    assert metrics['max'] == 30
    assert metrics['count'] == 3
```

## Best Practices

✅ **Use logging at key steps**

```python
logger.info(f"Service: Step description - Details")
logger.error(f"Service: Error description - Details")
```

✅ **Keep services stateless**

```python
class MyService:
    @staticmethod  # No instance state
    def do_work(data: dict) -> dict:
        return process(data)
```

✅ **Use dependency injection**

```python
class EmailService:
    def __init__(self, provider: EmailProvider):
        self.provider = provider  # Injected
```

✅ **Type hints for clarity**

```python
from app.dtos import SimulationRequest

@staticmethod
def validate(request: SimulationRequest) -> bool:
    ...
```

❌ **Avoid HTTP concerns in services**

```python
# Bad - HTTP in service
class JobService:
    def get_job(self):
        raise HTTPException(...)  # ❌

# Good - Return data, let controller handle HTTP
class JobService:
    def get_job(self) -> dict | None:
        return job_data
```

❌ **Avoid infrastructure code in services**

```python
# Bad
class MyService:
    def work(self):
        redis = Redis()  # ❌ Infrastructure

# Good
class MyService:
    def work(self):
        redis = get_redis_client()  # Use config
```

## When Project is Small

If no shared logic yet, leave this module empty:

```python
# app/services/__init__.py
"""Business logic and service layer for shared operations."""
# Services will be added as needed
```

Then add services as project grows and you identify shared code.

## See Also

- [API Module](../api/README.md) - Routes calling controllers
- [Controllers Module](../controllers/README.md) - orchestrating services
- [DTOs Module](../dtos/README.md) - Request/response validation
- [Workers Module](../workers/README.md) - Workers using services
