
import time
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.lib.logging.logging import get_logger
from app.lib.response_formatter import ResponseFormatter
from app.repositories.waitlist_repository import WaitlistRepository
from app.services.invitation_service import InvitationService
from app.services.clerk_service import ClerkService
from app.lib.clerk import get_clerk_sdk
from app.dtos.requests.invitation_request_dto import SendInvitationRequestDTO

logger = get_logger(__name__)

class InvitationsController:
    def __init__(self, db: Session):
        self.db = db
        self.waitlist_repository = WaitlistRepository(db)
        self.clerk_client = next(get_clerk_sdk())
        self.clerk_service = ClerkService(self.clerk_client)
        self.invitation_service = InvitationService(
            self.waitlist_repository,
            self.clerk_service
        )
        
    async def enqueue_bulk_invitations(self, request: SendInvitationRequestDTO) -> JSONResponse:
        start_time = time.time()
        waitlist_ids = request.waitlist_ids
        waitlist_count = len(waitlist_ids)
        
        wide_event: dict[str, object] = {
            "event_type": "invitation_request",
            "waitlist_count": waitlist_count,
            "waitlist_ids": waitlist_ids,
            "status": "processing",
        }

        result = await self.invitation_service.enqueue_bulk_invitations(waitlist_ids)
        
        wide_event["status"] = "success"
        wide_event["job_count"] = len(result)
        wide_event["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(wide_event)
        
        return ResponseFormatter.success_with_data(
            data=result,
            message="Invitations have been enqueued for processing",
            status_code=200
        )