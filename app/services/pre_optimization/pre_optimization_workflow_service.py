from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.lib.logging.logging import get_logger
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.services.job_service import enqueue_job
from app.workers.pre_optimization.courier_mapping_worker import map_couriers as map_couriers_to_simulation
from app.workers.pre_optimization.node_mapping_worker import map_nodes as map_optimization_nodes

logger = get_logger(__name__)


class PreOptimizationWorkflowService:
    def __init__(
        self,
        simulation_job_repository: SimulationJobRepository,
    ):
        self.simulation_job_repository = simulation_job_repository

    async def continue_workflow_after_courier_mapping(self, simulation_job_id: str):
        try:
            courier_mapping_job = enqueue_job(
                map_couriers_to_simulation,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.OPTIMIZATION_PRE_COURIER_MAPPING,
                simulation_job_id=simulation_job_id,
            )
            
            logger.info(
                f"Enqueued courier mapping job {courier_mapping_job.id} for simulation {simulation_job_id} after courier mapping completion"
            )

            node_mapping_job = enqueue_job(
                map_optimization_nodes,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.OPTIMIZATION_PRE_NODE_MAPPING,
                simulation_job_id=simulation_job_id,
                depends_on=courier_mapping_job,
            )

            logger.info(
                f"Enqueued node mapping job {node_mapping_job.id} for simulation {simulation_job_id} after courier mapping completion"
            )

        except Exception as e:
            raise e