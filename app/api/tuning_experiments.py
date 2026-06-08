from fastapi import APIRouter
from pydantic import BaseModel

from app.controllers.tuning_experiment_controller import TuningExperimentController
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tuning-experiments", tags=["Tuning Experiments"])


class TuneParametersRequest(BaseModel):
    file_path: str


@router.post(
    path="/{tuning_experiment_dataset_id}",
    summary="Start search for optimal parameters for a given tuning experiment"
)
async def tune_parameters(
    tuning_experiment_dataset_id: str,
    request: TuneParametersRequest,
):
    controller = TuningExperimentController()
    return await controller.tune_parameters(
        tuning_experiment_dataset_id=tuning_experiment_dataset_id,
    )