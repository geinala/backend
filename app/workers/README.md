# Workers Module

Job handler functions for RQ (Redis Queue) - asynchronous task execution layer.

## Purpose

This module contains **job handler functions** that execute when jobs are enqueued from controllers or services.

- **Long-running tasks** - Offload CPU/IO-bound work from HTTP layer
- **Background processing** - Execute asynchronously via Redis queue
- **Scalability** - Run multiple worker processes for parallel execution
- **Logging** - Track job progress and results

## Architecture Position

```
FastAPI Route (HTTP)
        ↓
Controller (orchestration)
        ↓
Service (business logic)
        ↓
Worker (execution) ← You are here
        ↓
        Redis Queue (message broker)
```

Workers execute jobs enqueued by controllers/services and use services for shared business logic.

## File Organization

```
workers/
├── __init__.py              # Worker exports
├── simulation.py            # Simulation job handlers
├── processing.py            # Processing job handlers
└── README.md
```

`app/workers/__init__.py`:

```python
"""Background job handlers for RQ."""

# Note: Individual job functions are in their respective modules
# Import pattern: from app.workers.simulation import process_simulation
# RQ will discover handlers via the module path
```

## Writing Job Handlers

### Basic Template with Logging

```python
# app/workers/simulation.py

from app.lib.logging import get_logger
from pydantic import ValidationError
from rq import current_job

logger = get_logger(__name__)

def process_simulation(name: str, iterations: int, timeout: int, debug: bool) -> dict:
    \"\"\"
    Main job handler for simulation processing.

    Called by: SimulationController via q.enqueue()
    Uses: SimulationService for business logic

    Args:
        name: Simulation name
        iterations: Number of iterations
        timeout: Job timeout in seconds
        debug: Enable debug output

    Returns:
        Result dictionary with status and outcome

    Raises:
        Exception: On unrecoverable errors (RQ will capture and mark as failed)
    \"\"\"
    job = current_job()

    try:
        logger.info(f"Worker: Job {job.id} - Starting simulation {name}")

        # Step 1: Validate inputs (optional - controller should validate too)
        if iterations < 1 or iterations > 10000:
            logger.error(f"Worker: Job {job.id} - Invalid iterations: {iterations}")
            raise ValueError(f"Iterations must be 1-10000, got {iterations}")

        # Step 2: Initialize job metadata
        job.meta['status'] = 'initializing'
        job.meta['progress'] = 0
        job.save_meta()
        logger.info(f"Worker: Job {job.id} - Initialized")

        # Step 3: Use services for business logic
        from app.services import SimulationService

        # Simulate work with progress tracking
        job.meta['status'] = 'processing'
        results = {}

        for i in range(iterations):
            # Simulate work...
            result = i * 2
            results[f'iteration_{i}'] = result

            # Update progress every 10%
            if (i + 1) % max(1, iterations // 10) == 0:
                progress = int((i + 1) / iterations * 100)
                job.meta['progress'] = progress
                job.save_meta()
                logger.info(f"Worker: Job {job.id} - Progress {progress}%")

        # Step 4: Calculate metrics using service
        logger.info(f"Worker: Job {job.id} - Calculating metrics")
        metrics = SimulationService.calculate_metrics(results)

        # Step 5: Return result
        result = {
            'status': 'success',
            'result': metrics,
            'iterations': iterations
        }

        job.meta['status'] = 'completed'
        job.meta['progress'] = 100
        job.save_meta()

        logger.info(f"Worker: Job {job.id} - Completed successfully")
        return result

    except ValidationError as e:
        logger.error(f"Worker: Job {job.id} - Validation error: {str(e)}")
        job.set_status('failed')
        raise

    except Exception as e:
        logger.error(f"Worker: Job {job.id} - Unexpected error: {str(e)}")
        job.set_status('failed')
        job.exc_info = str(e)
        raise
```

### Using Services in Workers

