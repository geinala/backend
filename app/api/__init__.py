from fastapi import APIRouter
from app.api.invitations import router as invitations_router
from app.api.jobs import router as jobs_router

def get_routers() -> list[APIRouter]:
    return [
        invitations_router,
        jobs_router
    ]


__all__ = ["get_routers"]