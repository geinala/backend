from enum import Enum

from app.configs.worker_configuration import JobType

class JOB_PREFIXES_ENUM(str, Enum):
    INVITATION = JobType.LIGHT.value + "-" + "invitation"
    INVITATION_REVOKE = JobType.LIGHT.value + "-" + "invitation_revoke"
    SIMULATION_JOB_PROCESSING_DATA = JobType.HEAVY.value + "-" + "simulation_process_files"
    SIMULATION_JOB_CLEANING_DATA = JobType.HEAVY.value + "-" + "simulation_clean_uploaded_rows"
    SIMULATION_JOB_GEOCODING = JobType.HEAVY.value + "-" + "simulation_geocoding"
    SIMULATION_JOB_REVALIDATION = JobType.HEAVY.value + "-" + "simulation_revalidation"
    MATRIX_GENERATION = JobType.HEAVY.value + "-" + "matrix_generation"
    MATRIX_STATUS_CHECK = JobType.LIGHT.value + "-" + "matrix_status_check"
    MATRIX_RESULT_PROCESSING = JobType.HEAVY.value + "-" + "matrix_result_processing"
    OPTIMIZATION = JobType.HEAVY.value + "-" + "optimization"
    GET_OPTIMIZATION_RESULT = JobType.HEAVY.value + "-" + "get_optimization_result"
    ROUTE_GENERATION = JobType.HEAVY.value + "-" + "route_generation"
