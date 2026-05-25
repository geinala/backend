# pyright: basic
from typing import Any

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.services.solver.base import BaseSolverStrategy
from app.services.solver.types import SolverProblem


class OrToolsSolverStrategy(BaseSolverStrategy):
    def __init__(
        self,
        *,
        first_solution_strategy: int,
        local_search_metaheuristic: int | None = None,
    ):
        self.first_solution_strategy = first_solution_strategy
        self.local_search_metaheuristic = local_search_metaheuristic

    def solve(
        self,
        problem: SolverProblem,
    ) -> tuple[pywrapcp.RoutingIndexManager, pywrapcp.RoutingModel, pywrapcp.Assignment | None]:
        start_index = problem.start_index
        end_index = problem.end_index if problem.end_index is not None else problem.depot_index

        if start_index == end_index:
            manager = pywrapcp.RoutingIndexManager(
                len(problem.time_matrix),
                1,
                start_index,
            )
        else:
            manager = pywrapcp.RoutingIndexManager(
                len(problem.time_matrix),
                1,
                [start_index],
                [end_index],
            )
        routing = pywrapcp.RoutingModel(manager)

        self._register_callbacks(
            manager=manager,
            routing=routing,
            problem=problem,
        )

        search_parameters = self._build_search_parameters(problem.time_limit_seconds)
        solution = routing.SolveWithParameters(search_parameters)

        return manager, routing, solution

    def _build_search_parameters(self, time_limit_seconds: int) -> Any:
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = self.first_solution_strategy

        if self.local_search_metaheuristic is not None:
            search_parameters.local_search_metaheuristic = self.local_search_metaheuristic

        search_parameters.time_limit.FromSeconds(time_limit_seconds)
        return search_parameters

    def _register_callbacks(
        self,
        *,
        manager: pywrapcp.RoutingIndexManager,
        routing: pywrapcp.RoutingModel,
        problem: SolverProblem,
    ) -> None:
        def demand_callback(from_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            return problem.demands[from_node]

        def time_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)

            time_travel = problem.time_matrix[from_node][to_node]
            service_time = 300

            return time_travel + service_time

        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        routing.AddDimension(
            transit_callback_index,
            0,
            28800,
            True,
            "Time",
        )

        time_dimension = routing.GetDimensionOrDie("Time")

        for vehicle_id in range(routing.vehicles()):
            start_index = routing.Start(vehicle_id)
            end_index = routing.End(vehicle_id)

            time_dimension.CumulVar(start_index).SetRange(0, 0)
            time_dimension.CumulVar(end_index).SetRange(0, 28800)

        time_dimension.SetGlobalSpanCostCoefficient(10)

        for vehicle_id in range(routing.vehicles()):
            end_index = routing.End(vehicle_id)
            time_dimension.SetCumulVarSoftUpperBound(
                end_index,
                25200,
                1000,
            )

def build_greedy_solver() -> OrToolsSolverStrategy:
    return OrToolsSolverStrategy(
        first_solution_strategy=routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC,
    )


def build_tabu_search_solver() -> OrToolsSolverStrategy:
    return OrToolsSolverStrategy(
        first_solution_strategy=routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC,
        local_search_metaheuristic=routing_enums_pb2.LocalSearchMetaheuristic.TABU_SEARCH,
    )
