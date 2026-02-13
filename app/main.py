from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.configs import get_environment_configuration
from app.api.routes import router


def create_app() -> FastAPI:
    settings = get_environment_configuration()
    
    app = FastAPI(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description="Bridge between Next.js and RQ Worker via Redis Queue"
    )
    
    # TODO: Add CORS settings based on environment configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(router)
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_environment_configuration()
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
