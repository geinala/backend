
from pydantic import BaseModel


class TuningExperimentBaseSchema(BaseModel):
    experiment_batch_id: str
    dataset_file_path: str
    algorithm_config_id: int

    base_n_c: int
    it_max: int
    tab_tenure: int
    it_cons: int
    it_div: int

    random_seed: int = 42
    early_stop_no_improvement_iterations: int | None = None


class TuningExperimentCreateSchema(TuningExperimentBaseSchema):
    pass

class TuningExperimentUpdateSchema(BaseModel):
    status: str | None = None
    initial_fitness_score: float | None = None
    best_fitness_score: float | None = None
    execution_time_ms: float | None = None
    convergence_iteration: int | None = None
    improvement_percentage: float | None = None