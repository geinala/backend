import asyncio
import time
from datetime import datetime
from typing import Any, TypedDict

from app.models.courier import Courier
from app.models.node import Node
from app.models.simulation import SimulationStatusEnum
from app.models.solution import Solution
from app.models.route import CreateRouteLeg, RouteStatusEnum
from app.repositories.courier_route_repository import CourierRouteRepository
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.schemas.courier_route_schema import CreateCourierRoute
from app.schemas.optimization_run_schema import CreateOptimizationRun
from app.repositories.route_repository import RouteRepository
from app.repositories.courier_repository import CourierRepository
from app.services.tomtom_service import TomTomRouteResultResponse, TomTomService
from app.repositories.solution_repository import SolutionRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.services.realtime_event_service import CourierArrivalSchedule
from app.services.matrix_service import MatrixService
from app.services.solver import GreedySolver, SolverProblem, TabuSearchSolver
from app.services.solver.types import Route as SolverRoute


class RouteSummary(TypedDict):
    lengthInMeters: int
    travelTimeInSeconds: int


class RouteBuild(TypedDict):
    solution: Solution
    courier: Courier
    tabu_route: SolverRoute
    greedy_summary: RouteSummary
    tabu_summary: RouteSummary
    greedy_computation_time_in_ms: float
    tabu_computation_time_in_ms: float

