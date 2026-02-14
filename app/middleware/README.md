# Middleware Module

Infrastructure layer that intercepts and enhances HTTP request/response processing. Middleware handles cross-cutting concerns like logging, authentication, and request tracking.

Your middleware modules provide:

- **Logging Middleware** - Structured logging with request context and correlation
- **Request Tracing** - Automatic request ID generation and tracking
- **Performance Metrics** - Request duration and timing information
- **Error Handling** - Automatic error capture and context preservation

## Purpose

Middleware sits between the HTTP client and your route handlers. It processes requests before they reach your routes and can modify responses before returning to clients.

Your middleware implementation follows the **wide events pattern** - emitting one context-rich event per request with all relevant information at completion.

## Architecture

Middleware processes requests in this order:

1. Client sends HTTP request
2. Middleware receives request (before routes)
3. Middleware generates or extracts request ID
4. Middleware sets up request context for tracing
5. Middleware tracks start time
6. Route handler processes request
7. Middleware captures response status
8. Middleware calculates duration
9. Middleware emits wide event with all context
10. Response returned to client

## WideEventMiddleware

Emits structured logging events for every HTTP request with complete context.

### Features

- **Request ID Tracking** - Generates UUID or extracts from `X-Request-ID` header
- **Distributed Tracing** - Pass request IDs across services for end-to-end tracing
- **Performance Metrics** - Measures request duration in milliseconds
- **Status Tracking** - Captures HTTP status code and determines success/error
- **Error Context** - Includes exception type and message on failures
- **Wide Events** - One complete event per request at completion

### Setup

Add middleware to your FastAPI app in `app/main.py`:

```python
from fastapi import FastAPI
from app.middleware.logging_middleware import WideEventMiddleware

app = FastAPI()

# Add logging middleware FIRST (processes requests first)
app.add_middleware(WideEventMiddleware)

# Then add other middleware (CORS, etc.)
app.add_middleware(CORSMiddleware, ...)
```

**Important:** Add `WideEventMiddleware` first so it wraps all other middleware and routes.

### How It Works

#### 1. Request ID Handling

```python
# Option 1: Middleware generates request ID
GET /api/jobs
# Result: request_id="req_a1b2c3d4e5f6"

# Option 2: Client provides request ID
GET /api/jobs -H "X-Request-ID: req_custom_123"
# Result: request_id="req_custom_123"
```

#### 2. Request Context

Middleware sets request context available to all handlers:

```python
# Available in routes via context
request_id = get_request_id()  # "req_abc123"
context = get_request_context()
# {
#   "request_id": "req_abc123",
#   "method": "POST",
#   "path": "/api/jobs"
# }
```

#### 3. Wide Event Emission

At request completion, middleware emits one event with all context:

**Development Output (Readable Text):**

```
[2026-02-14 15:30:45] [INFO] [app.middleware.logging_middleware]
event_type=http_request | request_id=req_abc123 | method=POST | path=/api/jobs | status_code=200 | outcome=success | duration_ms=125.50
```

**Production Output (Structured JSON):**

```json
{
  "timestamp": "2026-02-14T15:30:45.123456Z",
  "level": "INFO",
  "logger": "app.middleware.logging_middleware",
  "event_type": "http_request",
  "request_id": "req_abc123",
  "method": "POST",
  "path": "/api/jobs",
  "status_code": 200,
  "outcome": "success",
  "duration_ms": 125.50
}
```

### Usage in Routes

Your route handlers automatically work with middleware context:

```python
from fastapi import APIRouter
from app.lib import get_logger
from app.lib.logging.logging_context import get_request_id

router = APIRouter()
logger = get_logger(__name__)

@router.post("/jobs")
async def enqueue_job(request: JobRequest):
    """Enqueue a new simulation job.
    
    Request ID is automatically available from middleware context.
    """
    request_id = get_request_id()  # Set by middleware
    
    logger.info({
        "event_type": "job_enqueued",
        "job_name": request.name,
        "iterations": request.iterations,
    })
    
    return {"job_id": "job_123", "status": "queued"}
```

### Error Handling

Middleware captures errors and adds them to wide events:

```python
@router.post("/jobs")
async def enqueue_job(request: JobRequest):
    # Error automatically captured by middleware
    if not request.name:
        raise ValidationError("name", "Cannot be empty")
```

**Error Event (Production JSON):**

```json
{
  "event_type": "http_request",
  "request_id": "req_abc123",
  "method": "POST",
  "path": "/api/jobs",
  "status_code": 500,
  "outcome": "error",
  "duration_ms": 45.25,
  "error": {
    "type": "ValidationError",
    "message": "name: Cannot be empty"
  }
}
```

## Common Patterns

### Pattern 1: Tracing Across Services

Use request ID to correlate requests across multiple services:

```python
# Service A
request_id = get_request_id()  # "req_abc123"

# Call Service B with request ID
response = requests.post(
    "http://service-b/api/process",
    headers={"X-Request-ID": request_id},
    json={"data": "..."}
)

# Service B receives and logs with same request ID
# Logs from both services share request_id for correlation
```

### Pattern 2: Custom Request Context

Extend request context with business data:

```python
from app.lib.logging.logging_context import set_request_context, get_request_context

@router.post("/jobs")
async def enqueue_job(request: JobRequest, user_id: str):
    # Add business context
    context = get_request_context()
    context["user_id"] = user_id
    context["feature_flags"] = {"new_ui": True}
    set_request_context(context)
    
    # This context appears in all logged events
    logger.info({
        "event_type": "job_enqueued",
        "iterations": request.iterations,
    })
```

### Pattern 3: Multi-Middleware Stack

Combine with other middleware:

```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()

# Order matters! Add logging first
app.add_middleware(WideEventMiddleware)

# Then compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Then CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)
```

## Configuration

Middleware behavior is controlled via environment variables:

```env
# Log level
LOG_LEVEL=DEBUG              # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Logging format
ENVIRONMENT=development      # development or production

# File logging
ENABLE_FILE_LOGGING=false    # Set true in production
LOG_DIR=logs                 # Directory for log files
```

In **development**: Middleware logs readable text to console.
In **production**: Middleware emits structured JSON to stdout and files.

## Extending Middleware

To add new middleware for cross-cutting concerns:

1. Create new file in `app/middleware/` (e.g., `auth_middleware.py`)
2. Extend `BaseHTTPMiddleware` from Starlette
3. Implement `async dispatch()` method
4. Add to FastAPI app with `add_middleware()`

```python
# app/middleware/auth_middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract auth token
        token = request.headers.get("Authorization")
        
        # Validate (you implement this)
        # user = validate_token(token)
        
        # Pass to handlers
        response = await call_next(request)
        return response
```

Then add to app:

```python
from app.middleware.auth_middleware import AuthMiddleware

app.add_middleware(WideEventMiddleware)  # Logging first
app.add_middleware(AuthMiddleware)       # Then auth
```

## See Also

- [Logging Module](../lib/README.md) - Logging best practices and setup
- [Main App](../main.py) - FastAPI app configuration
- [API Module](../api/README.md) - HTTP route handlers
- [External: FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
- [External: Starlette Middleware](https://www.starlette.io/middleware/)
