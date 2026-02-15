from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.configs import get_environment_configuration
from app.api import get_routers
from app.configs import open_api_configuration_factory
from app.exceptions import global_exception_handler_factory
from app.lib import get_logger
from app.middleware.logging_middleware import WideEventMiddleware

logger = get_logger(__name__)

def create_app() -> FastAPI:
    settings = get_environment_configuration()
    
    # Log app initialization
    logger.info({
        "event_type": "app_startup",
        "title": settings.API_TITLE,
        "version": settings.API_VERSION,
        "environment": settings.ENVIRONMENT,
    })
    
    # Configure docs URLs based on settings
    docs_url = "/docs" if settings.ENABLE_DOCS else None
    redoc_url = "/redoc" if settings.ENABLE_REDOC else None
    openapi_url = "/openapi.json" if settings.ENABLE_OPENAPI else None
    
    app = FastAPI(
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    
    # Register global exception handlers
    global_exception_handler_factory(app)
    
    # Add middleware for wide events (must be first to capture all requests)
    app.add_middleware(WideEventMiddleware)
    
    # Set up CORS middleware with configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
        expose_headers=settings.cors_expose_headers,
        max_age=settings.CORS_MAX_AGE,
    )
    
    # Include all routers
    for router in get_routers():
        app.include_router(router)
        logger.info({
            "event_type": "router_registered",
            "tags": router.tags,
        })
    
    return app


app = create_app()

# Set up OpenAPI configuration
open_api_configuration_factory(app)

if __name__ == "__main__":
    import uvicorn
    settings = get_environment_configuration()
    
    logger.info({
        "event_type": "server_start",
        "host": settings.API_HOST,
        "port": settings.API_PORT,
    })
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
