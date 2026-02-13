# Core Module

Configuration, environment setup, and shared utilities.

## Purpose

This module provides:
- **Configuration Management**: Settings from environment variables (`.env`)
- **Redis Connection**: Singleton Redis client instance
- **RQ Queue Setup**: Job queue initialization
- **Common Utilities**: Shared helper functions

## Structure

```
core/
├── __init__.py       # Redis & Queue helpers
├── config.py         # Settings & environment
└── README.md
```

## Configuration (config.py)

Uses `pydantic-settings` for environment-based configuration.

### Environment Variables

Create a `.env` file in the project root:

```env
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=           # Optional

# RQ Job Queue
RQ_QUEUE=default
RQ_JOB_TIMEOUT=10m
RQ_RESULT_TTL=300

# FastAPI (Health checks)
API_HOST=0.0.0.0
API_PORT=8000

# Environment
ENVIRONMENT=development
```

### Accessing Settings

```python
from app.core.config import get_settings

settings = get_settings()  # Cached singleton
print(settings.REDIS_HOST)
print(settings.redis_url)  # Returns formatted Redis URL
```

## Redis Connection (\_\_init\_\_.py)

### Get Redis Client

```python
from app.core import get_redis_connection

redis_client = get_redis_connection()
redis_client.set('key', 'value')
```

### Get RQ Queue

```python
from app.core import get_queue

q = get_queue()  # Uses default queue name from settings
q.enqueue(job_function, args=(arg1, arg2))

# Or specific queue
q_priority = get_queue('high_priority')
```

## Usage in Job Handlers

```python
# In app/workers/simulation.py
from app.core import get_redis_connection
from app.core.config import get_settings

def process_simulation(config: dict):
    settings = get_settings()
    redis = get_redis_connection()
    
    # Use settings
    timeout = settings.RQ_JOB_TIMEOUT
    
    # Access Redis directly if needed
    redis.incr('simulation:count')
    
    return {"result": "success"}
```

## Docker & Production

For containerized deployment:

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync

# Start worker
CMD ["rq", "worker"]
# Or with config
CMD ["rq", "worker", "-u", "redis://redis:6379"]
```

Environment variables can be injected via `docker-compose.env` or Kubernetes secrets.

## Testing

Mock settings in tests:

```python
from unittest.mock import patch
from app.core.config import Settings

def test_with_mock_settings():
    mock_settings = Settings(
        REDIS_HOST="test-redis",
        DEBUG=True
    )
    with patch('app.core.config.get_settings', return_value=mock_settings):
        # ... test code ...
```
