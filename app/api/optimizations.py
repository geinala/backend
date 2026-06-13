
from fastapi import APIRouter

from app.controllers.optimize_controller import OptimizeController
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/optimizations", tags=["Optimizations"])

@router.post(
    path="/{simulation_id}",
    summary="Start optimization process for a given simulation"
)
async def initial_solution(
    simulation_id: str
):
    controller = OptimizeController()
    return await controller.optimize(simulation_id=simulation_id)