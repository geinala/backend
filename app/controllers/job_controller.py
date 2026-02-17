from app.dtos.responses.job_response_dto import  JobResponseDTO
from app.lib.logging.logging import get_logger
from app.lib.logging.wide_event_logger import wide_event
from app.lib.response_formatter import ResponseFormatter
from app.lib.job_utils import get_job_type_from_job_id
from fastapi.responses import JSONResponse
from app.services.job_service import get_job_status

logger = get_logger(__name__)

class JobController:
    @staticmethod
    async def get_jobs_status(job_ids: list[str]) -> JSONResponse:
        with wide_event("controller_get_jobs_status", job_count=len(job_ids) if job_ids else 0) as event:
            responses: list[JobResponseDTO] = []

            for job_id in job_ids:
                job_type = get_job_type_from_job_id(job_id)
                
                if job_type is None:
                    event["status"] = "invalid_job_id"
                    event["invalid_job_id"] = job_id
                    
                    logger.warning(event)
                    
                    return ResponseFormatter.error(
                        message=f"Invalid job ID: {job_id}",
                        status_code=400
                    )
            
                job_status = get_job_status(job_id=job_id, job_type=job_type)
                responses.append(JobResponseDTO(job_id=job_id, status=job_status))
            
            event["retrieved_count"] = len(responses)
            
            return ResponseFormatter.success_with_data(
                data=responses,
                message="Job status retrieved successfully",
                status_code=200
            )


