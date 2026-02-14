# Lib Module

Shared utility functions and modules that your application uses across all layers.

Your lib module provides:

- **Logging** - Structured JSON logging with wide events for powerful analytics
- **Logging context** - Request/job tracking utilities for event correlation
- **Logging middleware** - FastAPI middleware for automatic request tracing
- **Response formatting** - Standardized API response formatting
- **Database helpers** - Database connection utilities

## Logging Best Practices

Your application uses **wide events** (canonical log lines) - the recommended pattern for modern logging and observability.

### What Are Wide Events?

Instead of scattering multiple log lines throughout your code, emit **one context-rich event** at completion with all relevant information. This enables powerful debugging and analytics.

### Why Wide Events?

Wide events provide:

- **Complete context** per request/job in one place
- **Better querying** by request/job ID across all services
- **Analytics** with many dimensions (cardinality)
- **Debugging** without searching multiple log lines
- **Correlation** between services using request IDs

### Logging Principles

Follow these principles for effective logging:

#### 1. Wide Events (One Event Per Request/Job)

Emit a single structured event at completion with all context:

```python
from app.lib import get_logger
from app.lib.logging.logging_context import create_wide_event, WideEventTimer

logger = get_logger(__name__)

with WideEventTimer() as timer:
    # Do work here
    result = execute_job()

# Emit one wide event with all context
wide_event = create_wide_event(
    "job_execution",
    status="completed",
    outcome="success",
    result=result,
    duration_ms=timer.elapsed_ms,
)
logger.info(wide_event)
```

#### 2. High Cardinality & Dimensionality

Include fields with many unique values (request IDs, job IDs, user IDs) and many fields per event:

```python
wide_event = {
    "request_id": "req_abc123",      # High cardinality (millions of values)
    "job_id": "job_xyz789",          # Enables querying specific jobs
    "user_id": "user_456",           # User tracking
    "status": "completed",           # Categorical
    "duration_ms": 1250.50,          # Numeric
    "result_size": 2048,             # Business metric
}
```

#### 3. Business Context

Always include business information alongside technical details:

```python
# Include: what matters to your product
wide_event = {
    "event_type": "simulation_completed",
    "iterations": 10000,             # Business parameter
    "compute_time_ms": 5000,         # Technical metric
    "result_accuracy": 0.95,         # Business metric
    "user_tier": "premium",          # User context
    "price_impact_cents": 150,       # Business value
}
```

#### 4. Environment Characteristics

Include deployment and environment info:

```python
import os

wide_event = {
    "service_version": os.getenv("SERVICE_VERSION", "1.0.0"),
    "environment": os.getenv("ENVIRONMENT", "development"),
    "commit_hash": os.getenv("COMMIT_HASH", "unknown"),
    "region": os.getenv("REGION", "us-east-1"),
}
```

### Logging in Different Contexts

#### HTTP Requests (FastAPI)

The `WideEventMiddleware` automatically emits events for all HTTP requests:

```python
# In app/main.py (already configured)
app.add_middleware(WideEventMiddleware)

# Automatically logs:
# {
#   "event_type": "http_request",
#   "request_id": "req_abc123",
#   "method": "POST",
#   "path": "/api/jobs",
#   "status_code": 200,
#   "duration_ms": 150.25,
#   "outcome": "success"
# }
```

Set request IDs with headers:

```bash
# Client sends
curl -H "X-Request-ID: req_custom123" http://localhost:8000/api/jobs
```

#### Background Jobs (RQ Workers)

Emit wide events at job completion:

```python
from app.lib import get_logger
from app.lib.logging.logging_context import create_wide_event, WideEventTimer

logger = get_logger(__name__)

def process_simulation(config: dict) -> dict:
    job = get_current_job()

    with WideEventTimer() as timer:
        try:
            result = do_work(config)
            outcome = "success"
        except Exception as e:
            outcome = "error"
            raise
        finally:
            # Emit wide event with all context
            wide_event = create_wide_event(
                "simulation_job",
                job_id=job.id,
                status="completed",
                outcome=outcome,
                duration_ms=timer.elapsed_ms,
                iterations=config.get("iterations"),
            )
            logger.info(wide_event)
```

#### Services and Controllers

Include context in business logic:

```python
class SimulationService:
    @staticmethod
    def validate(config: dict) -> bool:
        wide_event = create_wide_event(
            "validation_check",
            status="running",
        )

        try:
            is_valid = config_is_valid(config)
            wide_event["outcome"] = "success" if is_valid else "validation_failed"
            return is_valid
        except Exception as e:
            wide_event["outcome"] = "error"
            wide_event["error"] = str(e)
            raise
        finally:
            logger.info(wide_event)
```

### Log Format

#### Development (Human-Readable)

```
[2026-02-14 15:30:45] [INFO] [app.workers.simulation] - status=completed | outcome=success | duration_ms=1250.50 | job_id=job_123
```

#### Production (Structured JSON)

```json
{
  "timestamp": "2026-02-14T15:30:45.123456Z",
  "level": "INFO",
  "logger": "app.workers.simulation",
  "event_type": "simulation_job",
  "job_id": "job_123",
  "status": "completed",
  "outcome": "success",
  "duration_ms": 1250.5,
  "request_id": "req_abc123"
}
```

