"""Logging module with structured JSON logging and wide events support.

This package provides:
- Structured JSON logging for production and readable text for development
- Wide events (canonical log lines) pattern for complete context per event
- Request/job context tracking for distributed tracing
- FastAPI middleware for automatic HTTP request logging
"""

from app.lib.logging.logging import (
    get_logger,
    setup_logging,
    root_logger,
    StructuredJSONFormatter,
    SimpleTextFormatter,
)
from app.lib.logging.logging_context import (
    create_wide_event,
    WideEventTimer,
    get_request_id,
    set_request_id,
    get_job_id,
    set_job_id,
    generate_request_id,
    set_request_context,
    get_request_context,
)

__all__ = [
    # Logging setup
    "get_logger",
    "setup_logging",
    "root_logger",
    "StructuredJSONFormatter",
    "SimpleTextFormatter",
    # Wide events
    "create_wide_event",
    "WideEventTimer",
    # Request/job tracking
    "get_request_id",
    "set_request_id",
    "get_job_id",
    "set_job_id",
    "generate_request_id",
    "set_request_context",
    "get_request_context",
]
