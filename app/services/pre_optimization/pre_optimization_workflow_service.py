from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.lib.logging.logging import get_logger
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.repositories.courier_repository import CourierRepository
from app.services.job_service import enqueue_job
from app.workers.optimization_worker import optimize as run_optimization
from app.workers.pre_optimization.node_mapping_worker import map_nodes as map_optimization_nodes

logger = get_logger(__name__)


class PreOptimizationWorkflowService:
    def __init__(
        self,
        simulation_job_repository: SimulationJobRepository,
        simulation_uploaded_row_repository: SimulationUploadedRowRepository,
        courier_repository: CourierRepository,
        node_repository: NodeRepository,
    ):
        self.simulation_job_repository = simulation_job_repository
        self.simulation_uploaded_row_repository = simulation_uploaded_row_repository
        self.courier_repository = courier_repository
        self.node_repository = node_repository

    async def continue_workflow_after_courier_mapping(self, simulation_id: str):
        try:
            simulation_job = await self.simulation_job_repository.get_simulation_job_by_id(simulation_id)
            if not simulation_job:
                return

            node_mapping_job = enqueue_job(
                map_optimization_nodes,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.OPTIMIZATION_PRE_NODE_MAPPING,
                simulation_id=simulation_id,
            )

            logger.info(
                f"Enqueued node mapping job {node_mapping_job.id} for simulation {simulation_id} after courier mapping completion"
            )

            optimization_job = enqueue_job(
                run_optimization,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.OPTIMIZATION,
                simulation_id=simulation_id,
                depends_on=node_mapping_job,
            )

            logger.info(
                f"Enqueued optimization job {optimization_job.id} for simulation {simulation_id} after node mapping completion"
            )
        except Exception as e:
            raise e