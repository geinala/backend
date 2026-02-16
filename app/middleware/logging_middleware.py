"""Middleware for FastAPI to emit wide events with request context.

This middleware:
- Generates or extracts request ID
- Tracks request timing
- Captures request/response metadata
- Emits one wide event per request at completion
"""

import time
from typing import Callable, Awaitable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.lib.logging.logging import get_logger
from app.lib.logging.logging_context import (
    generate_request_id,
    set_request_id,
    set_request_context,
)

logger = get_logger(__name__)


class WideEventMiddleware(BaseHTTPMiddleware):
    """Emit wide events (canonical log lines) for each HTTP request.
    
    Each request generates one structured event at completion with:
    - Request ID for tracing
    - HTTP method and path
    - Status code and outcome
    - Duration in milliseconds
    - Any error information
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request and emit wide event.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from handler
        """
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", generate_request_id())
        set_request_id(request_id)
        
        # Set request context for wide event
        set_request_context({
            "method": request.method,
            "path": request.url.path,
            "request_id": request_id,
        })
        
        # Track start time
        start_time = time.time()
        
        # Initialize wide event
        wide_event: dict[str, str | int | float | dict[str, str]] = {
            "event_type": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }
        
        try:
            # Call handler
            response = await call_next(request)
            
            # Capture response metadata
            wide_event["status_code"] = response.status_code
            wide_event["outcome"] = "success" if response.status_code < 400 else "error"
            
            return response
            
        except Exception as e:
            # Capture error information
            wide_event["status_code"] = 500
            wide_event["outcome"] = "error"
            wide_event["error"] = {
                "type": type(e).__name__,
                "message": str(e),
            }
            raise
            
        finally:
            # Calculate duration and emit wide event
            duration_ms = (time.time() - start_time) * 1000
            wide_event["duration_ms"] = round(duration_ms, 2)
            
            # Emit the wide event
            logger.info(wide_event)
