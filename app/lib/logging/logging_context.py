"""Logging context utilities for wide events support.

This module provides utilities for collecting and emitting wide events
(canonical log lines) with context across request/job lifecycle.

Wide events pattern:
- Emit ONE event per request/job at completion
- Include all relevant context (timing, status, business data, environment)
- Use request/job IDs to correlate across services
"""

import time
from contextvars import ContextVar
from typing import Any, Optional
from uuid import uuid4

# Context variables for tracking request/job lifecycle
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
job_id_var: ContextVar[str] = ContextVar("job_id", default="")
request_context_var: ContextVar[dict[str, Any]] = ContextVar("request_context", default={})


def generate_request_id() -> str:
    """Generate a unique request ID for tracing.
    
    Returns:
        Unique request ID (UUID4 format)
    """
    return f"req_{uuid4().hex[:12]}"


def set_request_id(request_id: str) -> None:
    """Set the current request ID for context tracking.
    
    Args:
        request_id: Unique request identifier
    """
    request_id_var.set(request_id)


def get_request_id() -> str:
    """Get the current request ID.
    
    Returns:
        Current request ID or empty string if not set
    """
    return request_id_var.get("")


def set_job_id(job_id: str) -> None:
    """Set the current job ID for context tracking.
    
    Args:
        job_id: Unique job identifier
    """
    job_id_var.set(job_id)


def get_job_id() -> str:
    """Get the current job ID.
    
    Returns:
        Current job ID or empty string if not set
    """
    return job_id_var.get("")


def set_request_context(context: dict[str, Any]) -> None:
    """Set request context for wide event.
    
    Args:
        context: Dictionary with context fields (method, path, user_id, etc.)
    """
    request_context_var.set(context)


def get_request_context() -> dict[str, Any]:
    """Get current request context.
    
    Returns:
        Request context dictionary
    """
    return request_context_var.get({})


def create_wide_event(
    event_type: str,
    request_id: Optional[str] = None,
    job_id: Optional[str] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a wide event with context.
    
    Collects all relevant context for a single event emission
    at handler completion.
    
    Args:
        event_type: Type of event (e.g., "api_request", "job_execution")
        request_id: Request ID (auto-get from context if not provided)
        job_id: Job ID (auto-get from context if not provided)
        **kwargs: Additional event data (status, outcome, duration_ms, etc.)
        
    Returns:
        Dictionary with all event context ready to log
        
    Example:
        ```python
        wide_event = create_wide_event(
            "job_execution",
            status="completed",
            duration_ms=1250,
        )
        logger.info(wide_event)
        ```
    """
    event = {
        "event_type": event_type,
    }
    
    # Add request/job IDs if available
    request_id = request_id or get_request_id()
    if request_id:
        event["request_id"] = request_id
    
    job_id = job_id or get_job_id()
    if job_id:
        event["job_id"] = job_id
    
    # Add request context if available
    context = get_request_context()
    if context:
        event.update(context)
    
    # Add custom fields
    event.update(kwargs)
    
    return event


class WideEventTimer:
    """Context manager for tracking event duration.
    
    Usage:
        ```python
        with WideEventTimer() as timer:
            # do work
            pass
        
        # timer.elapsed_ms contains duration
        wide_event["duration_ms"] = timer.elapsed_ms
        ```
    """
    
    def __init__(self) -> None:
        """Initialize timer."""
        self.start_time: float = 0.0
        self.end_time: float = 0.0
    
    def __enter__(self) -> "WideEventTimer":
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing."""
        self.end_time = time.time()
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds.
        
        Returns:
            Duration in milliseconds (rounded to 2 decimals)
        """
        duration = (self.end_time - self.start_time) * 1000
        return round(duration, 2)
