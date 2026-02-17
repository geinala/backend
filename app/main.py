from fastapi import FastAPI
from app.configs.environment_configuration import get_environment_configuration
from app.api import get_routers
from app.configs.openapi_configuration import open_api_configuration_factory
from app.configs.cors_configuration import cors_configuration_factory
from app.exceptions import global_exception_handler_factory
from app.lib.logging.logging import get_logger
from app.middleware.logging_middleware import WideEventMiddleware

logger = get_logger(__name__)

def create_app() -> FastAPI:
    settings = get_environment_configuration()
    
    logger.info({
        "event_type": "app_startup",
        "title": settings.API_TITLE,
        "version": settings.API_VERSION,
        "environment": settings.ENVIRONMENT,
    })
    
    docs_url = "/docs" if settings.ENABLE_DOCS else None
    redoc_url = "/redoc" if settings.ENABLE_REDOC else None
    openapi_url = "/openapi.json" if settings.ENABLE_OPENAPI else None
    
    app = FastAPI(
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    
    global_exception_handler_factory(app)
    
    app.add_middleware(WideEventMiddleware)
    
    cors_configuration_factory(app)
    
    for router in get_routers():
        app.include_router(router, prefix="/api")
        logger.info({
            "event_type": "router_registered",
            "tags": router.tags,
        })
    
    return app


app = create_app()

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
