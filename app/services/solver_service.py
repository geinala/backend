# pyright: basic
from typing import Literal

from ortools.constraint_solver import pywrapcp

from app.lib.logging.logging import get_logger
from app.models.solution import CreateSolution
from app.models.vehicle import Vehicle
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.services.matrix_service import MatrixService
from app.services.solver import GreedySolver, Route, SolverProblem, TabuSearchSolver

logger = get_logger(__name__)

SolverAlgorithm = Literal["tabu_search", "greedy"]


class SolverService:
    def __init__(
        self,
        matrix_service: MatrixService,
        vehicle_repository: VehicleRepository,
        node_repository: NodeRepository,
        solution_repository: SolutionRepository,
        simulation_repository: SimulationRepository,
    ):
        self.matrix_service = matrix_service
        self.vehicle_repository = vehicle_repository
        self.node_repository = node_repository
        self.solution_repository = solution_repository
        self.simulation_repository = simulation_repository

    async def solve(self, simulation_id: str, algorithm: SolverAlgorithm = "tabu_search"):
        time_matrix = await self.matrix_service.build_time_matrix(simulation_id)
        vehicles = self.vehicle_repository.get_all_active_vehicles_by_simulation_id(simulation_id)
        vehicle_capacities = self._mapped_vehicle_constraints(vehicles, simulation_id)
        demands = self._get_demands(simulation_id)

        problem = SolverProblem(
            time_matrix=time_matrix,
            demands=demands,
            vehicle_capacities=vehicle_capacities,
            vehicles=vehicles,
        )

        manager, routing, solution = self._get_solver(algorithm).solve(problem)

        if not solution:
            raise Exception("No solution found for the given optimization problem.")

        routes = self._parse_solution(manager, routing, solution, demands, vehicles)
        solutions = [
            CreateSolution(
                routes=route.route,
                demand_in_kilograms=route.load / 1000,
                time_in_seconds=route.time,
                vehicle_id=route.vehicle_id,
                simulation_id=simulation_id,
            )
            for route in routes
        ]

        await self.solution_repository.bulk_insert_solutions(solutions)
        await self.simulation_repository.update_simulation_fields(
            simulation_id,
            {
                "total_demand_in_kilograms": sum(solution.demand_in_kilograms for solution in solutions),
                "total_vehicles": len(solutions),
                "total_active_vehicles": len(solutions),
            },
        )

    async def solve_with_tabu_search(self, simulation_id: str):
        await self.solve(simulation_id, algorithm="tabu_search")

    async def solve_with_greedy(self, simulation_id: str):
        await self.solve(simulation_id, algorithm="greedy")

    def _get_solver(self, algorithm: SolverAlgorithm) -> TabuSearchSolver | GreedySolver:
        if algorithm == "greedy":
            return GreedySolver()

        if algorithm == "tabu_search":
            return TabuSearchSolver()

        raise ValueError(f"Unsupported solver algorithm: {algorithm}")

    def _parse_solution(
        self,
        manager: pywrapcp.RoutingIndexManager,
        routing: pywrapcp.RoutingModel,
        solution: pywrapcp.Assignment,
        demands: list[int],
        vehicles: list[Vehicle],
    ) -> list[Route]:
        routes: list[Route] = []

        for vehicle_index, vehicle in enumerate(vehicles):
            index = routing.Start(vehicle_index)
            route_load = 0
            route_time = 0
            route_nodes: list[int] = []

            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_load += demands[node_index]
                route_nodes.append(node_index)

                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_time += routing.GetArcCostForVehicle(previous_index, index, vehicle_index)

            route_nodes.append(manager.IndexToNode(index))

            routes.append(
                Route(
                    vehicle_id=vehicle.id,
                    route=route_nodes,
                    load=route_load,
                    time=route_time,
                )
            )

        return routes

    def _mapped_vehicle_constraints(self, active_vehicles: list[Vehicle], simulation_id: str) -> list[int]:
        logger.info(f"Active vehicles for simulation {simulation_id}: {[vehicle.id for vehicle in active_vehicles]}")
        return [self._conversion_vehicle_capacity_to_grams(vehicle.max_capacity) for vehicle in active_vehicles]

    def _get_demands(self, simulation_id: str) -> list[int]:
        nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        nodes_sorted = sorted(nodes, key=lambda n: n.matrix_index)
        return [self._conversion_demand_to_grams(node.demand) for node in nodes_sorted]

    def _conversion_vehicle_capacity_to_grams(self, vehicle_capacity: float) -> int:
        return round(vehicle_capacity * 1000)

    def _conversion_demand_to_grams(self, demand: float) -> int:
        return round(demand * 1000)
