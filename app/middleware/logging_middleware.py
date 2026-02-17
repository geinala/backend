
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
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", generate_request_id())
        set_request_id(request_id)
        
        set_request_context({
            "method": request.method,
            "path": request.url.path,
            "request_id": request_id,
        })
        
        start_time = time.time()
        
        wide_event: dict[str, str | int | float | dict[str, str]] = {
            "event_type": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }
        
        try:
            response = await call_next(request)
            
            wide_event["status_code"] = response.status_code
            wide_event["outcome"] = "success" if response.status_code < 400 else "error"
            
            return response
            
        except Exception as e:
            wide_event["status_code"] = 500
            wide_event["outcome"] = "error"
            wide_event["error"] = {
                "type": type(e).__name__,
                "message": str(e),
            }
            raise
            
        finally:
            duration_ms = (time.time() - start_time) * 1000
            wide_event["duration_ms"] = round(duration_ms, 2)
            
            logger.info(wide_event)