```python
# app/workers/processing.py

from app.lib.logging import get_logger
from app.services import ProcessingService, NotificationService
from rq import current_job

logger = get_logger(__name__)

def process_and_notify(job_data: dict, user_email: str) -> dict:
    \"\"\"
    Complex workflow using multiple services.
    \"\"\"
    job = current_job()

    try:
        logger.info(f"Worker: Job {job.id} - Starting process and notify")

        # Use service for processing
        processed = ProcessingService.process_data(job_data)
        logger.info(f"Worker: Job {job.id} - Processing complete")

        # Use service for notification (if it was successful)
        if processed['status'] == 'success':
            logger.info(f"Worker: Job {job.id} - Sending notification")
            NotificationService.send_job_status(job.id, 'completed', user_email)

        logger.info(f"Worker: Job {job.id} - Completed")
        return {'status': 'success', 'result': processed}

    except Exception as e:
        logger.error(f"Worker: Job {job.id} - Error: {str(e)}")
        raise
```

## Key Patterns

### 1. Job Context Access

```python
from rq import current_job

def my_job():
    job = current_job()
    job.meta['key'] = 'value'
    job.save_meta()

    # Access job ID, status, queue name, etc.
    print(job.id)  # RQ job ID
    print(job.get_status())  # Current status
    print(job.func_name)  # Handler function name
```

### 2. Progress Tracking

```python
def process_large_dataset(items: list) -> dict:
    job = current_job()

    for i, item in enumerate(items):
        # Process item...

        # Update progress every 10% to reduce Redis calls
        if (i + 1) % max(1, len(items) // 10) == 0:
            job.meta['progress'] = int((i + 1) / len(items) * 100)
            job.meta['items_processed'] = i + 1
            job.save_meta()

    return {'status': 'success', 'total_items': len(items)}
```

### 3. Logging with Job ID

```python
from app.lib.logging import get_logger
from rq import current_job

logger = get_logger(__name__)

def my_job(param: str):
    job = current_job()

    # Always include job ID in logs
    logger.info(f"Worker: Job {job.id} - Processing param: {param}")

    try:
        result = do_work(param)
        logger.info(f"Worker: Job {job.id} - Success")
        return result
    except Exception as e:
        logger.error(f"Worker: Job {job.id} - Error: {str(e)}")
        raise
```

### 4. Error Handling

```python
from rq import current_job

def my_job(data: dict) -> dict:
    job = current_job()

    try:
        # Main logic
        result = process(data)
        return result

    except ValueError as e:
        logger.warning(f"Worker: Job {job.id} - Invalid value: {str(e)}")
        job.set_status('failed')
        raise  # RQ will capture and retry if configured

    except Exception as e:
        logger.error(f"Worker: Job {job.id} - Unexpected error: {str(e)}")
        job.set_status('failed')
        job.exc_info = str(e)  # Store error info
        raise
```

### 5. Using DTOs for Validation

```python
from app.dtos import SimulationRequest
from pydantic import ValidationError
from rq import current_job

logger = get_logger(__name__)

def process_simulation(name: str, iterations: int) -> dict:
    job = current_job()

    try:
        # Optional: Re-validate with DTO
        # request = SimulationRequest(name=name, iterations=iterations)
        # This ensures we have correct types throughout the worker

        logger.info(f"Worker: Job {job.id} - Processing {name}")
        # ... process ...

    except ValidationError as e:
        logger.error(f"Worker: Job {job.id} - Validation error")
        raise
```

## Naming Conventions

- **Function names**: `process_[feature]`, `handle_[feature]`, `execute_[feature]`
- **File names**: `feature_name.py` (underscore-separated)
- **One feature per file** for clarity

## Async Support

RQ supports async handlers:

```python
async def process_simulation_async(name: str) -> dict:
    \"\"\"Async job handler.\"\"\"
    job = current_job()

    logger.info(f"Worker: Job {job.id} - Async processing")
    # ... await async operations ...

    return {'status': 'success'}
```

Requires `async-timeout` dependency.

## Running Workers

### Single Worker

