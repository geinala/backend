

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.controllers.simulation_controller import SimulationController

logger = get_logger(__name__)

router = APIRouter(prefix="/simulations/jobs", tags=["Simulations Jobs"])

@router.post(
    path="/{id}/files",
    summary="Process files for simulation"
)
async def process_files(
    id: str,
    db: Session = Depends(get_db)
):
    controller = SimulationController(db=db)
    return await controller.process_files(simulation_job_id=id)


@router.post(
    path="/{id}/cleaning",
    summary="Clean uploaded rows for simulation"
)
async def clean_uploaded_rows(
    id: str,
    db: Session = Depends(get_db)
):
    controller = SimulationController(db=db)
    return await controller.clean_uploaded_rows(simulation_job_id=id)
