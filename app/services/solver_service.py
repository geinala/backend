

# pyright: basic
from app.models.solution import CreateSolution
from app.models.vehicle import Vehicle
from app.repositories.node_repository import NodeRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.repositories.solution_repository import SolutionRepository
from app.repositories.simulation_repository import SimulationRepository
from app.services.matrix_service import MatrixService

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

class Route:
    def __init__(self, vehicle_id: int, route: list[int], load: int, time: int):
        self.vehicle_id = vehicle_id
        self.route = route
        self.load = load
        self.time = time

class SolverService:
    def __init__(self, 
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

    async def solve(self, simulation_id: str):
        time_matrix = await self.matrix_service.build_time_matrix(simulation_id)
        
        vehicle_capacities, num_vehicles = self._mapped_vehicle_constraints(simulation_id)
        demands = self._get_demands(simulation_id)
        
        manager, routing = self._create_routing_model(
            num_vehicles=num_vehicles,
            length_of_time_matrix=len(time_matrix),
            depot_index=0
        )
        
        self._callbacks_factory(
            manager=manager,
            routing=routing,
            time_matrix=time_matrix,
            demands=demands,
            vehicle_capacities=vehicle_capacities
        )
        
        search_parameters = self._search_parameters_factory(time_limit=60)
        
        solution = routing.SolveWithParameters(search_parameters)
        
        if solution:
            routes = self._parse_solution(manager, routing, solution, demands, self.vehicle_repository.get_all_active_vehicles_by_simulation_id(simulation_id))

            solutions: list[CreateSolution] = []

            for route in routes:
                solutions.append(CreateSolution(
                    routes=route.route,
                    demand_in_kilograms=route.load / 1000,
                    time_in_seconds=route.time,
                    vehicle_id=route.vehicle_id,
                    simulation_id=simulation_id
                ))
                
            await self.solution_repository.bulk_insert_solutions(solutions)

            await self.simulation_repository.update_simulation_fields(
                simulation_id,
                {
                    "total_demand_in_kilograms": sum(solution.demand_in_kilograms for solution in solutions),
                    "total_vehicles": len(solutions),
                    "total_active_vehicles": len(solutions),
                },
            )
            
        else:
            raise Exception("No solution found for the given optimization problem.")
    
    def _parse_solution(self, manager: pywrapcp.RoutingIndexManager, routing: pywrapcp.RoutingModel, solution: pywrapcp.Assignment, demands: list[int], vehicles: list[Vehicle]) -> list[Route]:
        routes: list[Route] = []
        
        for vehicle_index, vehicle in enumerate(vehicles):
            index = routing.Start(vehicle_index)
            route_load = 0
            route_dist = 0
            route_nodes = []
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_load += demands[node_index]
                route_nodes.append(node_index)
                
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_dist += routing.GetArcCostForVehicle(previous_index, index, vehicle_index)
            
            # Add return to depot
            route_nodes.append(manager.IndexToNode(index))
        
            routes.append(Route(
                vehicle_id=vehicle.id,
                route=route_nodes,
                load=route_load,
                time=route_dist
            ))
        
        return routes
    
    def _search_parameters_factory(self, time_limit: int):
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION)
        search_parameters.local_search_metaheuristic = (routing_enums_pb2.LocalSearchMetaheuristic.TABU_SEARCH)
        search_parameters.time_limit.FromSeconds(time_limit)
        
        return search_parameters
    
    def _callbacks_factory(
        self,
        manager: pywrapcp.RoutingIndexManager,
        routing: pywrapcp.RoutingModel,
        time_matrix: list[list[int]],
        demands: list[int],
        vehicle_capacities: list[int],
    ):  
        def demand_callback(from_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            return demands[from_node]
        
        def time_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            
            time_travel = time_matrix[from_node][to_node]
            service_time = 300  # 5 menit
            
            return time_travel + service_time
        
        # === COST FUNCTION ===
        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        # === CAPACITY CONSTRAINT ===
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            vehicle_capacities,
            True,
            'Capacity'
        )
        
        # === TIME DIMENSION (JAM KERJA) ===
        routing.AddDimension(
            transit_callback_index,
            0,          # no waiting slack
            28800,      # 8 jam (09:00 - 17:00)
            True,
            'Time'
        )
        
        time_dimension = routing.GetDimensionOrDie('Time')
        
        # === ⏰ JAM KERJA: 09:00 - 17:00 ===
        # 09:00 = 0 detik
        # 17:00 = 28800 detik
        for vehicle_id in range(routing.vehicles()):
            start_index = routing.Start(vehicle_id)
            end_index = routing.End(vehicle_id)
            
            # harus mulai tepat jam 09:00
            time_dimension.CumulVar(start_index).SetRange(0, 0)
            
            # harus selesai sebelum jam 17:00
            time_dimension.CumulVar(end_index).SetRange(0, 28800)
        
        # === ⚖️ BALANCING (INI KUNCI BIAR GA TIMPANG) ===
        time_dimension.SetGlobalSpanCostCoefficient(100)
        
        # === OPTIONAL: SOFT LIMIT BIAR LEBIH REALISTIS ===
        for vehicle_id in range(routing.vehicles()):
            end_index = routing.End(vehicle_id)
            
            # idealnya selesai <= 7 jam (25200 detik)
            time_dimension.SetCumulVarSoftUpperBound(
                end_index,
                25200,
                1000  # penalty
            )
    
    def _create_routing_model(self, num_vehicles: int, length_of_time_matrix: int, depot_index: int) -> tuple[pywrapcp.RoutingIndexManager, pywrapcp.RoutingModel]:
        manager = pywrapcp.RoutingIndexManager(
            length_of_time_matrix,
            num_vehicles,
            depot_index
        )
        
        routing = pywrapcp.RoutingModel(manager)
        
        return manager, routing

    def _mapped_vehicle_constraints(self, simulation_id: str) -> tuple[list[int], int]:
        active_vehicles = self.vehicle_repository.get_all_active_vehicles_by_simulation_id(simulation_id)
        
        logger.info(f"Active vehicles for simulation {simulation_id}: {[vehicle.id for vehicle in active_vehicles]}")  # Log active vehicle IDs
        
        vehicle_capacities = [self._conversion_vehicle_capacity_to_grams(vehicle.max_capacity) for vehicle in active_vehicles]
        num_vehicles = len(active_vehicles)
        
        return vehicle_capacities, num_vehicles
    
    def _get_demands(self, simulation_id: str) -> list[int]:
        nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        nodes_sorted = sorted(nodes, key=lambda n: n.matrix_index)

        demands = [self._conversion_demand_to_grams(node.demand) for node in nodes_sorted]
        
        return demands
    
    def _conversion_vehicle_capacity_to_grams(self, vehicle_capacity: float) -> int:
        return round(vehicle_capacity * 1000)
    
    def _conversion_demand_to_grams(self, demand: float) -> int:
        return round(demand * 1000)