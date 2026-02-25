
import time
from fastapi.exceptions import ValidationException
from fastapi.responses import JSONResponse
from rq.job import Job
from sqlalchemy.orm import Session

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.dtos.responses.invitation_response_dto import InvitationResponseDTO, RevokeInvitationResponseDTO
from app.lib.logging.logging import get_logger
from app.lib.response_formatter import ResponseFormatter
from app.models.waitlist import WaitlistStatusEnum
from app.repositories.waitlist_repository import WaitlistRepository
from app.services.invitation_service import InvitationService
from app.services.clerk_service import ClerkService
from app.lib.clerk import get_clerk_sdk
from app.dtos.requests.invitation_request_dto import SendInvitationRequestDTO, RevokeInvitationRequestDTO
from app.services.job_service import enqueue_job, get_job_status

logger = get_logger(__name__)

class InvitationsController:
    def __init__(self, db: Session):
        self.db = db
        self.invitation_service = InvitationService(
            WaitlistRepository(db),
            ClerkService(next(get_clerk_sdk()))
        )
        
    async def revoke_bulk_invitations(self, request: RevokeInvitationRequestDTO) -> JSONResponse:
        start_time = time.time()
        waitlist_ids = request.waitlist_ids
        wide_event: dict[str, object] = {
            "event_type": "enqueue_revoke_bulk_invitations",
            "invitation_count": len(waitlist_ids),
            "waitlist_ids": waitlist_ids,
            "status": "processing",
        }
        
        try:
            await self.invitation_service.validate_waitlist_ids(waitlist_ids)
            
            waitlist_with_clerk_invitation_ids = await self.invitation_service.get_clerk_invitation_ids_by_waitlist_ids(waitlist_ids)
            
            jobs: list[Job] = []
            jobs_response: list[RevokeInvitationResponseDTO] = []
            
            for entry in waitlist_with_clerk_invitation_ids:
                waitlist_id = entry["waitlist_id"]
                clerk_invitation_id = entry["clerk_invitation_id"]
                
                job = enqueue_job(
                    'app.workers.invitation_worker.process_revoke_invitations',
                    job_type=JobType.LIGHT,
                    job_prefix=JOB_PREFIXES_ENUM.INVITATION_REVOKE,
                    waitlist_id=waitlist_id,
                    clerk_invitation_id=clerk_invitation_id
                )
                jobs.append(job.id)
                response = RevokeInvitationResponseDTO(
                    job_id=str(job.id),
                    status=get_job_status(job_id=job.id, job_type=JobType.LIGHT),
                    waitlist_id=waitlist_id,
                    clerk_invitation_id=clerk_invitation_id
                )
                jobs_response.append(response)
            
            wide_event["status"] = "success"
            wide_event["job_count"] = len(jobs)
            wide_event["job_ids"] = jobs
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.info(wide_event)
            
            return ResponseFormatter.success_with_data(
                data=jobs_response,
                message="Revoke invitations have been enqueued for processing",
                status_code=200
            )
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.error(wide_event)
            raise e
        
    async def enqueue_bulk_invitations(self, request: SendInvitationRequestDTO) -> JSONResponse:
        start_time = time.time()
        waitlist_ids = request.waitlist_ids
        waitlist_count = len(waitlist_ids)
        
        wide_event: dict[str, object] = {
            "event_type": "enqueue_bulk_invitations",
            "waitlist_count": waitlist_count,
            "waitlist_ids": waitlist_ids,
            "status": "processing",
        }
        
        try:
            await self.invitation_service.validate_waitlist_ids(waitlist_ids, status=WaitlistStatusEnum.sending)
            
            jobs: list[Job] = []
            jobs_response: list[InvitationResponseDTO] = []
            
            for waitlist_id in waitlist_ids:
                job = enqueue_job(
                    'app.workers.invitation_worker.process_invitations',
                    job_type=JobType.LIGHT,
                    job_prefix=JOB_PREFIXES_ENUM.INVITATION,
                    waitlist_id=waitlist_id
                )
                jobs.append(job.id)
                
                job_status = get_job_status(job_id=job.id, job_type=JobType.LIGHT)
                
                response = InvitationResponseDTO(
                    job_id=str(job.id),
                    status=job_status,
                    waitlist_id=waitlist_id
                )
                
                jobs_response.append(response)
            
            job_ids = [str(job_id) for job_id in jobs]
            
            wide_event["status"] = "success"
            wide_event["job_count"] = len(job_ids)
            wide_event["job_ids"] = job_ids
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return ResponseFormatter.success_with_data(
                data=jobs_response,
                message="Invitations have been enqueued for processing",
                status_code=200
            )
        
        except ValidationException as ve:
            wide_event["status"] = "validation_error"
            wide_event["error"] = ve.errors
            wide_event["error_type"] = type(ve).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.warning(wide_event)
            raise ve
            
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e