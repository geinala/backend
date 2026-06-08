
from datetime import datetime

from pydantic import BaseModel


class TuningExperimentBaseSchema(BaseModel):
    dataset_id: str

    base_n_c: int
    it_max: int
    tab_tenure: int
    it_cons: int
    it_div: int

    random_seed: int = 42
    early_stop_no_improvement_iterations: int | None = None


class TuningExperimentCreateSchema(TuningExperimentBaseSchema):
    initial_fitness_score: float | None = None
    best_fitness_score: float | None = None
    execution_time_ms: float | None = None
    convergence_iteration: int | None = None
    improvement_percentage: float | None = None
    best_route_payload: str | None = None
    completed_at: datetime | None = None

class TuningExperimentUpdateSchema(BaseModel):
    initial_fitness_score: float | None = None
    best_fitness_score: float | None = None
    execution_time_ms: float | None = None
    convergence_iteration: int | None = None
    improvement_percentage: float | None = None