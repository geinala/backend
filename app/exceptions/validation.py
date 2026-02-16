from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ValidationException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.dtos.responses.api_response_dto import ApiErrorResponseWithDetailsDTO
from app.lib.response_formatter import ResponseFormatter
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

class ValidationErrorDetailsDTO(BaseModel):
    field: str
    message: str
    
class ValidationErrorResponseDTO(ApiErrorResponseWithDetailsDTO[ValidationErrorDetailsDTO]):
    pass

def register_validation_exception_handlers(app: FastAPI):
    @app.exception_handler(ValidationException)
    async def validation_exception_handler(request: Request, exc: ValidationException) -> JSONResponse: # type: ignore
        wide_event = {
            "event_type": "validation_exception",
            "path": request.url.path,
            "method": request.method,
            "error": str(exc.errors()),
            "error_type": type(exc).__name__,
        }
        
        logger.warning(wide_event)
        
        return ResponseFormatter.error(
            message=str(exc.errors()),
            status_code=400
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse: # type: ignore
        wide_event = {
            "event_type": "validation_exception",
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
        
        logger.warning(wide_event)
        
        errors: list[ValidationErrorDetailsDTO] = []
        
        for error in exc.errors():
            loc = error.get("loc", [])
            field = ".".join(str(item) for item in loc if item != "body")
            message = error.get("msg", "Invalid input")
            
            errors.append(ValidationErrorDetailsDTO(field=field, message=message))
            
        return ResponseFormatter.error_with_details(
            errors=errors,
            message="Validation error",
            status_code=422
        )