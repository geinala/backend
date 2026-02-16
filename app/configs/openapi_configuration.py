from typing import Any, Callable, ParamSpec, TypeVar
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from app.constants.responses import (
    VALIDATION_ERROR_RESPONSE,
    BAD_REQUEST_RESPONSE,
    INTERNAL_SERVER_ERROR_RESPONSE,
)
from app.configs.environment_configuration import get_environment_configuration
from app.exceptions.validation import ValidationErrorResponseDTO 

def open_api_configuration_factory(app: FastAPI):
    settings = get_environment_configuration()
    
    def openapi_config():
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title=settings.API_TITLE,
            version=settings.API_VERSION,
            description="Bridge between Next.js and RQ Worker via Redis Queue",
            routes=app.routes,
        )
        
        validation_schema_factory(openapi_schema)
        
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue

            skip = getattr(route.endpoint, "skip_global_responses", False)

            if skip:
                continue

            path = openapi_schema["paths"].get(route.path)
            if not path:
                continue

            for method in route.methods or []:
                method_lower = method.lower()

                if method_lower not in path:
                    continue

                operation = path[method_lower]
                operation.setdefault("responses", {})

                operation["responses"]["400"] = BAD_REQUEST_RESPONSE
                operation["responses"]["422"] = VALIDATION_ERROR_RESPONSE
                operation["responses"]["500"] = INTERNAL_SERVER_ERROR_RESPONSE

        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    def validation_schema_factory(openapi_schema: dict[str, Any]):
        schema = ValidationErrorResponseDTO.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        
        if "$defs" in schema:
            if "components" not in openapi_schema:
                openapi_schema["components"] = {"schemas": {}}
            if "schemas" not in openapi_schema["components"]:
                openapi_schema["components"]["schemas"] = {}
                
            for model_name, model_schema in schema["$defs"].items():
                openapi_schema["components"]["schemas"][model_name] = model_schema
            
            del schema["$defs"]
    
    app.openapi = openapi_config

P = ParamSpec("P")
R = TypeVar("R")

def no_global_responses(
    func: Callable[P, R]
) -> Callable[P, R]:
    func.skip_global_responses = True  # type: ignore[attr-defined]
    return func
