from fastapi import APIRouter
from app.api.invitations import router as invitations_router
from app.api.simulations import router as simulations_router
from app.api.jobs import router as jobs_router
from app.api.optimizations import router as optimizations_router

def get_routers() -> list[APIRouter]:
    return [
        jobs_router,
        simulations_router,
        invitations_router,
        optimizations_router
    ]


__all__ = ["get_routers"]