# pyright: basic
from typing import Literal

from ortools.constraint_solver import pywrapcp

from app.lib.logging.logging import get_logger
from app.models.courier import Courier
from app.models.node import Node
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.repositories.courier_repository import CourierRepository
from app.schemas.solution_schema import CreateSolution
from app.services.matrix_service import MatrixService
from app.services.solver import GreedySolver, Route, SolverProblem, TabuSearchSolver

logger = get_logger(__name__)

SolverAlgorithm = Literal["tabu_search", "greedy"]


class SolverService:
    def __init__(
        self,
        matrix_service: MatrixService,
        courier_repository: CourierRepository,
        node_repository: NodeRepository,
        solution_repository: SolutionRepository,
        simulation_repository: SimulationRepository,
    ):
        self.matrix_service = matrix_service
        self.courier_repository = courier_repository
        self.node_repository = node_repository
        self.solution_repository = solution_repository
        self.simulation_repository = simulation_repository

    async def solve(self, simulation_id: str, algorithm: SolverAlgorithm = "tabu_search"):
        time_matrix = await self.matrix_service.build_time_matrix(simulation_id)
        couriers = self.courier_repository.get_all_active_couriers_by_simulation_id(simulation_id)
        all_nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        nodes_by_index = {node.matrix_index: node for node in all_nodes}
        solutions: list[CreateSolution] = []

        for courier in couriers:
            courier_nodes = self.node_repository.get_nodes_by_simulation_id_and_courier_id(simulation_id, courier.id)

            if not courier_nodes:
                logger.info(f"Courier {courier.id} - {courier.name} has no assigned nodes, skipping")
                continue

            selected_node_indices = self._build_courier_node_indices(simulation_id, courier_nodes, nodes_by_index)
            submatrix = self._build_submatrix(time_matrix, selected_node_indices)
            demands = [self._conversion_demand_to_grams(nodes_by_index[node_index].demand) for node_index in selected_node_indices]
            route_capacity = sum(demands)

            logger.info(
                f"Courier {courier.id} - {courier.name} has {len(selected_node_indices) - 1} assigned nodes and "
                f"route demand of {route_capacity / 1000:.3f} kg"
            )

            problem = SolverProblem(
                time_matrix=submatrix,
                demands=demands,
                courier=courier,
            )

            manager, routing, solution = self._get_solver(algorithm).solve(problem)

            if not solution:
                raise Exception(f"No solution found for courier {courier.id} in simulation {simulation_id}.")

            route = self._parse_solution(manager, routing, solution, demands, selected_node_indices, courier)
            solutions.append(
                CreateSolution(
                    routes=route.route,
                    demand_in_kilograms=route.load / 1000,
                    time_in_seconds=route.time,
                    courier_id=route.courier_id,
                    simulation_id=simulation_id,
                )
            )

        await self.solution_repository.bulk_insert_solutions(solutions)
        await self.simulation_repository.update_simulation_fields(
            simulation_id,
            {
                "total_demand_in_kilograms": sum(solution.demand_in_kilograms for solution in solutions),
                "total_couriers": len(solutions),
                "total_active_couriers": len(solutions),
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
        selected_node_indices: list[int],
        courier: Courier,
    ) -> Route:
        index = routing.Start(0)
        route_load = 0
        route_time = 0
        route_nodes: list[int] = []

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += demands[node_index]
            route_nodes.append(selected_node_indices[node_index])

            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_time += routing.GetArcCostForVehicle(previous_index, index, 0)

        route_nodes.append(selected_node_indices[manager.IndexToNode(index)])

        return Route(
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
