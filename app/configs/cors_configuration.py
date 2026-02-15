from fastapi import FastAPI
from app.configs import get_environment_configuration
from fastapi.middleware.cors import CORSMiddleware

def cors_configuration_factory(app: FastAPI):
    settings = get_environment_configuration()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
        expose_headers=settings.cors_expose_headers,
        max_age=settings.CORS_MAX_AGE,
    )