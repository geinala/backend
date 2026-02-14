# Configs Module

Configuration management and Redis connection setup for your worker service.

This module handles all application configuration including:

- **Environment variables** - Redis, RQ, and API settings
- **Redis connection** - Singleton pattern for Redis client and Queue instances
- **Singleton pattern** - Thread-safe initialization with lazy loading

## Files

This module is organized as follows:

### environment_configuration.py

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

### redis_configuration.py

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

- Thread-safe singleton: Only one instance across the app
- Lazy initialization: Connection created on first access
- Connection pooling: Socket keepalive and health checks
- Custom queues: Support multiple queue names
- Graceful shutdown: `close()` method for cleanup

### database_configuration.py

Singleton database connection management using thread-safe initialization pattern.

```python
from app.configs.database_configuration import DatabaseConfiguration

# Get singleton database configuration
db_config = DatabaseConfiguration()
print(db_config.database_url)  # postgresql://user:pass@localhost:5432/db
```

**Features:**

- Thread-safe singleton: Only one instance across the app using `Lock`
- Lazy initialization: Database connection setup on first access
- Reusable pattern: Template for other singleton configurations
- Double-checked locking: Efficient thread-safe initialization

**How it works:**

1. `__new__` ensures only one instance is created (singleton pattern)
2. `_initialized` flag prevents re-initialization in `__init__`
3. `Lock` provides thread-safe access during initialization
4. Settings loaded from `EnvironmentConfiguration`

**Example Usage:**

```python
from app.configs.database_configuration import DatabaseConfiguration

# In services/workers
db_config = DatabaseConfiguration()
db_url = db_config.database_url

# Connect to database
# engine = create_engine(db_url)
```

**Database Connection Format:**

The database URL is constructed from environment variables:

```
postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}
```

Example from `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USERNAME=user
DB_PASSWORD=password
DB_NAME=simulation_db

# Results in:
# postgresql://user:password@localhost:5432/simulation_db
```

### `worker_configuration.py`

Queue and worker configuration for routing jobs to specialized worker pools.

Supports multiple queue types with different processing characteristics:

- **Heavy Queue**: CPU-intensive, long-running tasks (fewer workers, longer timeout)
- **Light Queue**: Quick, low-resource tasks (more workers, shorter timeout)
- **Default Queue**: Standard priority tasks

```python
from app.configs import (
    JobType,
    get_worker_config,
    get_queue_for_job,
    enqueue_job
)

# Route jobs to appropriate queue
job = enqueue_job(
    'app.workers.simulation.process_large_simulation',
    job_type=JobType.HEAVY,  # CPU-intensive job
    iterations=50000
)

# Or for quick tasks
job = enqueue_job(
    'app.workers.validation.validate_config',
    job_type=JobType.LIGHT,  # Quick job
    config={'name': 'test'}
)

# Get queue information
config = get_worker_config()
info = config.get_queue_info()
# {
#   'heavy': {'workers': 2, 'job_timeout': '30m', 'job_count': 5},
#   'light': {'workers': 4, 'job_timeout': '5m', 'job_count': 12},
#   'default': {'workers': 1, 'job_timeout': '10m', 'job_count': 3}
# }
```

**Features:**

- ✅ **Multiple queue types** - Heavy, Light, Default with different characteristics
- ✅ **Separate worker pools** - Different worker counts per queue type
- ✅ **Type-safe routing** - JobType enum for safe job routing
- ✅ **Singleton pattern** - Consistent configuration across the app
- ✅ **Queue monitoring** - Get statistics for all queues
- ✅ **Configurable** - All settings via environment variables

**Queue Characteristics:**

```
Heavy Queue:
  - Workers: 2 (fewer for CPU-intensive)
  - Timeout: 30 minutes (longer for heavy processing)
  - Result TTL: 1 hour
  - Use for: Simulations, data processing, heavy computations

Light Queue:
  - Workers: 4 (more for parallelism)
  - Timeout: 5 minutes (shorter for quick tasks)
  - Result TTL: 5 minutes
  - Use for: Validation, notifications, quick operations

Default Queue:
  - Workers: 1
  - Timeout: 10 minutes
  - Result TTL: 5 minutes
  - Use for: General purpose, standard priority jobs
```

## Usage

### In Workers

```python
from app.configs import get_redis_client, get_queue
from app.configs.database_configuration import DatabaseConfiguration

def my_job():
    # Redis and RQ
    redis = get_redis_client()
    q = get_queue()

    # Database
    db_config = DatabaseConfiguration()
    db_url = db_config.database_url

    # Use in job...
    result = redis.get('some_key')
    return result
```

### In API Routes

