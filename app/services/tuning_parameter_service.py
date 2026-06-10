import statistics

from app.lib.logging.logging import get_logger
from app.repositories.tabu_search_configuration_repository import TabuSearchConfigurationRepository
from app.repositories.tuning_experiment_repository import TuningExperimentRepository
from app.schemas.tabu_search_configuration_schema import TabuSearchConfigurationCreate

logger = get_logger(__name__)

class TuningParameterService:
    def __init__(
        self,
        tabu_search_configuration_repository: TabuSearchConfigurationRepository,
        tuning_experiment_repository: TuningExperimentRepository,
    ):
        self.tuning_experiment_repository = tuning_experiment_repository
        self.tabu_search_configuration_repository = tabu_search_configuration_repository
        
    async def calibrate_parameters(self):
        try:
            logger.info("Calibrating parameters based on the latest tuning experiments")
            
            tuning_experiments = await self.tuning_experiment_repository.get_newest_tuning_experiments()
            
            if not tuning_experiments or len(tuning_experiments) == 0:
                return
            
            multipliers_it_max: list[float] = []
            dividers_tab_tenure: list[float] = []
            multipliers_it_cons: list[float] = []
            dividers_it_div: list[float] = []
            
            for experiment in tuning_experiments:
                base_n_c = experiment.base_n_c
                
                if base_n_c <= 0:
                    continue
                
                # Reverse-engineer untuk mendapatkan kembali nilai opsi pengali/pembagi
                # it_max (pengali: 5, 10, 15) -> dibulatkan penuh
                multipliers_it_max.append(round(experiment.it_max / base_n_c))
                
                # it_cons (pengali: 0.5, 1, 2) -> dibulatkan 1 desimal untuk menjaga 0.5
                multipliers_it_cons.append(round(experiment.it_cons / base_n_c, 1))
                
                # tab_tenure (pembagi: 6, 3, 2) -> n_c / nilai riil
                if experiment.tab_tenure > 0:
                    dividers_tab_tenure.append(round(base_n_c / experiment.tab_tenure))
                    
                # it_div (pembagi: 10, 5, 2, 1)
                if experiment.it_div > 0:
                    dividers_it_div.append(round(base_n_c / experiment.it_div))
                    
            best_it_max = statistics.mode(multipliers_it_max) if multipliers_it_max else 10.0
            best_tab_tenure = statistics.mode(dividers_tab_tenure) if dividers_tab_tenure else 3.0
            best_it_cons = statistics.mode(multipliers_it_cons) if multipliers_it_cons else 1.0
            best_it_div = statistics.mode(dividers_it_div) if dividers_it_div else 5.0
            
            active_config = await self.tabu_search_configuration_repository.get_active_tabu_search_configuration()
            
            new_config_payload = TabuSearchConfigurationCreate(
                it_max_multiplier=float(best_it_max),
                tab_tenure_divider=float(best_tab_tenure),
                it_cons_multiplier=float(best_it_cons),
                it_div_divider=float(best_it_div),
                is_active=True if active_config is None else False,  # Aktifkan hanya jika belum ada konfigurasi aktif
            )
            
            await self.tabu_search_configuration_repository.create_tabu_search_configuration(
                data=new_config_payload
            )
            
        except Exception as e:
            raise e