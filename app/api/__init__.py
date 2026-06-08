from fastapi import APIRouter
from app.api.simulations_job import router as simulations_router
from app.api.jobs import router as jobs_router
from app.api.optimizations import router as optimizations_router
from app.api.events import router as events_router
from app.api.tuning_experiments import router as tuning_experiments_router

def get_routers() -> list[APIRouter]:
    return [
        jobs_router,
        simulations_router,
        optimizations_router,
        events_router,
        tuning_experiments_router
    ]


__all__ = ["get_routers"]