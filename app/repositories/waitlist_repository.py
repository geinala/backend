
from sqlalchemy.orm import Session
from typing import TypedDict

from app.lib.logging.logging import get_logger
from app.models.waitlist import Waitlist, WaitlistStatusEnum, WaitlistUpdateData

logger = get_logger(__name__)

class ClerkInvitationMapping(TypedDict):
    waitlist_id: int
    clerk_invitation_id: str

class WaitlistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        
    async def get_clerk_invitation_ids_by_waitlist_ids(self, waitlist_ids: list[int]) -> list[ClerkInvitationMapping]:
        results = self.db.query(Waitlist.id, Waitlist.clerk_invitation_id).filter(Waitlist.id.in_(waitlist_ids)).all()
        return [{"waitlist_id": waitlist_id, "clerk_invitation_id": clerk_id} for waitlist_id, clerk_id in results if clerk_id is not None]
          
    async def get_valid_waitlist_ids(self, waitlist_ids: list[int], status: WaitlistStatusEnum | None = None) -> list[int]:
        query = self.db.query(Waitlist.id).filter(Waitlist.id.in_(waitlist_ids))
        
        if status:
            query = query.filter(Waitlist.status == status)
        
        results = query.all()
        return [id_tuple[0] for id_tuple in results]
    
    async def get_waitlist_entries_by_id(self, waitlist_id: int) -> Waitlist | None:
        result = self.db.query(Waitlist).filter(Waitlist.id == waitlist_id).first()
        return result

    async def update_waitlist_entry(self, waitlist_id: int, update_data: WaitlistUpdateData) -> Waitlist | None:
        waitlist_entry = await self.get_waitlist_entries_by_id(waitlist_id)
        
        if not waitlist_entry:
            logger.warning(f"Waitlist entry with ID {waitlist_id} not found for update.")
            return None
        
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if hasattr(waitlist_entry, field):
                setattr(waitlist_entry, field, value)  # type: ignore[assignment]
            else:
                logger.warning(f"Waitlist model does not have field: {field}")
        
        self.db.commit()
        self.db.refresh(waitlist_entry)
        
        return waitlist_entry