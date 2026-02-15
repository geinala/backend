import time

from fastapi.exceptions import ValidationException
from app.lib import get_logger
from app.configs import enqueue_job, JobType
from app.repositories import WaitlistRepository
from app.services.clerk_service import ClerkService
from app.dtos import ClerkUserDTO
from rq.job import Job
from app.dtos import JobStatusEnum, InvitationResponseDTO


logger = get_logger(__name__)

class InvitationService:
    def __init__(self, waitlist_repository: WaitlistRepository, clerk_service: ClerkService):
        self.waitlist_repository = waitlist_repository
        self.clerk_service = clerk_service
    
    async def create_clerk_user_and_send_invitation(self, waitlist_id: int):
        start_time = time.time()
        
        wide_event: dict[str, object] = {
            "event_type": "send_invitation",
            "waitlist_id": waitlist_id,
            "status": "processing",
        }
        
        try:
            waitlist_entry = await self.waitlist_repository.get_waitlist_entries_by_id(waitlist_id)
            
            if not waitlist_entry:
                wide_event["status"] = "skipped"
                wide_event["reason"] = "no_pending_entry"
                wide_event["duration_ms"] = (time.time() - start_time) * 1000
                logger.info(wide_event)
                return
            
            wide_event["user_id"] = waitlist_entry.id
            wide_event["first_name"] = waitlist_entry.first_name
            
            try:
                clerk_user = await self.clerk_service.create_user(ClerkUserDTO(
                    first_name=str(waitlist_entry.first_name),
                    last_name=str(waitlist_entry.last_name),
                    email_address=[str(waitlist_entry.email)],
                    public_metadata={"is_onboarded": True},
                    delete_self_enabled=True
                ))
                
                wide_event["clerk_user_id"] = clerk_user.id
                
                await self.clerk_service.invite_user(clerk_user.email_addresses[0].email_address)
                
                await self.waitlist_repository.update_waitlist_entry_status(waitlist_id, waitlist_entry.status.invited)
                
                wide_event["status"] = "success"
                
            except Exception as clerk_error:
                wide_event["status"] = "failed_clerk_operation"
                wide_event["error"] = str(clerk_error)
                logger.error(wide_event)
                raise clerk_error
            
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.info(wide_event)
        
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.error(wide_event)
            raise e
        
    async def enqueue_bulk_invitations(self, waitlist_ids: list[int]) -> list[InvitationResponseDTO]:
        start_time = time.time()
        waitlist_ids = waitlist_ids
        waitlist_count = len(waitlist_ids)
        
        wide_event: dict[str, object] = {
            "event_type": "enqueue_bulk_invitations",
            "waitlist_count": waitlist_count,
            "waitlist_ids": waitlist_ids,
            "status": "processing",
        }
        
        try:
            is_valid_ids = await self.waitlist_repository.validate_waitlist_ids(waitlist_ids)
            
            if not is_valid_ids:
                wide_event["status"] = "failed"
                wide_event["reason"] = "invalid_waitlist_ids"
                wide_event["duration_ms"] = (time.time() - start_time) * 1000
                logger.warning(wide_event)
                raise ValidationException(errors="One or more waitlist IDs are invalid")
            
            jobs: list[Job] = []
            jobs_response: list[InvitationResponseDTO] = []
            
            for waitlist_id in waitlist_ids:
                job = enqueue_job(
                    'app.workers.send_invitation_worker.process_invitations',
                    job_type=JobType.LIGHT,
                    waitlist_id=waitlist_id
                )
                jobs.append(job.id)
                
                response = InvitationResponseDTO(
                    job_id=str(job.id),
                    status=JobStatusEnum.QUEUED,
                    message=f"Invitation job {job.id} has been enqueued",
                    waitlist_id=waitlist_id
                )
                
                jobs_response.append(response)
            
            job_ids = [str(job_id) for job_id in jobs]
            
            wide_event["status"] = "success"
            wide_event["job_count"] = len(job_ids)
            wide_event["job_ids"] = job_ids
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return jobs_response
        
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
        