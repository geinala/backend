from typing import List
from fastapi.responses import JSONResponse
from app.controllers.job_controller import JobController
from app.lib.logging.logging import get_logger
from app.lib.logging.wide_event_logger import wide_event
from fastapi import APIRouter, Query

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get(path="", summary="Get details of all background jobs")
async def get_jobs(job_ids: List[str] = Query(default=None, max_length=20)) -> JSONResponse:
    with wide_event("get_jobs_status", job_count=len(job_ids) if job_ids else 0, job_ids=job_ids):
        return await JobController.get_jobs_status(job_ids)

