# Lib Module

Utility and utility functions used across the application.

## Purpose

This module provides:

- **Logging** - Structured logging with file rotation
- **Response formatting** - Standardized API response formatting
- **Database helpers** - Database connection utilities

## Module Contents

### logging.py

Centralized logging configuration with file rotation.

```python
from app.lib.logging import get_logger

logger = get_logger(__name__)

# Use in any module
logger.info("Application started")
logger.error("Processing failed")
logger.debug("Debug information")
```

**Features:**

- ✅ Console and file output
- ✅ Log rotation (10 MB max, 5 backups)
- ✅ Configurable log level via `.env`
- ✅ Environment-aware configuration

**Configuration via `.env`:**

```env
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR=logs                # Directory for log files
LOG_FILE=app.log            # Log filename
LOG_BACKUP_COUNT=5          # Number of backup files
LOG_MAX_BYTES=10485760      # Max file size (10 MB)
ENABLE_FILE_LOGGING=false   # Write to file (default: false = console-only)
```

**Development vs Production:**

- **Development** (ENABLE_FILE_LOGGING=false): Logs only to console for immediate visibility
- **Production** (ENABLE_FILE_LOGGING=true): Logs to both console and file with rotation

```python
from app.lib.logging import get_logger

logger = get_logger(__name__)

def my_function():
    logger.info("Starting function")
    logger.warning("Something unexpected")
    logger.error("An error occurred")
```

**Log Output Locations:**

- **Console** - Always enabled, real-time output to terminal (all log levels)
- **File** - Optional, enabled via ENABLE_FILE_LOGGING=true in `.env` (logs to `logs/app.log`)

When ENABLE_FILE_LOGGING=true:

```
logs/
├── app.log              # Current log file (newest)
├── app.log.1            # Backup 1
├── app.log.2            # Backup 2
├── app.log.3
└── ...                  # Total of LOG_BACKUP_COUNT backups
```

When ENABLE_FILE_LOGGING=false:

```
logs/
└── (no log files created, all output goes to console)
```

### response_formatter.py

Standardized response formatting for API endpoints using DTOs.

```python
from app.lib.response_formatter import ResponseFormatter
from app.dtos import ApiResponseWithDataDTO

# Success response with data
response = ResponseFormatter.success_with_data(
    data={"job_id": "abc123", "status": "queued"},
    message="Job enqueued successfully"
)
# Returns: {"success": True, "message": "...", "data": {...}}

# Success response without data
response = ResponseFormatter.success("Operation completed")
# Returns: {"success": True, "message": "Operation completed"}

# Error response
response = ResponseFormatter.error(
    message="Invalid configuration",
    errors=["Field 'name' is required", "Field 'timeout' exceeds maximum"]
)
# Returns: {"success": False, "message": "...", "errors": [...]}
```

**Features:**

- ✅ Type-safe with DTOs
- ✅ Consistent response structure
- ✅ Error details support
- ✅ Generic data type support

**Response Format:**

Success with data:

```json
{
  "success": true,
  "message": "Operation successful",
  "data": {
    "job_id": "123",
    "status": "queued"
  }
}
```

Error response:

```json
{
  "success": false,
  "message": "Validation failed",
  "errors": ["Name is required", "Timeout exceeds limit"]
}
```

**Using in Routes:**

```python
from fastapi import APIRouter
from app.lib.response_formatter import ResponseFormatter

router = APIRouter()

@router.get("/status")
def health_check():
    return ResponseFormatter.success("Server is healthy")

@router.post("/jobs")
def enqueue_job(request: JobRequest):
    try:
        job_id = JobService.enqueue(request)
        return ResponseFormatter.success_with_data(
            data={"job_id": job_id},
            message="Job enqueued"
        )
    except ValidationError as e:
        return ResponseFormatter.error(
            message="Validation failed",
            errors=e.errors()
        )
```

### db.py

Database connection utilities (optional - for future database support).