```bash
# Default queue
rq worker

# Specific queue
rq worker high_priority

# With verbose logging
rq worker --verbose

# With custom log level
rq worker --log-level DEBUG
```

### Multiple Workers (Local)

```bash
# Terminal 1
rq worker

# Terminal 2
rq worker

# Terminal 3
rq worker
```

### Docker Scaling

```bash
# Scale to 3 workers
docker-compose up -d --scale worker=3

# Scale to 5
docker-compose up -d --scale worker=5

# View logs
docker-compose logs -f worker
```

## Enqueuing Jobs

Jobs are enqueued from controllers, not from this module:

```python
# app/controllers/simulation_controller.py

from app.configs import get_queue

class SimulationController:
    @staticmethod
    def enqueue_simulation(request: SimulationRequest) -> dict:
        q = get_queue()
        job = q.enqueue(
            'app.workers.simulation.process_simulation',  # Function path
            name=request.name,                            # Function args
            iterations=request.iterations,
            timeout=request.timeout,
            debug=request.debug,
            job_timeout='30m'                             # RQ timeout
        )
        return {'job_id': job.id}
```

## Testing Workers

Mock the job context:

```python
from unittest.mock import patch, MagicMock
from app.workers.simulation import process_simulation

def test_process_simulation():
    \"\"\"Test worker handler.\"\"\"
    mock_job = MagicMock()
    mock_job.id = 'test-job-123'

    with patch('rq.current_job', return_value=mock_job):
        result = process_simulation(
            name='test',
            iterations=100,
            timeout=300,
            debug=False
        )

    assert result['status'] == 'success'
    assert result['iterations'] == 100

    # Verify progress was updated
    mock_job.save_meta.assert_called()
```

## Common Patterns

### Pattern: Work with Database

```python
from app.configs.database_configuration import DatabaseConfiguration
from app.repositories import SimulationRepository
from rq import current_job

logger = get_logger(__name__)

def process_simulation(sim_id: int) -> dict:
    job = current_job()

    try:
        logger.info(f"Worker: Job {job.id} - Fetching simulation {sim_id}")

        # Get database connection
        db_config = DatabaseConfiguration()
        # engine = create_engine(db_config.database_url)
        # repository = SimulationRepository(engine)
        # sim = repository.get_by_id(sim_id)

        logger.info(f"Worker: Job {job.id} - Processing simulation")
        # ... process ...

        logger.info(f"Worker: Job {job.id} - Updating database")
        # repository.update_status(sim_id, 'completed')

        return {'status': 'success'}

    except Exception as e:
        logger.error(f"Worker: Job {job.id} - Error: {str(e)}")
        raise
```

### Pattern: Distributed Task

```python
from app.lib.logging import get_logger
from rq import current_job

logger = get_logger(__name__)

def process_batch(items: list, processor_name: str) -> dict:
    \"\"\"Process batch of items.\"\"\"
    job = current_job()

    logger.info(f"Worker: Job {job.id} ({processor_name}) - Processing {len(items)} items")

    results = []
    for i, item in enumerate(items):
        # Process item...
        results.append(item)

        # Update progress
        progress = int((i + 1) / len(items) * 100)
        job.meta['progress'] = progress
        job.meta['items_processed'] = i + 1
        job.save_meta()

    logger.info(f"Worker: Job {job.id} - Completed {len(results)} items")
    return {'status': 'success', 'items_processed': len(results)}
```

## Troubleshooting

- **Job never executes**: Check Redis connection and queue name
- **Job fails silently**: Add logging in handlers, check RQ dashboard
- **Progress never updates**: Ensure `job.save_meta()` is called after `job.meta['field']` changes
- **Input validation errors**: Use Pydantic schemas to catch errors early

## See Also

- [API Module](../api/README.md) - Routes enqueuing jobs
- [Controllers Module](../controllers/README.md) - Orchestrating job
- [Services Module](../services/README.md) - Business logic called by workers
- [DTOs Module](../dtos/README.md) - Validation for job parameters
