
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.controllers.optimize_controller import OptimizeController
from app.lib.db import get_db
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/optimizations", tags=["Optimizations"])

@router.post(
    path="/{id}",
    summary="Start optimization process for a given simulation"
)
async def initial_solution(
    id: str,
    db: Session = Depends(get_db)
):
    controller = OptimizeController()
    return await controller.optimize(simulation_id=id)