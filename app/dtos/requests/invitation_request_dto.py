from pydantic import BaseModel, Field

class SendInvitationRequestDTO(BaseModel):
    waitlist_ids: list[int] = Field(..., min_length=1, description="List of waitlist IDs to send invitations for")
    
class RevokeInvitationRequestDTO(SendInvitationRequestDTO):
    pass