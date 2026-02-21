
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.lib.logging.logging import get_logger
from app.lib.db import get_db
from app.dtos.requests.invitation_request_dto import SendInvitationRequestDTO, RevokeInvitationRequestDTO
from app.controllers.invitation_controller import InvitationsController

logger = get_logger(__name__)

router = APIRouter(prefix="/invitations", tags=["Invitations"])

@router.post(
    path="", 
    summary="Send bulk invitations", 
    responses={
        200: {
            "description": "Invitations enqueued successfully", 
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Invitations enqueued successfully",
                        "data": [
                            {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "queued",
                                "message": "Invitation job 123e4567-e89b-12d3-a456-426614174000 has been enqueued"
                            },
                            {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "queued",
                                "message": "Invitation job 123e4567-e89b-12d3-a456-426614174000 has been enqueued"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def send_invitation(
    request: SendInvitationRequestDTO,
    db: Session = Depends(get_db)
):
    controller = InvitationsController(db)
    return await controller.enqueue_bulk_invitations(request)

@router.post(
    path="/revoke/bulk",
    summary="Revoke bulk invitations",
    responses={
        200: {
            "description": "Invitations revoked successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Invitations revoked successfully",
                        "data": [
                            {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "queued",
                                "message": "Revocation job 123e4567-e89b-12d3-a456-426614174000 has been enqueued"
                            },
                            {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "queued",
                                "message": "Revocation job 123e4567-e89b-12d3-a456-426614174000 has been enqueued"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def revoke_bulk_invitations(
    request: RevokeInvitationRequestDTO,
    db: Session = Depends(get_db)
):
    controller = InvitationsController(db)
    return await controller.revoke_bulk_invitations(request)