### Configuration

Control logging format and output via environment variables:

```env
# Log level
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL

# File output (disabled by default in development)
ENABLE_FILE_LOGGING=false   # Set to true in production

# Log file settings
LOG_DIR=logs                # Directory for log files
LOG_FILE=app.log            # Log filename
LOG_BACKUP_COUNT=5          # Number of backup files
LOG_MAX_BYTES=10485760      # Max file size (10 MB)

# Environment (controls JSON format)
ENVIRONMENT=development     # development or production
```

In **development**: Logs appear as readable text on console.
In **production**: Logs appear as structured JSON for analytics.

### Using Logging Utilities

Import the logging utilities you need:

```python
# Basic logger
from app.lib import get_logger

logger = get_logger(__name__)

# Wide event utilities
from app.lib.logging.logging_context import (
    create_wide_event,
    WideEventTimer,
    get_request_id,
    set_request_context,
)

# Use in your handlers
with WideEventTimer() as timer:
    result = do_work()

event = create_wide_event(
    "my_event",
    outcome="success",
    duration_ms=timer.elapsed_ms,
    **result
)
logger.info(event)
```

### Module File Organization

```
lib/
├── __init__.py                      # Exports
├── logging/                         # Logging subpackage
│   ├── __init__.py
│   ├── logging.py                   # Logging setup with JSON formatting
│   └── logging_context.py           # Request/job context tracking
├── response_formatter.py            # Response formatting
├── db.py                            # Database utilities
└── README.md
```

The logging middleware is located in:

```
app/
├── middleware/
│   ├── __init__.py
│   └── logging_middleware.py        # FastAPI middleware for wide events
```

#### logging.py

Structured logging with JSON formatters:

```python
from app.lib import get_logger
from app.lib.logging.logging import setup_logging

logger = get_logger(__name__)

# JSON format in production, readable text in development
logger.info({
    "event_type": "job_started",
    "job_id": "job_123",
    "status": "running",
})
```

#### logging_context.py

Context tracking for wide events:

```python
from app.lib.logging.logging_context import (
    create_wide_event,
    WideEventTimer,
    get_request_id,
    set_request_id,
)

# Automatic request ID generation and tracking
request_id = get_request_id()

# Create wide events with context
event = create_wide_event(
    "process_complete",
    status="done",
)
```

#### logging_middleware.py

Automatic request tracking:

```python
from app.middleware.logging_middleware import WideEventMiddleware

# Add to FastAPI app
app.add_middleware(WideEventMiddleware)

# Automatically emits HTTP request events
```

### Common Patterns

#### Pattern 1: Worker with Wide Event

```python
from app.lib import get_logger
from app.lib.logging.logging_context import create_wide_event, WideEventTimer
from rq.job import get_current_job

logger = get_logger(__name__)

def my_job(param1: str, param2: int) -> dict:
    job = get_current_job()

    with WideEventTimer() as timer:
        try:
            # Do work
            result = process(param1, param2)
            outcome = "success"
        except Exception as e:
            outcome = "error"
            raise
        finally:
            event = create_wide_event(
                "my_job",
                job_id=job.id,
                outcome=outcome,
                duration_ms=timer.elapsed_ms,
                param1=param1,
                param2=param2,
            )
            logger.info(event)
```

#### Pattern 2: Service with Context

```python
from app.lib import get_logger
from app.lib.logging.logging_context import create_wide_event

logger = get_logger(__name__)

class MyService:
    @staticmethod
    def do_work(data: dict) -> dict:
        event = create_wide_event(
            "service_operation",
            operation="process",
        )

        try:
            result = execute(data)
            event["outcome"] = "success"
            event["result_size"] = len(result)
            return result
        except Exception as e:
            event["outcome"] = "error"
            event["error_type"] = type(e).__name__
            raise
        finally:
            logger.info(event)
```

### Response Formatting

Format standardized responses for API endpoints:

```python
from app.lib.response_formatter import ResponseFormatter

# Success response with data
response = ResponseFormatter.success_with_data(
    data={"job_id": "abc123", "status": "queued"},
    message="Job enqueued successfully"
)

# Error response
response = ResponseFormatter.error(
    message="Validation failed",
    errors=["Field required"]
)
```

### File Organization

Export all utilities from `__init__.py`:

```python
# app/lib/__init__.py

from app.lib.logging.logging import get_logger, setup_logging, root_logger
from app.lib.logging.logging_context import (
    create_wide_event,
    WideEventTimer,
    get_request_id,
    set_request_id,
)
from app.lib.response_formatter import ResponseFormatter
from app.lib.db import get_db

__all__ = [
    "get_logger",
    "setup_logging",
    "create_wide_event",
    "WideEventTimer",
    "get_request_id",
    "set_request_id",
    "ResponseFormatter",
    "get_db",
]
```

### See Also

- [Middleware Module](../middleware/README.md) - Request logging and tracing setup
- [API Module](../api/README.md) - Logging in routes
- [Workers Module](../workers/README.md) - Logging in job execution
- [Services Module](../services/README.md) - Logging in business logic
- [Controllers Module](../controllers/README.md) - Logging in orchestration
- [Configs Module](../configs/README.md) - Logging configuration
