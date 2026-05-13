
from app.lib.db import get_db
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.services.pre_processing.pre_processing_workflow_service import PreProcessingWorkflowService


async def continue_workflow(simulation_job_id: str):
    try:
        db_session = get_db()
        db = next(db_session)
        pre_processing_workflow_service = PreProcessingWorkflowService(
            simulation_job_repository=SimulationJobRepository(db)
        )
        
        await pre_processing_workflow_service.continue_workflow_after_file_validation(simulation_job_id=simulation_job_id)
    except Exception as e:
        raise e