
from pydantic import BaseModel


class TuningExperimentRunBaseSchema(BaseModel):
    it_max: int
    tab_tenure: int
    it_cons: int
    it_div: int
    fitness_score: float
    execution_time_ms: float
    convergence_iteration: int | None = None


class TuningExperimentRunCreateSchema(TuningExperimentRunBaseSchema):
    tuning_experiment_id: int | None = None