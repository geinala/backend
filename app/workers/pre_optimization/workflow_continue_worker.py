from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.services.pre_optimization.pre_optimization_workflow_service import PreOptimizationWorkflowService

logger = get_logger(__name__)


async def continue_workflow(simulation_id: str):
    try:
        db_session = get_db()
        db = next(db_session)
        pre_optimization_workflow_service = PreOptimizationWorkflowService(
            simulation_job_repository=SimulationJobRepository(db),
        )

        await pre_optimization_workflow_service.continue_workflow_after_courier_mapping(simulation_id=simulation_id)
    except Exception as e:
        raise e