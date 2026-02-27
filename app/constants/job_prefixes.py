from enum import Enum

from app.configs.worker_configuration import JobType

class JOB_PREFIXES_ENUM(str, Enum):
    INVITATION = JobType.LIGHT.value + "-" + "invitation"
    INVITATION_REVOKE = JobType.LIGHT.value + "-" + "invitation_revoke"
    SIMULATION_PROCESSING_DATA = JobType.HEAVY.value + "-" + "simulation_process_files"