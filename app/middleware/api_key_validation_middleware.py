from typing import Callable, Awaitable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.configs.environment_configuration import get_environment_configuration
from app.lib.response_formatter import ResponseFormatter
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)


class APIKeyValidationMiddleware(BaseHTTPMiddleware):
    EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json"}
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_environment_configuration()
        
        if not settings.ENABLE_API_KEY_VALIDATION:
            return await call_next(request)
        
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        api_key = self._extract_api_key(request)
        
        if not api_key or api_key != settings.API_KEY:
            logger.warning({
                "event_type": "api_key_validation_failed",
                "path": request.url.path,
                "method": request.method,
                "has_api_key": bool(api_key),
            })
            
            return ResponseFormatter.error(
                message="Invalid or missing API key",
                status_code=401
            )
        
        request.state.api_key_valid = True
        
        return await call_next(request)
    
    def _extract_api_key(self, request: Request) -> str | None:
        return request.headers.get("X-API-Key")
