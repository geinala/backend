# Controllers Module

Business logic layer for handling API requests.

## Purpose

This module separates business logic from API routes:

- **Controllers** - Handle business logic and orchestration
- **Routes** - Handle HTTP concerns only (request/response)
- **Cleanness** - Keep routes thin and focused on HTTP

## Architecture Pattern

```
API Request
    ↓
Route Handler (app/api/routes.py)
    ↓
Controller (app/controllers/)
    ↓
Business Logic (workers, services, etc.)
    ↓
Response
```

## When to Use Controllers

Use controllers when:

- You have complex business logic in multiple steps
- Logic is shared across multiple routes
- You want to keep routes clean and readable

Simple jobs don't need controllers - enqueue directly from routes:

```python
@router.post("/hello-world")
async def enqueue_hello_world():
    q = get_queue()
    job = q.enqueue('app.workers.hello_world.hello_world')
    return JobResponse(job_id=job.id, status="queued", message="OK")
```

## Controller Example

```python
# app/controllers/__init__.py

from app.configs import get_queue

class SimulationController:
    """Controller for simulation job orchestration."""

    @staticmethod
    def enqueue_simulation(config: dict) -> dict:
        """
        Enqueue a simulation job.

        Args:
            config: Simulation configuration

        Returns:
            dict with job_id and status
        """
        q = get_queue()
        job = q.enqueue(
            'app.workers.simulation.process_simulation',
            config,
            job_timeout='30m'
        )
        return {
            'job_id': job.id,
            'status': 'queued'
        }
```

Then use in routes:

```python
from app.controllers import SimulationController

@router.post("/simulations")
async def enqueue_simulation(request: SimulationRequest):
    result = SimulationController.enqueue_simulation(request.dict())
    return SimulationResponse(**result)
```

## File Organization

When controllers are needed:

```
controllers/
├── __init__.py
├── simulation_controller.py
└── processing_controller.py
```

Import pattern:

```python
from app.controllers import SimulationController, ProcessingController
```

## Design Principles

- **Single Responsibility** - One controller per domain
- **Testability** - Logic is separate from HTTP layer
- **Reusability** - Controllers can be used by multiple routes or CLI
- **Simplicity** - Don't over-engineer simple workflows

For now, this directory is a placeholder for future use.
