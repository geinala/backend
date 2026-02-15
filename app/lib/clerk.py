from clerk_backend_api import Clerk
from app.lib import get_logger

from app.configs import get_environment_configuration

logger = get_logger(__name__)

def get_clerk_sdk():
    secret_key = get_environment_configuration().CLERK_SECRET_KEY
    clerk = Clerk(bearer_auth=secret_key)
    yield clerk