# Services Module

Reusable business logic and service layer for shared operations.

## Purpose

This module provides:

- **Shared business logic** - Code used by both workers and API routes
- **External integrations** - Third-party API calls, email, notifications
- **Data transformations** - Complex processing independent of HTTP/workers
- **Service orchestration** - Coordinating multiple operations
- **Abstraction** - Hide implementation details behind clean interfaces

## When to Use Services

✅ **Use services for:**

- Logic shared between workers and API routes
- Complex data transformations and calculations
- External API integrations (payment, email, SMS, etc.)
- Business rule validations
- Multi-step workflows

❌ **Don't use services for:**

- Simple job enqueuing (do it in routes)
- Worker-only logic (keep in workers)
- HTTP-specific concerns (keep in routes)
- Data persistence (use repositories instead)

## Service Patterns

### 1. Stateless Service (Recommended)

```python
# app/services/__init__.py

class SimulationService:
    """Service for simulation operations."""

    @staticmethod
    def validate_config(config: SimulationConfig) -> dict:
        """Validate simulation configuration."""
        if config.timeout < 10:
            return {'valid': False, 'error': 'Timeout too low'}
        return {'valid': True}

    @staticmethod
    def calculate_metrics(data: dict) -> dict:
        """Calculate metrics from simulation data."""
        return {
            'mean': sum(data.values()) / len(data),
            'count': len(data)
        }
```

Use in routes:

```python
from app.services import SimulationService
from app.dtos import SimulationConfig

@router.post("/simulations")
async def enqueue_simulation(config: SimulationConfig):
    validation = SimulationService.validate_config(config)
    if not validation['valid']:
        raise HTTPException(status_code=400, detail=validation['error'])

    q = get_queue()
    job = q.enqueue('app.workers.simulation.process_simulation', config.dict())
    return {"job_id": job.id}
```

Use in workers:

```python
from app.services import SimulationService

def process_simulation(config_dict: dict) -> dict:
    config = SimulationConfig(**config_dict)

    # Use shared service logic
    validation = SimulationService.validate_config(config)
    if not validation['valid']:
        return {'status': 'failed', 'error': validation['error']}

    # ... process simulation ...
    metrics = SimulationService.calculate_metrics(results)

    return {
        'status': 'success',
        'metrics': metrics
    }
```

### 2. External Integration Service

```python
# app/services/__init__.py

class EmailService:
    """Service for sending emails."""

    @staticmethod
    def send_job_notification(job_id: str, status: str, email: str):
        """Send job status notification email."""
        subject = f"Job {job_id}: {status.upper()}"
        body = f"Your job {job_id} has {status}."

        # Call email provider
        return send_email(email, subject, body)

class NotificationService:
    """Service for notifications."""

    @staticmethod
    def notify_job_complete(job_id: str, result: dict):
        """Notify about job completion."""
        # Could send to Slack, Discord, webhook, etc.
        pass
```

### 3. Multi-Step Workflow Service

```python
# app/services/__init__.py

class WorkflowService:
    """Service for complex workflows."""

    @staticmethod
    def process_and_notify(config: SimulationConfig, user_email: str) -> dict:
        """Process simulation and notify user."""

        # Step 1: Validate
        if not SimulationService.validate_config(config)['valid']:
            return {'status': 'failed', 'error': 'Invalid config'}

        # Step 2: Enqueue job
        q = get_queue()
        job = q.enqueue(
            'app.workers.simulation.process_simulation',
            config.dict()
        )

        # Step 3: Send notification
        EmailService.send_job_notification(job.id, 'queued', user_email)

        return {'job_id': job.id, 'status': 'queued'}
```

## File Organization

```
services/
├── __init__.py           # All services exported here
├── simulation.py         # Simulation-related services (optional)
├── notification.py       # Notification services (optional)
└── external_api.py       # External API integrations (optional)
```

Or keep single file for simple projects:

```
services/
└── __init__.py           # All services in one file
```

## Service vs Controller vs Worker

| Layer          | Purpose                  | Used By       |
| -------------- | ------------------------ | ------------- |
| **Service**    | Reusable business logic  | Workers + API |
| **Controller** | Orchestration & workflow | API only      |
| **Worker**     | Job execution            | Queue only    |

```
API Route
    ↓
Controller (optional - orchestration)
    ↓
Service (shared logic)
    ↓
Worker execution
```

## Testing Services

```python
from app.services import SimulationService
import pytest

def test_validate_config():
    """Test config validation."""
    config = SimulationConfig(
        name="test",
        timeout=5  # Too low
    )
    result = SimulationService.validate_config(config)
    assert not result['valid']
    assert 'error' in result

def test_calculate_metrics():
    """Test metrics calculation."""
    data = {'a': 10, 'b': 20, 'c': 30}
    metrics = SimulationService.calculate_metrics(data)

    assert metrics['mean'] == 20
    assert metrics['count'] == 3
```

## Best Practices

✅ **Keep services stateless**

```python
class MyService:
    @staticmethod
    def do_something(data: dict) -> dict:
        # No instance state needed
        return process(data)
```

✅ **Use dependency injection for external deps**

```python
class EmailService:
    def __init__(self, provider: EmailProvider):
        self.provider = provider

    def send(self, email: str, subject: str, body: str):
        return self.provider.send(email, subject, body)
```

✅ **Type hints for clarity**

```python
from app.dtos import SimulationConfig

class SimulationService:
    @staticmethod
    def process(config: SimulationConfig) -> dict[str, any]:
        ...
```

❌ **Don't create service instances unnecessarily**

```python
# Bad
service = SimulationService()
result = service.validate(config)

# Good
result = SimulationService.validate(config)
```

❌ **Don't mix HTTP concerns in services**

```python
# Bad
class JobService:
    def get_job(self, job_id: str):
        from fastapi import HTTPException  # ❌ Don't import HTTP stuff
        ...

# Good
class JobService:
    def get_job(self, job_id: str) -> dict | None:
        # Return data, let route handle HTTP
        ...
```

## When Project is Small

If no shared logic yet, leave this module empty:

```python
# app/services/__init__.py
"""Business logic and service layer for shared operations."""
# Services will be added as needed
```

Then add services as project grows and you identify shared code.

## Common Services to Add Later

- `SimulationService` - Simulation validations and calculations
- `DataService` - Data transformations and processing
- `ExternalAPIService` - Third-party API integrations
- `NotificationService` - Email, Slack, webhook notifications
- `ReportService` - Report generation and exports
- `CacheService` - Caching logic if using Redis beyond queues

## Architecture

```
┌─────────────────────────────────────┐
│        API Routes (HTTP)             │
├─────────────────────────────────────┤
│    Controllers (Orchestration)       │
├─────────────────────────────────────┤
│   Services (Shared Business Logic)   │ ← You are here
├─────────────────────────────────────┤
│  Workers (Job Execution)             │
│  DTOs (Validation)                   │
│  Models (Data Persistence)           │
└─────────────────────────────────────┘
```

**Services bridge between API and Workers** by providing reusable business logic.
