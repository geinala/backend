from fastapi.responses import JSONResponse

from app.dtos import (
    BaseApiResponseDTO,
    ApiResponseWithDataDTO,
    ApiErrorResponseWithDetailsDTO,
)

from typing import TypeVar

T = TypeVar('T')
E = TypeVar('E')

class ResponseFormatter:
    @staticmethod
    def success(message: str = "Success", status_code: int = 200) -> JSONResponse:
        response = BaseApiResponseDTO(success=True, message=message)
        return JSONResponse(content=response.model_dump(), status_code=status_code)

    @staticmethod
    def success_with_data(data: list[T] | T, message: str = "Success", status_code: int = 200) -> JSONResponse:
        response = ApiResponseWithDataDTO[list[T] | T](
            success=True, 
            message=message, 
            data=data
        )
        
        return JSONResponse(
            content=response.model_dump(mode='json'), 
            status_code=status_code
        )
    
    @staticmethod
    def error(message: str = "Error", status_code: int = 400) -> JSONResponse:
        response = BaseApiResponseDTO(success=False, message=message)
        return JSONResponse(content=response.model_dump(), status_code=status_code)

    @staticmethod
    def error_with_details(errors: list[E], message: str = "Error", status_code: int = 400) -> JSONResponse:
        response = ApiErrorResponseWithDetailsDTO[list[E] | E](
            success=False, 
            message=message, 
            errors=errors
        )
        
        return JSONResponse(
            content=response.model_dump(mode='json'), 
            status_code=status_code
        )