# pyright: basic

import asyncio
import time
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from ortools.constraint_solver import pywrapcp

from app.lib.logging.logging import get_logger
from app.models.courier import Courier
from app.models.node import Node
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.repositories.courier_repository import CourierRepository
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.schemas.simulation_schema import UpdateSimulationSchema
from app.schemas.solution_schema import CreateSolution
from app.schemas.optimization_run_schema import CreateOptimizationRun
from app.services.matrix_service import MatrixService
from app.services.or_tools_solver import GreedySolver, Route, SolverProblem, TabuSearchSolver

logger = get_logger(__name__)

SolverAlgorithm = Literal["tabu_search", "greedy"]

class OrToolsSolverService:
    def __init__(
        self,
        matrix_service: MatrixService,
        courier_repository: CourierRepository,
        node_repository: NodeRepository,
        solution_repository: SolutionRepository,
        simulation_repository: SimulationRepository,
        optimization_run_repository: OptimizationRunRepository,
    ):
        self.matrix_service = matrix_service
        self.courier_repository = courier_repository
        self.node_repository = node_repository
        self.solution_repository = solution_repository
        self.simulation_repository = simulation_repository
        self.optimization_run_repository = optimization_run_repository

    def _run_solver(self, solver: TabuSearchSolver | GreedySolver, problem: SolverProblem, demands: list[int], selected_node_indices: list[int], courier: Courier) -> tuple[Route, float]:
        start_time = time.time()
        manager, routing, solution = solver.solve(problem)

        if not solution:
            raise Exception(f"No solution found for courier {courier.id}.")

        route = self._parse_solution(manager, routing, solution, demands, selected_node_indices, courier)
        computation_time_in_ms = (time.time() - start_time) * 1000

        return route, computation_time_in_ms

    async def solve(self, simulation_id: str):
        time_matrix = await self.matrix_service.build_time_matrix(simulation_id)
        distance_matrix = await self.matrix_service.build_distance_matrix(simulation_id)
        
        couriers = self.courier_repository.get_all_active_couriers_by_simulation_id(simulation_id)
        all_nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        nodes_by_index = {node.matrix_index: node for node in all_nodes}
        
        solutions: list[CreateSolution] = []
        optimization_runs: list[CreateOptimizationRun] = []

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

            greedy_task = asyncio.to_thread(self._run_solver, GreedySolver(), problem, demands, selected_node_indices, courier)
            tabu_task = asyncio.to_thread(self._run_solver, TabuSearchSolver(), problem, demands, selected_node_indices, courier)
            
            (greedy_route, greedy_time_ms), (tabu_route, tabu_time_ms) = await asyncio.gather(greedy_task, tabu_task)
            
            greedy_distance = self._calculate_route_distance(greedy_route.route, distance_matrix)
            tabu_distance = self._calculate_route_distance(tabu_route.route, distance_matrix)

            nodes_explored = len(tabu_route.route)
            triggered_at = datetime.now(timezone.utc)

            optimization_runs.extend([
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="initial",
                    algorithm="greedy",
                    trigger_type="initial",
                    total_distance_in_meters=greedy_distance,
                    total_travel_time_in_seconds=greedy_route.time, 
                    computation_time_in_ms=greedy_time_ms,
                    total_nodes_explored=nodes_explored,
                    congestion_check_id=None,
                    triggered_at=triggered_at,
                    courier_id=courier.id,
                ),
                CreateOptimizationRun(
                    simulation_id=UUID(simulation_id),
                    run_type="initial",
                    algorithm="tabu_search",
                    trigger_type="initial",
                    total_distance_in_meters=tabu_distance,
                    total_travel_time_in_seconds=tabu_route.time,
                    computation_time_in_ms=tabu_time_ms,
                    total_nodes_explored=nodes_explored,
                    congestion_check_id=None,
                    before_total_distance_in_meters=greedy_distance,
                    before_total_travel_time_in_seconds=greedy_route.time,
                    triggered_at=triggered_at,
                    courier_id=courier.id,
                ),
            ])

            solutions.append(
                CreateSolution(
                    routes=tabu_route.route,
                    demand_in_kilograms=tabu_route.load / 1000,
                    time_in_seconds=tabu_route.time,
                    courier_id=tabu_route.courier_id,
                    simulation_id=simulation_id,
                    distance_in_meters=tabu_distance,
                )
            )

        self.optimization_run_repository.bulk_insert_optimization_runs(optimization_runs)
        await self.solution_repository.bulk_insert_solutions(solutions)
        
        await self.simulation_repository.update_simulation(
            simulation_id,
            UpdateSimulationSchema(
                total_demand_in_kilograms=sum(solution.demand_in_kilograms for solution in solutions),
                total_couriers=len(solutions),
                total_active_couriers=len(solutions),
            )
        )

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

    def _calculate_route_distance(self, route_nodes: list[int], distance_matrix: list[list[int]]) -> int:
        """Kalkulasi total jarak berdasarkan global index node pada distance matrix"""
        total_distance = 0
        for i in range(len(route_nodes) - 1):
            origin_index = route_nodes[i]
            destination_index = route_nodes[i + 1]
            total_distance += distance_matrix[origin_index][destination_index]
        return total_distance

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