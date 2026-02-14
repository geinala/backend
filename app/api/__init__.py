"""API module for FastAPI routes and exceptions."""
from fastapi import APIRouter
from app.api.jobs import router as jobs_router

def get_routers() -> list[APIRouter]:
    """
        Aggregate all route routers. 
        
        Add new routes here by importing them and adding to list.
    """
    return [
        jobs_router,
        # Add more routers here (invitations_router, simulations_router, etc.)
    ]


__all__ = ["get_routers"]