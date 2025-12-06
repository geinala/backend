from fastapi import FastAPI

from app.api.main import api_router

app = FastAPI(
    title="Simulation App API",
    description="API for the Simulation App",
    version="1.0.0",
)

app.include_router(api_router, prefix="/api")