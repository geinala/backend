from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.configs import get_environment_configuration
from app.api import get_routers
from app.lib.logging import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_environment_configuration()
    logger.info(f"Creating FastAPI app - Title: {settings.API_TITLE}, Version: {settings.API_VERSION}")
    logger.info(f"CORS Origins: {settings.CORS_ALLOW_ORIGINS}")
    logger.info(f"Docs enabled: {settings.ENABLE_DOCS}, ReDoc: {settings.ENABLE_REDOC}, OpenAPI: {settings.ENABLE_OPENAPI}")
    
    # Configure docs URLs based on settings
    docs_url = "/docs" if settings.ENABLE_DOCS else None
    redoc_url = "/redoc" if settings.ENABLE_REDOC else None
    openapi_url = "/openapi.json" if settings.ENABLE_OPENAPI else None
    
    app = FastAPI(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description="Bridge between Next.js and RQ Worker via Redis Queue",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    
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
        logger.info(f"Registered router: {router.tags}")
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_environment_configuration()
    
    logger.info(f"Starting server at {settings.API_HOST}:{settings.API_PORT}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
