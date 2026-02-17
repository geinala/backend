import hashlib
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Enum
from datetime import datetime, timezone
import enum

Base = declarative_base()

class WaitlistStatusEnum(enum.Enum):
    pending = 'pending'
    sending = 'sending'
    confirmed = 'confirmed'
    rejected = 'rejected'
    invited = 'invited'
    expired = 'expired'

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

    def generate_ticket_id(self):
        email_normalized = self.email.strip().lower()
        hashed = hashlib.sha256(email_normalized.encode()).hexdigest()
        return hashed[:16]