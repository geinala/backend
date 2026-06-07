from typing import Any, Callable

from rq.job import Job

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.constants.simulation_log_event_types import INITIAL_ROUTE_GENERATED, MATRIX_GENERATION_STARTED, MATRIX_RESULTS_PROCESSING_COMPLETED, MATRIX_RESULTS_PROCESSING_STARTED, OPTIMIZATION_COMPLETED, OPTIMIZATION_STARTED, ROUTE_GENERATION_STARTED
from app.repositories.simulation_repository import SimulationRepository
from app.services.job_service import enqueue_job
from app.services.matrix_service import MatrixService
from app.workers.matrix_worker import generate_matrices, get_matrix_results
from app.workers.solver_worker import get_solution
from app.workers.route_worker import generate_routes
from app.workers.log_worker import create_simulation_log
from app.schemas.simulation_log_schema import CreateSimulationLog

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
            job_timeout: int | None = None,
        ) -> Job:
            return enqueue_job(
                func,
                job_type=JobType.HEAVY,
                job_prefix=prefix,
                depends_on=depends_on,
                simulation_id=simulation_id,
                job_timeout=job_timeout,
            )

        def add_log(
            event_type: str,
            title: str,
            description: str,
            depends_on: Job | list[Job] | None = None,
        ) -> Job:
            return enqueue_job(
                create_simulation_log,
                job_type=JobType.LIGHT,
                job_prefix=JOB_PREFIXES_ENUM.SIMULATION_LOG,
                log_payload=CreateSimulationLog(
                    simulation_id=simulation_id,
                    event_type=event_type,
                    title=title,
                    description=description,
                ),
                depends_on=depends_on,
            )

        if run_matrix_gen:
            add_log(
                MATRIX_GENERATION_STARTED,
                f"Matrix generation started for simulation {simulation_id}",
                f"Matrix generation process has been initiated for simulation {simulation_id}",
            )

            add_job(generate_matrices, JOB_PREFIXES_ENUM.MATRIX_GENERATION, last_job)

            return

        if run_matrix_processing:
            add_log(
                MATRIX_RESULTS_PROCESSING_STARTED,
                f"Matrix result processing started for simulation {simulation_id}",
                f"Matrix result processing has been initiated for simulation {simulation_id}",
                depends_on=last_job,
            )
            last_job = add_job(get_matrix_results, JOB_PREFIXES_ENUM.MATRIX_RESULT_PROCESSING, last_job)
            add_log(
                MATRIX_RESULTS_PROCESSING_COMPLETED,
                f"Matrix results ready for optimization for simulation {simulation_id}",
                f"Matrix results have been processed for simulation {simulation_id}",
                depends_on=last_job,
            )

        add_log(
            OPTIMIZATION_STARTED,
            f"Optimization started for simulation {simulation_id}",
            f"Optimization process has been initiated for simulation {simulation_id}",
            depends_on=last_job,
        )

        last_job = add_job(get_solution, JOB_PREFIXES_ENUM.GET_OPTIMIZATION_RESULT, last_job, job_timeout=3600)

        add_log(
            OPTIMIZATION_COMPLETED,
            f"Optimization completed for simulation {simulation_id}",
            f"Optimization process has been completed for simulation {simulation_id}",
            depends_on=last_job,
        )

        add_log(
            ROUTE_GENERATION_STARTED,
            f"Route generation started for simulation {simulation_id}",
            f"Route generation has been initiated for simulation {simulation_id}",
            depends_on=last_job,
        )

        last_job = add_job(generate_routes, JOB_PREFIXES_ENUM.ROUTE_GENERATION, last_job, job_timeout=3600)

        add_log(
            INITIAL_ROUTE_GENERATED,
            f"Initial route generated for simulation {simulation_id}",
            f"Initial route has been generated for simulation {simulation_id}",
            depends_on=last_job
        )