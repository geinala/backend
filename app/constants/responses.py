from app.dtos.responses import BaseApiResponseDTO
from app.exceptions import ValidationErrorResponseDTO

VALIDATION_ERROR_RESPONSE: dict[str, object] = {
    "description": "Validation Error",
    "content": {
       "application/json": {
            "schema": ValidationErrorResponseDTO.model_json_schema(ref_template="#/components/schemas/{model}"),
            "example": {
                "success": False,
                "message": "Validation error occurred",
                "errors": [
                    {"field": "field_name", "message": "field required"}
                ],
            }
        }
    }
}

BAD_REQUEST_RESPONSE: dict[str, object] = {
    "description": "Bad Request",
    "content": {
        "application/json": {
            "schema": BaseApiResponseDTO.model_json_schema(ref_template="#/components/schemas/{model}"),
            "example": {
                "success": False,
                "message": "Bad request",
            }
        }
    }
}

INTERNAL_SERVER_ERROR_RESPONSE: dict[str, object] = {
    "description": "Internal Server Error",
    "content": {
        "application/json": {
            "schema": BaseApiResponseDTO.model_json_schema(ref_template="#/components/schemas/{model}"),
            "example": {
                "success": False,
                "message": "An unexpected error occurred",
            }
        }
    }
}