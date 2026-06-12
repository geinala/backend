from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, TypedDict

OptimizationTarget = Literal["time", "distance"]

class OptimizationEvent(TypedDict, total=False):
    event_type: str
    iteration: int
    elapsed_ms: float
    timestamp: datetime
    current_distance_in_meters: float
    current_duration_in_seconds: float
    best_distance_in_meters: float
    best_duration_in_seconds: float
    distance_improvement_in_meters: float
    duration_improvement_in_seconds: float
    improvement_percent: float
    iterations_without_improvement: int
    objective_value: float
    operator_used: Optional[str]
    is_new_best: bool
    triggered_diversification: bool
    used_aspiration_criteria: bool
    active_routes_count: Optional[int]
    unassigned_nodes_count: Optional[int]
    message: str
    intermediate_tour: Optional[List[int]]


@dataclass
class Assignment:
    tour: List[int]
    total_distance_in_meters: float
    total_duration_in_seconds: float
    algorithm_used: str
    elapsed_ms: float
    iterations: int = 0
    history: List[float] = field(default_factory=list[float])
    logs: List[OptimizationEvent] = field(default_factory=list[OptimizationEvent])


class FirstSolutionStrategy(Enum):
    NEAREST_NEIGHBOR = 1


class LocalSearchMetaheuristic(Enum):
    NONE = 0
    TABU_SEARCH = 2


class LocalImprovementStrategy(Enum):
    NONE = 0
    TWO_OPT = 1


@dataclass
class RoutingSearchParameters:
    first_solution_strategy: FirstSolutionStrategy = FirstSolutionStrategy.NEAREST_NEIGHBOR
    local_search_metaheuristic: LocalSearchMetaheuristic = LocalSearchMetaheuristic.TABU_SEARCH
    local_improvement_strategy: LocalImprovementStrategy = LocalImprovementStrategy.NONE
    optimization_target: OptimizationTarget = "time"  # "time" atau "distance"
    max_local_search_iterations: int = 500
    max_improvement_iterations: int = 1000
    max_execution_time_seconds: float = 60.0
    early_stop_no_improvement_iterations: int = 150
    min_improvement_percent: float = 0.0001
    tabu_tenure: Optional[int] = None
    enable_aspiration: bool = True
    use_oropt_neighborhood: bool = True
    max_neighbors_2opt: int = 30
    max_neighbors_oropt: int = 20
    diversify_after_iterations: int = 50
    diversification_strength: int = 1
    verbose: bool = False
    random_seed: int = 42
    track_iteration_history: bool = True
    save_intermediate_solutions: bool = False


@dataclass
class ManualSolverProblem:
    distance_matrix: List[List[float]]
    time_matrix: List[List[float]]
    start_index: Optional[int] = 0
    end_index: Optional[int] = 0
    