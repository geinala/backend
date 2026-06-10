from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.repositories.tabu_search_configuration_repository import TabuSearchConfigurationRepository
from app.repositories.tuning_experiment_repository import TuningExperimentRepository
from app.services.tuning_parameter_service import TuningParameterService

logger = get_logger(__name__)

async def calibrate_parameters():
        try:
            db = next(get_db())
            tuning_parameter_service = TuningParameterService(
                tabu_search_configuration_repository=TabuSearchConfigurationRepository(db),
                tuning_experiment_repository=TuningExperimentRepository(db),
            )
            
            await tuning_parameter_service.calibrate_parameters()
            
        except Exception as e:
            logger.error(f"Error calibrating parameters: {str(e)}")
            raise e