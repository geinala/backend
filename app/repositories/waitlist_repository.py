
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.lib import get_logger
from app.models import Waitlist, WaitlistStatusEnum

logger = get_logger(__name__)

class WaitlistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
    
    async def validate_waitlist_ids(self, waitlist_ids: list[int]) -> bool:
        existing_ids = self.db.query(Waitlist.id).filter(Waitlist.id.in_(waitlist_ids)).all()
        existing_ids_set = set(id for (id,) in existing_ids)
        invalid_ids = [id for id in waitlist_ids if id not in existing_ids_set]
        
        if invalid_ids:
            logger.warning(f"Invalid waitlist IDs: {invalid_ids}")
            return False
        
        return True
        
    
    async def get_waitlist_entries_by_id(self, waitlist_id: int) -> Waitlist | None:
        result = self.db.query(Waitlist).filter(Waitlist.id == waitlist_id).first()
        return result

    async def update_waitlist_entry_status(self, waitlist_id: int, new_status: WaitlistStatusEnum):
        
        waitlist_entry = await self.get_waitlist_entries_by_id(waitlist_id)
        
        if not waitlist_entry:
            logger.warning(f"Waitlist entry with ID {waitlist_id} not found for status update.")
            return None
        
        waitlist_entry.status = new_status  # type: ignore[assignment]
        waitlist_entry.invited_at = datetime.now(timezone.utc) # type: ignore[assignment]
        waitlist_entry.expired_at = datetime.now(timezone.utc) # type: ignore[assignment]
        waitlist_entry.ticket_id = waitlist_entry.generate_ticket_id() # type: ignore[assignment]
        
        self.db.commit()
        self.db.refresh(waitlist_entry)
        
        return waitlist_entry