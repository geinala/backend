# Exceptions Module

Custom exception hierarchy for consistent error handling and HTTP status mapping across all layers.

## Purpose

Provide a structured exception hierarchy that:
- Maps domain-level errors to HTTP status codes
- Allows controllers to catch and transform exceptions
- Enables routes to return consistent error responses
- Improves debugging with structured error information

## Architecture Position

```
Route (HTTP)
    ↓
  [catches APIException]
    ↓
Controller
    ↓
  [catches Service/Repository exceptions]
  [raises APIException]
    ↓
Service/Repository
    ↓
  [raises ServiceException, JobException, etc.]
    ↓
Database/External Integration
```

**When to use**:
- Throw service-level exceptions from services and repositories
- Catch them in controllers
- Map to API exceptions for HTTP response
- Handle in routes for final HTTP error response

## Exception Hierarchy

```
Exception (Python)
    │
    └── APIException (Base for all API-related errors)
            │
            ├── JobException
            │   ├── JobNotFoundError     (404)
            │   └── JobEnqueueError       (400)
            │
            ├── ValidationError           (422)
            │
            ├── ServiceException          (500)
            │   ├── DatabaseError
            │   └── ExternalServiceError
            │
            └── [Custom exceptions]
```

**Status Codes**:
- `400` - Bad Request (validation, enqueueing failed)
- `404` - Not Found (job not found)
- `422` - Validation Error (invalid input)
- `500` - Internal Server Error (service errors)

## Directory Structure

```
app/exceptions/
├── __init__.py          # Export all exceptions
├── README.md            # This file
└── base.py              # Exception class definitions
```

## Exception Classes

### APIException (Base)

Base class for all API exceptions. Maps to HTTP status code.

```python
# app/exceptions/base.py
from typing import Any, Dict, Optional

class APIException(Exception):
    """Base exception for all API errors."""
    
    def __init__(
        self, 
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)
```

### JobException

Base for job-related errors.

```python
class JobException(APIException):
    """Base for job operation errors."""
    
    def __init__(self, message: str, status_code: int = 400, **kwargs):
        super().__init__(message, status_code, **kwargs)

class JobNotFoundError(JobException):
    """Raised when job ID doesn't exist."""
    
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job {job_id} not found",
            status_code=404,
            error_code="JOB_NOT_FOUND",
            details={"job_id": job_id}
        )

class JobEnqueueError(JobException):
    """Raised when job enqueueing fails."""
    
    def __init__(self, reason: str):
        super().__init__(
            message=f"Failed to enqueue job: {reason}",
            status_code=400,
            error_code="JOB_ENQUEUE_ERROR",
            details={"reason": reason}
        )
```

### ValidationError

For input validation failures.

```python
class ValidationError(APIException):
    """Raised when input validation fails."""
    
    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Validation error in {field}: {message}",
            status_code=422,
            error_code="VALIDATION_ERROR",
            details={"field": field, "message": message}
        )
```

### ServiceException

Base for service layer errors.

```python
class ServiceException(APIException):
    """Base for service operation errors."""
    
    def __init__(self, message: str, status_code: int = 500, **kwargs):
        super().__init__(message, status_code, **kwargs)

class DatabaseError(ServiceException):
    """Raised on database operation failure."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            message=f"Database error during {operation}: {reason}",
            status_code=500,
            error_code="DATABASE_ERROR",
            details={"operation": operation, "reason": reason}
        )

class ExternalServiceError(ServiceException):
    """Raised when external service call fails."""
    
    def __init__(self, service: str, reason: str):
        super().__init__(
            message=f"External service error ({service}): {reason}",
            status_code=500,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, "reason": reason}
        )
```

## Usage Patterns

### In Services

```python
# app/services/job_service.py
from app.lib.logging import get_logger
from app.exceptions import JobNotFoundError, ValidationError
from rq import Queue
from redis.exceptions import RedisError

logger = get_logger(__name__)

class JobService:
    @staticmethod
    def get_job_status(job_id: str) -> dict:
        """Get job status, raising exceptions on error."""
        logger.info(f"Service: Fetching status for job {job_id}")
        
        try:
            # Validate input
            if not job_id:
                logger.error("Service: Empty job_id provided")
                raise ValidationError("job_id", "Cannot be empty")
            
            # Fetch from Redis
            from app.configs import get_redis_client
            from rq.job import Job
            
            redis = get_redis_client()
            job = Job.fetch(job_id, connection=redis)
            
            logger.info(f"Service: Status fetched - {job.get_status()}")
            return {
                "id": job.id,
                "status": job.get_status(),
                "progress": job.meta.get("progress", 0)
            }
            
        except Exception as e:
            logger.error(f"Service: Error - {str(e)}")
            # Catch RQ exceptions and transform
            if "NoSuchJobError" in str(type(e).__name__):
                raise JobNotFoundError(job_id)
            raise
```

### In Controllers

```python
# app/controllers/job_controller.py
from app.lib.logging import get_logger
from app.services.job_service import JobService
from app.exceptions import APIException

logger = get_logger(__name__)

class JobController:
    @staticmethod
    def get_job_status(job_id: str) -> dict:
        """Get job status with error mapping."""
        logger.info(f"Controller: Getting status for {job_id}")
        
        try:
            # Call service - may raise JobNotFoundError, ValidationError
            result = JobService.get_job_status(job_id)
            
            logger.info(f"Controller: Success")
            return result
            
        except APIException as e:
            # APIException already has status_code - re-raise for route
            logger.warning(f"Controller: API error - {e.error_code}: {e.message}")
            raise
        except Exception as e:
            # Unexpected errors
            logger.error(f"Controller: Unexpected error - {str(e)}")
            raise
```

