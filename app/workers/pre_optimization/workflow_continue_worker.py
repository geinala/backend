from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.repositories.courier_repository import CourierRepository
from app.services.pre_optimization.pre_optimization_workflow_service import PreOptimizationWorkflowService

logger = get_logger(__name__)


async def continue_workflow(simulation_id: str):
    try:
        db_session = get_db()
        db = next(db_session)
        pre_optimization_workflow_service = PreOptimizationWorkflowService(
            simulation_job_repository=SimulationJobRepository(db),
            simulation_uploaded_row_repository=SimulationUploadedRowRepository(db),
            courier_repository=CourierRepository(db),
            node_repository=NodeRepository(db),
        )

        await pre_optimization_workflow_service.continue_workflow_after_courier_mapping(simulation_id=simulation_id)
    except Exception as e:
        raise e