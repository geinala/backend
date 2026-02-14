"""Middleware module for FastAPI with structured logging.

This package provides:
- WideEventMiddleware: Automatic HTTP request logging with context
"""

from app.middleware.logging_middleware import WideEventMiddleware

__all__ = ["WideEventMiddleware"]