class RouteService:
    ROUTE_GENERATION_SUBMISSION_DELAY_IN_SECONDS = 2
    
    def __init__(self, 
                 tomtom_service: TomTomService, 
                 matrix_service: MatrixService,
                 solution_repository: SolutionRepository,
                 node_repository: NodeRepository,
                 courier_repository: CourierRepository,
                 route_repository: RouteRepository,
                 simulation_repository: SimulationRepository,
                 courier_route_repository: CourierRouteRepository,
                 optimization_run_repository: OptimizationRunRepository,
                 ):
        self.tomtom_service = tomtom_service
        self.matrix_service = matrix_service
        self.solution_repository = solution_repository
        self.node_repository = node_repository
        self.courier_repository = courier_repository
        self.route_repository = route_repository
        self.simulation_repository = simulation_repository
        self.courier_route_repository = courier_route_repository
        self.optimization_run_repository = optimization_run_repository

    async def generate_routes(self, simulation_id: str, depart_at: str | None = None) -> list[CourierArrivalSchedule]:
        solutions = await self.solution_repository.get_solutions_by_simulation_id(simulation_id)

        if not solutions:
            return []

        time_matrix = await self.matrix_service.build_time_matrix(simulation_id)
        nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)

        node_map = {
            node.matrix_index: node
            for node in nodes
        }

        tomtom_responses: list[TomTomRouteResultResponse] = []
        courier_routes: list[CreateCourierRoute] = []
        route_builds: list[RouteBuild] = []

        for index, solution in enumerate(solutions):
            courier = solution.courier

            if courier is None:
                raise Exception(f"Courier {solution.courier_id} could not be loaded for simulation {simulation_id}.")

            courier_nodes = self.node_repository.get_nodes_by_simulation_id_and_courier_id(simulation_id, courier.id)

            if not courier_nodes:
                continue

            selected_node_indices = self._build_courier_node_indices(simulation_id, courier_nodes, node_map)
            submatrix = self._build_submatrix(time_matrix, selected_node_indices)
            demands = [self._conversion_demand_to_grams(node_map[node_index].demand) for node_index in selected_node_indices]

            problem = SolverProblem(
                time_matrix=submatrix,
                demands=demands,
                courier=courier,
            )

            greedy_route, greedy_computation_time_in_ms = self._solve_problem(
                GreedySolver(),
                problem,
                demands,
                selected_node_indices,
                courier,
            )
            tabu_route, tabu_computation_time_in_ms = self._solve_problem(
                TabuSearchSolver(),
                problem,
                demands,
                selected_node_indices,
                courier,
            )

            greedy_routes_plan = ":".join(self._build_route_points(greedy_route.route, node_map))
            tabu_routes_plan = ":".join(self._build_route_points(tabu_route.route, node_map))

            greedy_routes = self.tomtom_service.generate_routes(greedy_routes_plan, depart_at)
            routes = self.tomtom_service.generate_routes(tabu_routes_plan, depart_at)

            tomtom_responses.append(routes)

            greedy_summary = greedy_routes["routes"][0]["summary"]
            tabu_summary = routes["routes"][0]["summary"]

            courier_routes.append(
                CreateCourierRoute(
                    solution_id=solution.id,
                    courier_id=courier.id,
                    route_version=1,
                    is_active=True,
                    total_distance_in_meters=tabu_summary["lengthInMeters"],
                    total_time_in_seconds=tabu_summary["travelTimeInSeconds"]
                )
            )

            route_builds.append(
                {
                    "solution": solution,
                    "courier": courier,
                    "tabu_route": tabu_route,
                    "greedy_summary": greedy_summary,
                    "tabu_summary": tabu_summary,
                    "greedy_computation_time_in_ms": greedy_computation_time_in_ms,
                    "tabu_computation_time_in_ms": tabu_computation_time_in_ms,
                }
            )
            
            if index < len(solutions) - 1:
                await asyncio.sleep(self.ROUTE_GENERATION_SUBMISSION_DELAY_IN_SECONDS)

        courier_route_objects = self.courier_route_repository.bulk_insert_courier_routes(courier_routes)

        optimization_runs: list[CreateOptimizationRun] = []

        for route_build, courier_route in zip(route_builds, courier_route_objects, strict=True):
            optimization_runs.extend(
                [
                    CreateOptimizationRun(
                        simulation_id=route_build["solution"].simulation_id,
                        courier_route_id=courier_route.id,
                        run_type="initial",
                        algorithm="greedy",
                        trigger_type="initial",
                        total_distance_in_meters=route_build["greedy_summary"]["lengthInMeters"],
                        total_travel_time_in_seconds=route_build["greedy_summary"]["travelTimeInSeconds"],
                        computation_time_in_ms=route_build["greedy_computation_time_in_ms"],
                    ),
                    CreateOptimizationRun(
                        simulation_id=route_build["solution"].simulation_id,
                        courier_route_id=courier_route.id,
                        run_type="initial",
                        algorithm="tabu_search",
                        trigger_type="initial",
                        total_distance_in_meters=route_build["tabu_summary"]["lengthInMeters"],
                        total_travel_time_in_seconds=route_build["tabu_summary"]["travelTimeInSeconds"],
                        computation_time_in_ms=route_build["tabu_computation_time_in_ms"],
                    ),
                ]
            )

        self.optimization_run_repository.bulk_insert_optimization_runs(optimization_runs)

        route_legs: list[CreateRouteLeg] = []
        arrival_schedules: list[CourierArrivalSchedule] = []

        for i, route_build in enumerate(route_builds):

            courier_route = courier_route_objects[i]
            routes = tomtom_responses[i]
            solution = route_build["solution"]
            tabu_route = route_build["tabu_route"]

            legs = routes["routes"][0]["legs"]
            cumulative_travel_time_seconds = 0

            for seq, leg in enumerate(legs):
                origin_node = node_map.get(tabu_route.route[seq])
                destination_node = node_map.get(tabu_route.route[seq + 1])

                if origin_node is None or destination_node is None:
                    continue

                summary = leg["summary"]
                cumulative_travel_time_seconds += int(summary["travelTimeInSeconds"])

                route_legs.append(
                    CreateRouteLeg(
                        courier_route_id=courier_route.id,
                        origin_latitude=origin_node.latitude,
                        origin_longitude=origin_node.longitude,
                        destination_latitude=destination_node.latitude,
                        destination_longitude=destination_node.longitude,
                        sequence=seq,
                        encoded_polyline=leg["encodedPolyline"],
                        encoded_polyline_precision=leg["encodedPolylinePrecision"],
                        distance_in_meters=summary["lengthInMeters"],
                        travel_time_in_seconds=summary["travelTimeInSeconds"],
                        traffic_delay_in_seconds=summary["trafficDelayInSeconds"],
                        traffic_distance_in_meters=summary["trafficLengthInMeters"],
                        departure_time=datetime.fromisoformat(summary["departureTime"].replace("Z", "+00:00")),
                        arrival_time=datetime.fromisoformat(summary["arrivalTime"].replace("Z", "+00:00")),
                        no_traffic_travel_time_in_seconds=summary["noTrafficTravelTimeInSeconds"],
                        historic_traffic_travel_time_in_seconds=summary["historicTrafficTravelTimeInSeconds"],
                        live_traffic_incidents_travel_time_in_seconds=summary["liveTrafficIncidentsTravelTimeInSeconds"],
                        route_status=(
                            RouteStatusEnum.running
                            if seq == 0
                            else RouteStatusEnum.planned
                        )
                    )
                )

                arrival_schedules.append(
                    {
                        "simulation_id": simulation_id,
                        "courier_route_id": int(courier_route.id),
                        "courier_id": int(route_build["courier"].id),
                        "node_id": int(destination_node.id),
                        "eta_seconds": cumulative_travel_time_seconds,
                    }
                )

        self.route_repository.bulk_insert_route_legs(route_legs)

        await self.simulation_repository.update_simulation_fields(
            simulation_id,
            {
                "total_distance_in_meters": sum(route.total_distance_in_meters for route in courier_routes),
                "total_duration_in_seconds": sum(route.total_time_in_seconds for route in courier_routes),
                "total_couriers": len(courier_routes),
                "total_active_couriers": sum(1 for route in courier_routes if route.is_active),
            },
        )
        
        await self.simulation_repository.update_simulation_status(simulation_id, SimulationStatusEnum.running)

        self.courier_repository.db.commit()

        return arrival_schedules

    def _solve_problem(
        self,
        solver: GreedySolver | TabuSearchSolver,
        problem: SolverProblem,
        demands: list[int],
        selected_node_indices: list[int],
        courier: Courier,
    ) -> tuple[SolverRoute, float]:
        start_time = time.time()
        manager, routing, solution = solver.solve(problem)

        if not solution:
            raise Exception(f"No solution found for courier {courier.id}.")

        route = self._parse_solution(manager, routing, solution, demands, selected_node_indices, courier)
        computation_time_in_ms = (time.time() - start_time) * 1000

        return route, computation_time_in_ms

    def _build_route_points(self, route_nodes: list[int], node_map: dict[int, Node]) -> list[str]:
        route_points: list[str] = []

        for node_index in route_nodes:
            node = node_map.get(node_index)

            if node:
                route_points.append(f"{node.latitude},{node.longitude}")

        return route_points

    def _parse_solution(
        self,
        manager: Any,
        routing: Any,
        solution: Any,
        demands: list[int],
        selected_node_indices: list[int],
        courier: Courier,
    ) -> SolverRoute:
        index: int = routing.Start(0)
        route_load: int = 0
        route_time: int = 0
        route_nodes: list[int] = []

        while not routing.IsEnd(index):
            node_index: int = manager.IndexToNode(index)
            route_load += demands[node_index]
            route_nodes.append(selected_node_indices[node_index])

            previous_index: int = index
            index = solution.Value(routing.NextVar(index))
            route_time += routing.GetArcCostForVehicle(previous_index, index, 0)

        node_index: int = int(manager.IndexToNode(index))
        route_nodes.append(selected_node_indices[node_index])

        return SolverRoute(
            courier_id=courier.id,
            route=route_nodes,
            load=route_load,
            time=route_time,
        )

    def _build_courier_node_indices(
        self,
        simulation_id: str,
        courier_nodes: list[Node],
        nodes_by_index: dict[int, Node],
    ) -> list[int]:
        if 0 not in nodes_by_index:
            raise Exception(f"Depot node is missing for simulation {simulation_id}.")

        node_indices = [0]
        node_indices.extend(sorted(node.matrix_index for node in courier_nodes))
        return node_indices

    def _build_submatrix(self, time_matrix: list[list[int]], node_indices: list[int]) -> list[list[int]]:
        return [
            [time_matrix[origin_index][destination_index] for destination_index in node_indices]
            for origin_index in node_indices
        ]

    def _conversion_demand_to_grams(self, demand: float) -> int:
        return round(demand * 1000)