### In Routes

```python
# app/api/jobs.py
from fastapi import APIRouter, HTTPException
from app.lib.logging import get_logger
from app.controllers.job_controller import JobController
from app.exceptions import APIException
from app.lib.response_formatter import ResponseFormatter

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/{job_id}/status")
async def get_job_status(job_id: str):
    """Get job status with standardized error responses."""
    try:
        logger.info(f"Route: Status request for {job_id}")
        
        # Call controller - may raise APIException
        result = JobController.get_job_status(job_id)
        
        logger.info(f"Route: Returning status")
        return ResponseFormatter.success_with_data(
            data=result,
            message="Job status retrieved"
        )
        
    except APIException as e:
        # Map to HTTPException with status code
        logger.error(f"Route: {e.error_code} - {e.message}")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error_code": e.error_code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        # Unexpected errors
        logger.error(f"Route: Unexpected error - {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

## Complete Exception Flow Example

```python
# Request arrives with invalid job_id

# 1. Route receives request
@router.get("/{job_id}/status")
async def get_job_status(job_id: str):  # job_id = ""
    try:
        result = JobController.get_job_status(job_id)
        # ↓ Controller called

# 2. Controller calls service
class JobController:
    @staticmethod
    def get_job_status(job_id: str):
        try:
            result = JobService.get_job_status(job_id)
            # ↓ Service called

# 3. Service validates and raises
class JobService:
    @staticmethod
    def get_job_status(job_id: str):
        if not job_id:
            raise ValidationError("job_id", "Cannot be empty")
            # ↑ ValidationError(status_code=422) raised

# 4. Controller catches and re-raises
        except APIException as e:
            logger.warning(f"Controller: {e.error_code}")
            raise  # Re-raise for route

# 5. Route catches and converts to HTTP
    except APIException as e:
        raise HTTPException(
            status_code=e.status_code,  # 422
            detail={
                "error_code": e.error_code,  # "VALIDATION_ERROR"
                "message": e.message,  # "Validation error in job_id: Cannot be empty"
                "details": e.details  # {"field": "job_id", ...}
            }
        )

# 6. Client receives error response
{
    "detail": {
        "error_code": "VALIDATION_ERROR",
        "message": "Validation error in job_id: Cannot be empty",
        "details": {"field": "job_id", "message": "Cannot be empty"}
    }
}
# HTTP 422 Unprocessable Entity
```

## Best Practices

✅ **DO**:
- Raise specific exception types (JobNotFoundError, not JobException)
- Include context in exception message and details
- Catch exceptions at layer boundaries (service → controller → route)
- Log exception with error code before re-raising
- Use consistent error_code format (UPPER_SNAKE_CASE)
- Include details dict for structured error information

❌ **DON'T**:
- Raise generic Exception - use custom exception types
- Catch and silently ignore exceptions
- Re-raise without logging first
- Include sensitive data in error messages
- Use exceptions for normal control flow
- Mix exception types across layers (e.g., raise APIException from service)

## Testing Exceptions

```python
# tests/test_exceptions.py
import pytest
from app.exceptions import JobNotFoundError, ValidationError
from app.controllers.job_controller import JobController

def test_job_not_found():
    """Test JobNotFoundError mapping."""
    with pytest.raises(JobNotFoundError) as exc_info:
        JobController.get_job_status("nonexistent")
    
    assert exc_info.value.status_code == 404
    assert exc_info.value.error_code == "JOB_NOT_FOUND"
    assert "nonexistent" in exc_info.value.details["job_id"]

def test_validation_error():
    """Test ValidationError mapping."""
    with pytest.raises(ValidationError) as exc_info:
        JobController.get_job_status("")
    
    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "VALIDATION_ERROR"
    assert exc_info.value.details["field"] == "job_id"

def test_exception_to_http_conversion(client):
    """Test exception converts to correct HTTP status."""
    response = client.get("/jobs/nonexistent/status")
    
    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "JOB_NOT_FOUND"
```

## Adding New Exceptions

When adding new exception types:

1. **Define base exception** if needed:
```python
class CustomException(APIException):
    """Description."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code)
```

2. **Define specific exceptions**:
```python
class SpecificError(CustomException):
    """When specific condition occurs."""
    def __init__(self, context: str):
        super().__init__(
            message=f"Specific error: {context}",
            status_code=400,
            error_code="SPECIFIC_ERROR",
            details={"context": context}
        )
```

3. **Export in `__init__.py`**:
```python
# app/exceptions/__init__.py
from .base import (
    APIException,
    CustomException,
    SpecificError,
    # ... other exceptions
)

__all__ = [
    "APIException",
    "CustomException",
    "SpecificError",
    # ... other exceptions
]
```

4. **Use in service/controller**:
```python
from app.exceptions import SpecificError

def my_function():
    if error_condition:
        raise SpecificError("context_value")
```

## Exception Reference

| Exception | Status | When to Use |
|-----------|--------|------------|
| `JobNotFoundError` | 404 | Job ID doesn't exist in Redis |
| `JobEnqueueError` | 400 | Failed to enqueue job to queue |
| `ValidationError` | 422 | Input validation failed |
| `ServiceException` | 500 | Service logic error |
| `DatabaseError` | 500 | Database operation failed |
| `ExternalServiceError` | 500 | External API call failed |

## See Also

- [API Module](../api/README.md) - Using exceptions in routes
- [Controllers Module](../controllers/README.md) - Catching and mapping exceptions
- [Services Module](../services/README.md) - Raising exceptions from business logic
- [Configuration](../configs/README.md) - Environment and infrastructure setup