```python
from app.lib.db import get_db

# For SQLAlchemy sessions
with get_db() as session:
    # Use session for queries
    user = session.query(User).first()
```

Currently a placeholder for when database support is added.

## Logging Best Practices

### 1. Always Use Named Loggers

```python
# Good
logger = get_logger(__name__)

# Bad - Using root logger
import logging
logger = logging.getLogger()
```

### 2. Include Context

```python
# Good - Include relevant context
logger.info(f"Job {job_id} started by user {user_id}")

# Bad - Vague message
logger.info("Job started")
```

### 3. Use Appropriate Log Levels

- **DEBUG** - Development debugging information
- **INFO** - General informational messages about normal operations
- **WARNING** - Something unexpected but application continues
- **ERROR** - Error occurred but application continues
- **CRITICAL** - Severe error, application may not continue

```python
logger.debug("Variable value: x = 5")           # Development
logger.info("User logged in successfully")      # Normal
logger.warning("Slow query detected")           # Unexpected
logger.error("Failed to connect to database")   # Error
logger.critical("Out of memory")                # Severe
```

### 4. Include Layer Information

Log messages should include the layer/component:

```python
# Route layer
logger.info("Route: Received request - /api/jobs")

# Controller layer
logger.info("Controller: Processing enqueue request")

# Service layer
logger.info("Service: Validating configuration")

# Worker layer
logger.info(f"Worker: Job {job_id} - Starting execution")
```

### 5. No Sensitive Data in Logs

```python
# Bad - Includes password
logger.info(f"Connecting to {username}:{password}@{host}")

# Good - Only safe information
logger.info(f"Connecting to database at {host}")
```

## Logging in Different Layers

```python
# app/api/jobs.py
logger = get_logger(__name__)

@router.post("/jobs")
def enqueue_job(request: JobRequest):
    logger.info("Route: Received enqueue request")
    try:
        job_id = JobController.enqueue(request)
        logger.info(f"Route: Job enqueued - {job_id}")
        return {"job_id": job_id}
    except Exception as e:
        logger.error(f"Route: Error - {str(e)}")
        raise

# app/controllers/job_controller.py
logger = get_logger(__name__)

class JobController:
    @staticmethod
    def enqueue(request: JobRequest) -> str:
        logger.info("Controller: Processing enqueue")
        job_id = JobService.enqueue(request)
        logger.info("Controller: Enqueue completed")
        return job_id

# app/services/job_service.py
logger = get_logger(__name__)

class JobService:
    @staticmethod
    def enqueue(request: JobRequest) -> str:
        logger.info("Service: Enqueueing job")
        q = get_queue()
        job = q.enqueue('app.workers.job.process', **request.dict())
        logger.info(f"Service: Job created - {job.id}")
        return job.id

# app/workers/job.py
logger = get_logger(__name__)

def process(**params):
    job = current_job()
    logger.info(f"Worker: Job {job.id} - Starting")
    try:
        # Process...
        logger.info(f"Worker: Job {job.id} - Completed")
    except Exception as e:
        logger.error(f"Worker: Job {job.id} - Failed: {str(e)}")
        raise
```

## File Organization

```
lib/
├── __init__.py                  # Exports
├── logging.py                   # Logging setup
├── response_formatter.py        # Response formatting
├── db.py                        # Database utilities
└── README.md
```

`app/lib/__init__.py`:

```python
"""Library utilities for the application."""

from app.lib.logging import get_logger, setup_logging
from app.lib.response_formatter import ResponseFormatter
from app.lib.db import get_db

__all__ = [
    "get_logger",
    "setup_logging",
    "ResponseFormatter",
    "get_db",
]
```

## See Also

- [API Module](../api/README.md) - Logging in routes
- [Controllers Module](../controllers/README.md) - Logging in orchestration
- [Services Module](../services/README.md) - Logging in business logic
- [Workers Module](../workers/README.md) - Logging in job execution
- [Configs Module](../configs/README.md) - Logging configuration
