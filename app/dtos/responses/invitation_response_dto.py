
from app.dtos.responses.job_response_dto import JobResponseDTO

class InvitationResponseDTO(JobResponseDTO):
    waitlist_id: int
    
class RevokeInvitationResponseDTO(InvitationResponseDTO):
    clerk_invitation_id: str