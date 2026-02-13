# Workers Module

Job handlers for RQ (Redis Queue) - asynchronous task processing.

## Purpose

This module contains all **job handler functions** that the RQ worker process will execute when jobs are enqueued from upstream services (API gateway, scheduler, etc.).

## Structure

```
workers/
├── __init__.py
├── README.md (this file)
├── simulation.py      # Simulation-related job handlers
├── processing.py      # Other processing handlers
└── ...
```

## Writing Job Handlers

### Basic Template

```python
from rq import current_job
from pydantic import ValidationError
from app.dtos import SimulationConfig

def process_simulation(config_data: dict) -> dict:
    """
    Main job handler for simulation processing.

    Args:
        config_data: Simulation configuration dictionary

    Returns:
        Result dictionary with outcome

    Raises:
        ValidationError: If config_data is invalid
    """
    # Get job context for metadata tracking
    job = current_job()

    # Validate input with Pydantic
    try:
        config = SimulationConfig(**config_data)
    except ValidationError as e:
        job.set_status('failed')
        raise ValueError(f"Invalid config: {e}")

    # Update progress
    job.meta['status'] = 'initializing'
    job.meta['progress'] = 0
    job.save_meta()

    # Simulate work
    for i in range(100):
        # ... processing logic ...
        job.meta['progress'] = i
        job.save_meta()

    job.meta['status'] = 'completed'
    job.save_meta()

    return {
        "status": "success",
        "result": {...},
        "timestamp": datetime.now().isoformat()
    }
```

## Key Patterns

### 1. Job Context Access

```python
from rq import current_job

job = current_job()
job.meta['progress'] = 50
job.save_meta()
```

### 2. Input Validation with Pydantic

```python
from app.dtos import SimulationConfig

def handle_job(config_dict: dict):
    config = SimulationConfig(**config_dict)  # Validates here
    # ... use config.field_name ...
```

### 3. Progress Tracking

```python
job.meta['progress'] = 10  # 0-100%
job.meta['status'] = 'processing'
job.save_meta()
```

### 4. Error Handling

```python
try:
    # ... logic ...
except Exception as e:
    job.set_status('failed')
    job.exc_info = str(e)
    raise
```

## Naming Convention

- Function names: `process_[feature]`, `handle_[feature]`, `execute_[feature]`
- File names: `feature_name.py` (underscore-separated)
- One feature module per file for clarity

## Async Support

RQ supports async handlers (requires `async-timeout` dependency):

```python
async def process_simulation_async(config: dict) -> dict:
    """Async job handler."""
    job = current_job()
    # ... async work ...
    return result
```

## Testing

Mock the job context in tests:

```python
from unittest.mock import patch, MagicMock

def test_process_simulation():
    mock_job = MagicMock()
    with patch('rq.current_job', return_value=mock_job):
        result = process_simulation({"param": "value"})
        assert result["status"] == "success"
```

## Enqueuing (Upstream)

Jobs are enqueued from external services, not from this module:

```python
# In API gateway or scheduler (EXTERNAL SERVICE)
from rq import Queue
from redis import Redis

redis = Redis()
q = Queue(connection=redis)
job = q.enqueue(
    'app.workers.simulation.process_simulation',
    config_data={'param': 'value'},
    job_timeout='10m',
    result_ttl=300
)
```

## Running Workers

```bash
# Start worker listening to default queue
rq worker

# Start worker with multiple jobs concurrently
rq worker -w 4  # 4 worker processes

# Start worker for specific queue
rq worker high priority low

# With logging
rq worker --verbose
```

## Troubleshooting

- **Job never executes**: Check Redis connection and queue name
- **Job fails silently**: Add logging in handlers, check RQ dashboard
- **Progress never updates**: Ensure `job.save_meta()` is called after `job.meta['field']` changes
- **Input validation errors**: Use Pydantic schemas to catch errors early
