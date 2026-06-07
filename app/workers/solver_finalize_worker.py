import time
from rq import get_current_job

from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.schemas.simulation_schema import UpdateSimulationSchema
from app.services.job_service import enqueue_job
from app.repositories.solution_repository import SolutionRepository
from app.repositories.simulation_repository import SimulationRepository
from app.workers.route_worker import generate_routes

logger = get_logger(__name__)


async def finalize_simulation(simulation_id: str):
    job = get_current_job()
    start_time = time.time()
    db = None

    wide_event: dict[str, object] = {
        "event_type": "worker_finalize_solver",
        "job_id": job.id if job else None,
        "simulation_id": simulation_id,
        "status": "processing",
    }

    try:
        db_session = get_db()
        db = next(db_session)

        solution_repo = SolutionRepository(db)
        simulation_repo = SimulationRepository(db)

        wide_event["stage"] = "aggregating_solutions"
        solutions = await solution_repo.get_solutions_by_simulation_id(simulation_id)

        total_demand = sum(sol.demand_in_kilograms for sol in solutions) if solutions else 0
        total_couriers = len(solutions)
        total_active_couriers = len(solutions)

        await simulation_repo.update_simulation(
            simulation_id,
            UpdateSimulationSchema(
                total_demand_in_kilograms=total_demand,
                total_couriers=total_couriers,
                total_active_couriers=total_active_couriers,
            )
        )

        db.commit()

        enqueue_job(
            generate_routes,
            job_type=JobType.HEAVY,
            job_prefix=JOB_PREFIXES_ENUM.ROUTE_GENERATION,
            depends_on=job,
            simulation_id=simulation_id,
        )

        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        wide_event["total_demand"] = total_demand
        wide_event["total_couriers"] = total_couriers
        logger.info(wide_event)

    except Exception as e:
        if db is not None:
            db.rollback()
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.error(wide_event)
        raise
    finally:
        if db is not None:
            db.close()
