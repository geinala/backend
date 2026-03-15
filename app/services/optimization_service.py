from typing import Any, Callable

from rq.job import Job

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.repositories.simulation_repository import SimulationRepository
from app.services.job_service import enqueue_job
from app.services.matrix_service import MatrixService
from app.workers.matrix_worker import generate_matrices, get_matrix_results
from app.workers.solver_worker import get_solution
from app.workers.route_worker import generate_routes

class OptimizationService:
    def __init__(self, matrix_service: MatrixService, simulation_repository: SimulationRepository):
        self.matrix_service = matrix_service
        self.simulation_repository = simulation_repository
        
    async def optimize(self, simulation_id: str) -> None:
        has_batches = self.matrix_service.has_batches(simulation_id)
        
        run_matrix_gen = not has_batches
        run_matrix_processing = run_matrix_gen or await self.matrix_service.has_pending_batches(simulation_id)
        
        last_job: Job | None = None
        
        def add_job(
            func: str | Callable[..., Any],
            prefix: str | None,
            depends_on: Job | list[Job] | None,
        ) -> Job:
            kwargs = {"depends_on": depends_on} if depends_on else {}
            return enqueue_job(
                func,
                job_type=JobType.HEAVY,
                job_prefix=prefix,
                simulation_id=simulation_id,
                **kwargs
            )

        if run_matrix_gen:
            last_job = add_job(generate_matrices, JOB_PREFIXES_ENUM.MATRIX_GENERATION, last_job)
            
        if run_matrix_processing:
            last_job = add_job(get_matrix_results, JOB_PREFIXES_ENUM.MATRIX_RESULT_PROCESSING, last_job)
            
        last_job = add_job(get_solution, JOB_PREFIXES_ENUM.GET_OPTIMIZATION_RESULT, last_job)
        
        add_job(generate_routes, JOB_PREFIXES_ENUM.ROUTE_GENERATION, last_job)