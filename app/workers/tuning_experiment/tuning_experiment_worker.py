
from app.lib.db import get_db
from app.repositories.depot_repository import DepotRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.tuning_experiment_dataset_repository import TuningExperimentDatasetRepository
from app.repositories.tuning_experiment_repository import TuningExperimentRepository
from app.repositories.tuning_experiment_run_repository import TuningExperimentRunRepository
from app.repositories.tuning_experiment_uploaded_row_repository import TuningExperimentUploadedRowRepository
from app.services.tomtom_service import TomTomService
from app.services.tuning_experiment.tuning_experiment_service import TuningExperimentService
from app.services.matrix_service import MatrixService


async def process_tuning_experiment(tuning_experiment_dataset_id: str):
    try:
        db_session = get_db()
        db = next(db_session)
        tuning_experiment_service = TuningExperimentService(
            tuning_experiment_repository=TuningExperimentRepository(db),
            tuning_experiment_run_repository=TuningExperimentRunRepository(db),
            tuning_experiment_uploaded_row_repository=TuningExperimentUploadedRowRepository(db),
            matrix_service=MatrixService(
                tomtom_service=TomTomService(),
                simulation_repository=SimulationRepository(db)
            ),
            depot_repository=DepotRepository(db),
            tuning_experiment_dataset_repository=TuningExperimentDatasetRepository(db)
        )

        await tuning_experiment_service.run_experiment(tuning_experiment_dataset_id=tuning_experiment_dataset_id)
    except Exception as e:
        raise e