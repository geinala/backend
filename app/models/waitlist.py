from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Enum
from datetime import datetime, timezone
import enum
from app.lib.db import Base

class WaitlistStatusEnum(enum.Enum):
    pending = 'pending'
    sending = 'sending'
    confirmed = 'confirmed'
    denied = 'denied'
    invited = 'invited'
    expired = 'expired'
    failed = 'failed'
    revoked = 'revoked'

class Waitlist(Base):
    __tablename__ = 'waitlist'
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    status = Column(Enum(WaitlistStatusEnum, native_enum=False), default=WaitlistStatusEnum.pending)
    invited_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    ticket_id = Column(String, nullable=True, unique=True)
    clerk_invitation_id = Column(String, nullable=True, unique=True)
    
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