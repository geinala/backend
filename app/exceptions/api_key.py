from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.lib.response_formatter import ResponseFormatter
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)


class InvalidAPIKeyException(Exception):
    def __init__(self, message: str = "Invalid or missing API key"):
        self.message = message
        super().__init__(self.message)


def register_api_key_exception_handlers(app: FastAPI):
    
    @app.exception_handler(InvalidAPIKeyException)
    async def api_key_exception_handler( # type: ignore
        request: Request, 
        exc: InvalidAPIKeyException
    ) -> JSONResponse:
        wide_event = {
            "event_type": "invalid_api_key",
            "path": request.url.path,
            "method": request.method,
            "error": exc.message,
            "error_type": type(exc).__name__,
        }
        
        logger.warning(wide_event)
        
        return ResponseFormatter.error(
            message=exc.message,
            status_code=401
        )
