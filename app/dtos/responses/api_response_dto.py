from typing import TypeVar, Generic

from pydantic import BaseModel

E = TypeVar('E')
T = TypeVar('T')

class BaseApiResponseDTO(BaseModel):
    success: bool
    message: str = ""
    
class ApiResponseWithDataDTO(BaseApiResponseDTO, Generic[T]):
    data: T | None = None
    
class ApiErrorResponseWithDetailsDTO(BaseApiResponseDTO, Generic[E]):
    errors: E | None = None