"""API module for FastAPI routes and exceptions."""
from fastapi import APIRouter
from app.api.invitations import router as invitations_router

def get_routers() -> list[APIRouter]:
    """
        Aggregate all route routers. 
        
        Add new routes here by importing them and adding to list.
    """
    return [
        invitations_router,
        # Add more routers here (simulations_router, etc.)
    ]


__all__ = ["get_routers"]