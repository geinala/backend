from app.lib.logging.logging import get_logger
from app.services.job_service import enqueue_job
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.configs.worker_configuration import JobType
from app.lib.response_formatter import ResponseFormatter
from app.workers.optimization_worker import optimize as run_optimization

logger = get_logger(__name__)

class OptimizeController:
    async def optimize(self, simulation_id: str):
        try:
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