

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.controllers.simulation_job_controller import SimulationJobController
from app.lib.db import get_db
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/simulations/jobs", tags=["Simulations Jobs"])

@router.post(
    path="/{id}/preprocess",
    summary="Prepocessing simulation job files, including validation and preparation for data cleaning and geocoding"
)
async def process_files(
    id: str,
    db: Session = Depends(get_db)
):
    controller = SimulationJobController(db=db)
    return await controller.preprocess_simulation_job(simulation_job_id=id)

@router.post(
    path="/{id}/revalidate",
    summary="Revalidate manually corrected simulation job geocoding results"
)
async def revalidate_files(
    id: str,
    db: Session = Depends(get_db)
):
    controller = SimulationJobController(db=db)
    return await controller.revalidate_simulation_job(simulation_job_id=id)
