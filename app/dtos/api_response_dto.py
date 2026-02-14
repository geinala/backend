from dataclasses import asdict, dataclass
from typing import TypeVar, Generic

T = TypeVar('T')

@dataclass
class BaseApiResponseDTO:
    success: bool
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
    
@dataclass    
class ApiResponseWithDataDTO(BaseApiResponseDTO, Generic[T]):
    data: T | None = None
    
@dataclass
class ApiErrorResponseWithErrorsDTO(BaseApiResponseDTO):
    errors: list[str] | None = None