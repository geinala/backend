from datetime import datetime, timedelta, timezone
import time

from app.lib.logging.logging import get_logger
from app.models.waitlist import WaitlistStatusEnum, WaitlistUpdateData
from app.repositories.waitlist_repository import ClerkInvitationMapping, WaitlistRepository
from app.services.clerk_service import ClerkService


logger = get_logger(__name__)

class InvitationService:
    def __init__(self, waitlist_repository: WaitlistRepository, clerk_service: ClerkService):
        self.waitlist_repository = waitlist_repository
        self.clerk_service = clerk_service
    
    async def get_clerk_invitation_ids_by_waitlist_ids(self, waitlist_ids: list[int]) -> list[ClerkInvitationMapping]:
        return await self.waitlist_repository.get_clerk_invitation_ids_by_waitlist_ids(waitlist_ids)
    
    async def validate_waitlist_ids(self, waitlist_ids: list[int], status: WaitlistStatusEnum | None = None) -> bool:
        valid_ids: list[int] = await self.waitlist_repository.get_valid_waitlist_ids(waitlist_ids, status=status)
        valid_ids_set: set[int] = set(valid_ids)
        requested_ids_set: set[int] = set(waitlist_ids)
        
        invalid_ids: set[int] = requested_ids_set - valid_ids_set
        
        if invalid_ids:
            logger.warning(f"Invalid waitlist IDs or status mismatch: {list(invalid_ids)}")
            return False
        
        return True
    
    async def revoke_clerk_invitation(self, waitlist_id: int, clerk_invitation_id: str):
        start_time = time.time()
        
        wide_event: dict[str, object] = {
            "event_type": "revoke_invitation",
            "clerk_invitation_id": clerk_invitation_id,
            "status": "processing",
        }
        
        try:
            await self.clerk_service.revoke_invitation(clerk_invitation_id)
            
            await self.waitlist_repository.update_waitlist_entry(
                waitlist_id, 
                WaitlistUpdateData(status=WaitlistStatusEnum.revoked, clerk_invitation_id=None, expired_at=None)
            )
            
            wide_event["status"] = "success"    
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.info(wide_event)
            
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.error(wide_event)
            
            raise e
    
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
            wide_event["email"] = waitlist_entry.email
            
            result = await self.clerk_service.invite_user(email_address=waitlist_entry.email.__str__(), ticket=waitlist_entry.ticket_id.__str__())
                
            await self.waitlist_repository.update_waitlist_entry(
                waitlist_id, 
                WaitlistUpdateData(
                    status=WaitlistStatusEnum.invited, 
                    clerk_invitation_id=result.id, 
                    invited_at=datetime.now(timezone.utc),
                    expired_at=datetime.now(timezone.utc) + timedelta(days=30)
                )
            )
                
            wide_event["status"] = "success"    
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.info(wide_event)
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.error(wide_event)
            
            await self.waitlist_repository.update_waitlist_entry(waitlist_id,
                WaitlistUpdateData(status=WaitlistStatusEnum.failed)
            )
            
            raise e