import time
from rq import get_current_job

from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.repositories.matrix_repository import MatrixRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.courier_repository import CourierRepository
from app.services.matrix_service import MatrixService
from app.services.solver_service import SolverAlgorithm, SolverService
from app.services.tomtom_service import TomTomService
from app.types.solver_algorithm_types import SolverAlgorithm

logger = get_logger(__name__)


async def solve_courier(simulation_id: str, courier_id: int, algorithm: SolverAlgorithm = SolverAlgorithm.TABU_SEARCH):
    job = get_current_job()
    start_time = time.time()

    wide_event: dict[str, object] = {
        "event_type": "worker_solve_courier",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "courier_id": courier_id,
        "status": "processing",
    }

    try:
        db_session = get_db()
        db = next(db_session)

        solver_service = SolverService(
            matrix_service=MatrixService(
                matrix_repository=MatrixRepository(db),
                node_repository=NodeRepository(db),
                tomtom_service=TomTomService(),
                simulation_repository=SimulationRepository(db),
            ),
            courier_repository=CourierRepository(db),
            node_repository=NodeRepository(db),
            solution_repository=SolutionRepository(db),
            simulation_repository=SimulationRepository(db),
        )

        wide_event["stage"] = "solving_courier"
        created = await solver_service.solve_courier(simulation_id, courier_id, algorithm)

        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        wide_event["created_solution"] = created.courier_id if created else None
        logger.info(wide_event)

    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(wide_event)
        raise
