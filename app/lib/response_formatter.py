from app.dtos.api_response_dto import (
    BaseApiResponseDTO,
    ApiResponseWithDataDTO,
    ApiErrorResponseWithErrorsDTO,
)

class ResponseFormatter:
    """Format API responses using DTOs with type safety."""

    @staticmethod
    def success(message: str = "Success") -> dict[str, object]:
        """Format a successful response without data."""
        response = BaseApiResponseDTO(success=True, message=message)
        return response.to_dict()

    @staticmethod
    def success_with_data(data: object, message: str = "Success") -> dict[str, object]:
        """Format a successful response with data."""
        response = ApiResponseWithDataDTO(success=True, message=message, data=data)
        return response.to_dict()
    
    @staticmethod
    def error(message: str = "Error") -> dict[str, object]:
        """Format an error response without details."""
        response = BaseApiResponseDTO(success=False, message=message)
        return response.to_dict()

    @staticmethod
    def error_with_details(message: str = "Error", errors: list[str] | None = None) -> dict[str, object]:
        """Format an error response."""
        response = ApiErrorResponseWithErrorsDTO(success=False, message=message, errors=errors)
        return response.to_dict()