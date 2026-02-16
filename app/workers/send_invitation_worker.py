import time
from rq.job import get_current_job

from app.lib import get_logger, get_db
from app.lib.clerk import get_clerk_sdk
from app.repositories import WaitlistRepository
from app.services import InvitationService, ClerkService

logger = get_logger(__name__)

async def process_invitations(waitlist_id: int) -> dict[str, object]:
    job = get_current_job()
    start_time = time.time()
    
    wide_event: dict[str, object] = {
        "event_type": "worker_process_invitations",
        "job_id": job.id if job else None,
        "waitlist_id": waitlist_id,
        "status": "processing",
    }
    
    try:
        db_session = get_db()
        waitlist_repository = WaitlistRepository(next(db_session))
        clerk_client = next(get_clerk_sdk())
        clerk_service = ClerkService(clerk_client)
        service = InvitationService(waitlist_repository, clerk_service)
        
        wide_event["stage"] = "sending_invitation"
        
        await service.create_clerk_user_and_send_invitation(waitlist_id)
        
        wide_event["status"] = "success"
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(wide_event)
        
        return {"status": "success", "waitlist_id": waitlist_id}
        
    except Exception as e:
        wide_event["status"] = "failed"
        wide_event["error"] = str(e)
        wide_event["error_type"] = type(e).__name__
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.error(wide_event)
        raise e