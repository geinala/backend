import time
from rq.job import get_current_job

from app.lib.logging.logging import get_logger
from app.lib.db import get_db

from pydantic import ValidationError
from app.schemas.simulation_log_schema import CreateSimulationLog
from typing import Any

logger = get_logger(__name__)


async def create_simulation_log(log_payload: CreateSimulationLog) -> dict[str, Any]:
    job = get_current_job()
    start_time = time.time()

    wide_event: dict[str, object] = {
        "event_type": "worker_create_simulation_log",
        "job_id": job.id if job else None,
        "status": "processing",
    }

    try:
        from app.repositories.simulation_log_repository import SimulationLogRepository
        db_session = get_db()
        db = next(db_session)
        repo = SimulationLogRepository(db)

        await repo.create_log(log_payload)

        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        logger.info(wide_event)

        return {"status": "success"}

    except ValidationError as ve:
        wide_event["status"] = "failed"
        wide_event["error"] = str(ve)
        wide_event["error_type"] = "ValidationError"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000

        logger.error(wide_event)
        raise
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000

        logger.error(wide_event)
        raise
