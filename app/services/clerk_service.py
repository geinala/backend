import time as time_module
from clerk_backend_api import Clerk, models
from app.configs.environment_configuration import get_environment_configuration

from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

class ClerkService:
    def __init__(self, clerk_client: Clerk):
        self.clerk = clerk_client
        
    async def invite_user(self, email_address: str, ticket: str):
        start_time = time_module.time()
        settings = get_environment_configuration()
        
        wide_event: dict[str, object] = {
            "event_type": "clerk_send_invitation",
            "email": email_address,
            "status": "processing",
        }
        
        try:
            self.clerk.invitations.create(request={
                'email_address': email_address,
                'redirect_url': settings.FRONTEND_URL + '/ticket?token=' + ticket,
                'template_slug': models.TemplateSlug.INVITATION,
                'ignore_existing': True
            })
            
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.info(wide_event)
            
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e