from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, TypedDict


class OptimizationEvent(TypedDict, total=False):
    event_type: str
    iteration: int
    elapsed_ms: float
    timestamp: datetime
    current_distance_in_meters: int
    current_duration_in_seconds: int
    best_distance_in_meters: int
    best_duration_in_seconds: int
    distance_improvement_in_meters: int
    duration_improvement_in_seconds: int
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
    total_distance_in_meters: int
    total_duration_in_seconds: int
    algorithm_used: str
    elapsed_ms: float
    iterations: int = 0
    history: List[int] = field(default_factory=list[int])
    logs: List[OptimizationEvent] = field(default_factory=list[OptimizationEvent])


class FirstSolutionStrategy(Enum):
    NEAREST_NEIGHBOR = 1
    GREEDY_EDGE_INSERTION = 2
    AUTOMATIC = 3


class LocalSearchMetaheuristic(Enum):
    NONE = 0
    TABU_SEARCH = 2


class LocalImprovementStrategy(Enum):
    NONE = 0
    TWO_OPT = 1


@dataclass
class RoutingSearchParameters:
    first_solution_strategy: FirstSolutionStrategy = FirstSolutionStrategy.AUTOMATIC
    local_search_metaheuristic: LocalSearchMetaheuristic = LocalSearchMetaheuristic.TABU_SEARCH
    local_improvement_strategy: LocalImprovementStrategy = LocalImprovementStrategy.NONE
    optimization_target: str = "time"  # "time" atau "distance"
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
    distance_matrix: List[List[int]]
    time_matrix: List[List[int]]
    depot: int = 0
    
ComparisonScenario = Literal["no_improvement", "with_improvement"]