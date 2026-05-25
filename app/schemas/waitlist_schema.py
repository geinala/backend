from datetime import datetime

from pydantic import BaseModel

from app.models.waitlist import WaitlistStatusEnum


class WaitlistUpdateData(BaseModel):
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    status: WaitlistStatusEnum | None = None
    invited_at: datetime | None = None
    expired_at: datetime | None = None
    confirmed_at: datetime | None = None
    ticket_id: str | None = None
    clerk_invitation_id: str | None = None

    class Config:
        from_attributes = True
