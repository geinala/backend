from app.constants.simulation_log_event_types import SIMULATION_STARTED
from app.lib.logging.logging import get_logger
from app.schemas.simulation_log_schema import CreateSimulationLog
from app.services.job_service import enqueue_job
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.configs.worker_configuration import JobType
from app.lib.response_formatter import ResponseFormatter
from app.workers.optimization_worker import optimize as run_optimization
from app.workers.log_worker import create_simulation_log

logger = get_logger(__name__)

class OptimizeController:
    async def optimize(self, simulation_id: str):
        try:
            log_payload: CreateSimulationLog = CreateSimulationLog(
                simulation_id=simulation_id,
                event_type=SIMULATION_STARTED,
                title=f"Optimization started for simulation {simulation_id}",
                description=f"Optimization process has been initiated for simulation {simulation_id}"
            )

            enqueue_job(
                create_simulation_log,
                job_type=JobType.LIGHT,
                job_prefix=JOB_PREFIXES_ENUM.SIMULATION_LOG,
                log_payload=log_payload
            )
            
            job = enqueue_job(
                run_optimization,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.OPTIMIZATION,
                simulation_id=simulation_id
            )
            
            logger.info(f"Enqueued optimization job {job.id} for simulation {simulation_id}")
            
            return ResponseFormatter.success_with_data(
                data={"job_id": str(job.id)},
                message="Optimization has been enqueued for processing",
                status_code=200
            )
        except Exception as e:
            logger.error(f"Error optimizing simulation {simulation_id}: {str(e)}")
            raise e