```python
from fastapi import APIRouter
from app.configs import get_redis_client, get_queue
from app.configs.database_configuration import DatabaseConfiguration

router = APIRouter()

@router.get("/status")
def health_check():
    redis = get_redis_client()
    db_config = DatabaseConfiguration()

    return {
        "redis_connected": redis.ping(),
        "database_url": db_config.database_url
    }
```

### In Services

```python
from app.configs import get_environment_configuration
from app.configs.database_configuration import DatabaseConfiguration

class MyService:
    def __init__(self):
        self.settings = get_environment_configuration()
        self.db_config = DatabaseConfiguration()

    def process(self):
        # Use settings
        environment = self.settings.ENVIRONMENT

        # Use database config
        db_url = self.db_config.database_url

        # ... business logic ...
```

## Environment Variables

Create `.env` file in project root:

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USERNAME=your_username
DB_PASSWORD=your_password
DB_NAME=your_database

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# RQ - Multiple Queues for Different Job Types
RQ_QUEUE=default
RQ_JOB_TIMEOUT=10m
RQ_RESULT_TTL=300

# Heavy Processing Queue (CPU-intensive, long-running tasks)
RQ_HEAVY_QUEUE=heavy
RQ_HEAVY_JOB_TIMEOUT=30m
RQ_HEAVY_RESULT_TTL=3600
RQ_HEAVY_WORKERS=2

# Light Processing Queue (Quick tasks, low resource)
RQ_LIGHT_QUEUE=light
RQ_LIGHT_JOB_TIMEOUT=5m
RQ_LIGHT_RESULT_TTL=300
RQ_LIGHT_WORKERS=4

# API
API_HOST=0.0.0.0
API_PORT=8000
API_TITLE=Simulation App Solver
API_VERSION=1.0.0

# CORS
CORS_ALLOW_ORIGINS=*
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
CORS_ALLOW_HEADERS=*

# API Documentation
ENABLE_DOCS=true
ENABLE_REDOC=true
ENABLE_OPENAPI=true

# Environment
ENVIRONMENT=development
DEBUG=true

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_FILE=app.log
LOG_BACKUP_COUNT=5
LOG_MAX_BYTES=10485760
ENABLE_FILE_LOGGING=false  # false = console-only (development), true = file + console (production)
```

## Using Multiple Job Queues

The application supports three job queues with different worker configurations for optimized job processing:

### Queue Types and Usage

```python
from app.lib.worker_configuration import JobType, enqueue_job

# Heavy Processing - CPU-intensive, long-running tasks
# Best for: Simulations, data processing, heavy computations
# Config: 2 workers, 30-minute timeout
heavy_job = enqueue_job(
    'app.workers.simulation.process_large_simulation',
    job_type=JobType.HEAVY,
    iterations=50000,
    algorithm='monte_carlo'
)

# Light Processing - Quick, low-resource tasks
# Best for: Validation, notifications, quick operations
# Config: 4 workers, 5-minute timeout
light_job = enqueue_job(
    'app.workers.validation.validate_config',
    job_type=JobType.LIGHT,
    config={'name': 'test'}
)

# Default - Standard priority tasks
# Best for: General purpose jobs, medium duration
# Config: 1 worker, 10-minute timeout
default_job = enqueue_job(
    'app.workers.standard.process',
    job_type=JobType.DEFAULT,
    data=params
)
```

### Running Workers for Different Queues

```bash
# Terminal 1: Process heavy jobs (2 concurrent workers)
rq worker heavy

# Terminal 2: Process light jobs (4 concurrent workers, faster processing)
rq worker light

# Terminal 3: Process default jobs (1 worker)
rq worker default

# Or: Single worker listening to all queues (processes in order)
rq worker heavy light default
```

### Enqueue Job in Service/Controller

```python
# app/services/simulation_service.py
from app.configs import JobType, enqueue_job
from app.lib.logging import get_logger

logger = get_logger(__name__)

class SimulationService:
    @staticmethod
    def enqueue_simulation(name: str, iterations: int):
        """Route to appropriate queue based on job size."""
        logger.info(f"Service: Enqueueing {name} ({iterations} iterations)")

        # Heavy processing for large jobs
        if iterations > 5000:
            logger.info("Service: Routing to HEAVY queue")
            job = enqueue_job(
                'app.workers.simulation.process_simulation',
                job_type=JobType.HEAVY,
                name=name,
                iterations=iterations
            )
        else:
            # Light processing for small jobs
            logger.info("Service: Routing to LIGHT queue")
            job = enqueue_job(
                'app.workers.simulation.process_simulation',
                job_type=JobType.LIGHT,
                name=name,
                iterations=iterations
            )

        logger.info(f"Service: Job {job.id} enqueued")
        return job.id
```

```python
# ✅ Type-safe
from app.configs import get_environment_configuration, get_redis_client

settings = get_environment_configuration()  # type: EnvironmentConfiguration
redis = get_redis_client()  # type: Redis
```
