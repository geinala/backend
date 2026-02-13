# Configs Module

Configuration management and Redis connection setup for the worker service.

## Purpose

This module handles all application configuration including:

- **Environment variables** - Redis, RQ, and API settings
- **Redis connection** - Singleton pattern for Redis client and Queue instances
- **Singleton pattern** - Thread-safe initialization with lazy loading

## Files

### `environment_configuration.py`

Pydantic-based settings for environment variables.

```python
from app.configs import get_environment_configuration

settings = get_environment_configuration()
print(settings.REDIS_HOST)      # localhost
print(settings.RQ_QUEUE)         # default
print(settings.ENVIRONMENT)      # development
```

**Key Settings:**

- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`
- RQ: `RQ_QUEUE`, `RQ_JOB_TIMEOUT`, `RQ_RESULT_TTL`
- API: `API_HOST`, `API_PORT`, `API_TITLE`, `API_VERSION`
- Environment: `ENVIRONMENT`, `DEBUG`

### `redis_configuration.py`

Singleton Redis client and RQ Queue management with thread-safe initialization.

```python
from app.configs import get_redis_client, get_queue, get_redis_config

# Get singleton Redis client
redis = get_redis_client()
redis.ping()  # Check connection

# Get singleton RQ Queue
q = get_queue()  # Default queue
q_high = get_queue("high_priority")  # Custom queue

# Or access via RedisConfig singleton
config = get_redis_config()
config.is_connected()  # Check connection health
config.close()  # Graceful shutdown
```

**Features:**

- ✅ **Thread-safe singleton** - Only one instance across the app
- ✅ **Lazy initialization** - Connection created on first access
- ✅ **Connection pooling** - Socket keepalive and health checks
- ✅ **Custom queues** - Support multiple queue names
- ✅ **Graceful shutdown** - `close()` method for cleanup

## Usage

### In Workers

```python
from app.configs import get_redis_client, get_queue

def my_job():
    redis = get_redis_client()
    q = get_queue()

    # Use redis/queue in job...
    result = redis.get('some_key')
    return result
```

### In API Routes

```python
from fastapi import APIRouter
from app.configs import get_redis_client, get_queue

router = APIRouter()

@router.get("/status")
def health_check():
    redis = get_redis_client()
    return {"connected": redis.ping()}
```

## Environment Variables

Create `.env` file in project root:

```env
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# RQ
RQ_QUEUE=default
RQ_JOB_TIMEOUT=10m
RQ_RESULT_TTL=300

# API
API_HOST=0.0.0.0
API_PORT=8000
API_TITLE=Simulation App Solver
API_VERSION=1.0.0

# Environment
ENVIRONMENT=development
DEBUG=true
```

## Type Safety (Pylance Strict Mode)

All type hints are strict-mode compatible:

```python
# ✅ Type-safe
from app.configs import get_environment_configuration, get_redis_client

settings = get_environment_configuration()  # type: EnvironmentConfiguration
redis = get_redis_client()  # type: Redis
```

## Testing

Mock Redis in tests:

```python
from unittest.mock import patch, MagicMock

def test_my_job():
    with patch('app.configs.get_redis_client') as mock_redis:
        mock_redis.return_value = MagicMock()
        # Test job...
```

## Architecture

```
EnvironmentConfiguration (Pydantic)
        ↓
get_environment_configuration() (cached)
        ↓
RedisConfig (Singleton)
        ↓
get_redis_client() / get_queue()
```

**Design principles:**

- Single responsibility - Each module handles one concern
- Lazy loading - Resources created on first access
- Thread safety - Lock-based singleton pattern
- Type safety - Full type hints for Pylance strict mode
