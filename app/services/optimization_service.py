from typing import Any, Callable
from uuid import UUID

from app.lib.logging.logging import get_logger
from rq.job import Job

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.constants.simulation_log_event_types import INITIAL_ROUTE_GENERATED, OPTIMIZATION_COMPLETED, OPTIMIZATION_STARTED, ROUTE_GENERATION_STARTED
from app.repositories.simulation_repository import SimulationRepository
from app.services.job_service import enqueue_job
from app.services.matrix_service import MatrixService
from app.workers.solver_worker import get_solution_with_manual_solver
from app.workers.route_worker import generate_routes
from app.workers.log_worker import create_simulation_log
from app.schemas.simulation_log_schema import SimulationLogCreate
from app.workers.pre_optimization.courier_mapping_worker import map_couriers as map_couriers_to_simulation
from app.workers.pre_optimization.node_mapping_worker import map_nodes as map_optimization_nodes

logger = get_logger(__name__)

class OptimizationService:
    def __init__(self, matrix_service: MatrixService, simulation_repository: SimulationRepository):
        self.matrix_service = matrix_service
        self.simulation_repository = simulation_repository
        
    async def optimize(self, simulation_id: str) -> None:
        simulation = await self.simulation_repository.get_simulation_by_id(simulation_id)
        
        if simulation is None:
            logger.error(f"Simulation with ID {simulation_id} not found")
            raise ValueError(f"Simulation with ID {simulation_id} not found")
        
        last_job: Job | None = None

        def add_job(
            func: str | Callable[..., Any],
            prefix: str | None,
            depends_on: Job | list[Job] | None,
            job_timeout: int | None = None,
            simulation_job_id: str | None = None,
            simulation_id: str | None = None
        ) -> Job:
            kwargs: dict[str, Any] = {}
            
            if simulation_id is not None:
                kwargs["simulation_id"] = simulation_id
            
            if job_timeout is not None:
                kwargs["job_timeout"] = job_timeout
                
            if simulation_job_id is not None:
                kwargs["simulation_job_id"] = simulation_job_id
                
            return enqueue_job(
                func,
                job_type=JobType.HEAVY,
                job_prefix=prefix,
                depends_on=depends_on,
                **kwargs
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
                log_payload=SimulationLogCreate(
                    simulation_id=UUID(simulation_id),
                    event_type=event_type,
                    title=title,
                    description=description,
                    log_level="INFO"
                ),
                depends_on=depends_on,
            )
            
        logger.info(f"Enqueued simulation log for optimization start of simulation {simulation_id}")
            
        last_job = add_job(
            map_couriers_to_simulation,
            JOB_PREFIXES_ENUM.OPTIMIZATION_PRE_COURIER_MAPPING,
            simulation_job_id=str(simulation.simulation_job_id),
            job_timeout=3600,
            depends_on=last_job
        )

        logger.info(f"Enqueued courier mapping job {last_job.id} for simulation {simulation_id}")

        last_job = add_job(
            map_optimization_nodes,
            JOB_PREFIXES_ENUM.OPTIMIZATION_PRE_NODE_MAPPING,
            simulation_job_id=str(simulation.simulation_job_id),
            depends_on=last_job,
            job_timeout=3600
        )

        add_log(
            OPTIMIZATION_STARTED,
            f"Optimization started for simulation {simulation_id}",
            f"Optimization process has been initiated for simulation {simulation_id}",
            depends_on=last_job,
        )

        last_job = add_job(
            get_solution_with_manual_solver,
            JOB_PREFIXES_ENUM.GET_OPTIMIZATION_RESULT,
            last_job, job_timeout=3600, simulation_id=simulation_id
        )

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

        last_job = add_job(generate_routes, JOB_PREFIXES_ENUM.ROUTE_GENERATION, last_job, job_timeout=3600, simulation_id=simulation_id)

        add_log(
            INITIAL_ROUTE_GENERATED,
            f"Initial route generated for simulation {simulation_id}",
            f"Initial route has been generated for simulation {simulation_id}",
            depends_on=last_job
        )