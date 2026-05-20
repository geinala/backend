from enum import Enum

class SolverAlgorithm(str, Enum):
    TABU_SEARCH = "tabu_search"
    GREEDY = "greedy"