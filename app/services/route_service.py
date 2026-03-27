from datetime import datetime
import asyncio

from app.models.route import CreateRouteLeg
from app.models.vehicle import CreateVehicleRoute
from app.repositories.route_repository import RouteRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.services.tomtom_service import TomTomRouteResultResponse, TomTomService
from app.repositories.solution_repository import SolutionRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.models.simulation import SimulationStatusEnum

class RouteService:
    ROUTE_GENERATION_SUBMISSION_DELAY_IN_SECONDS = 2
    
    def __init__(self, 
                 tomtom_service: TomTomService, 
                 solution_repository: SolutionRepository,
                 node_repository: NodeRepository,
                 vehicle_repository: VehicleRepository,
                 route_repository: RouteRepository,
                 simulation_repository: SimulationRepository
                 ):
        self.tomtom_service = tomtom_service
        self.solution_repository = solution_repository
        self.node_repository = node_repository
        self.vehicle_repository = vehicle_repository
        self.route_repository = route_repository
        self.simulation_repository = simulation_repository

    async def generate_routes(self, simulation_id: str, depart_at: str | None = None) -> None:
        solutions = await self.solution_repository.get_solutions_by_simulation_id(simulation_id)

        if not solutions:
            return

        nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)

        node_map = {
            node.matrix_index: node
            for node in nodes
        }

        tomtom_responses: list[TomTomRouteResultResponse] = []
        vehicle_routes: list[CreateVehicleRoute] = []

        for index, solution in enumerate(solutions):

            route_points: list[str] = []

            for idx in solution.routes:
                node = node_map.get(idx)
                if node:
                    route_points.append(f"{node.latitude},{node.longitude}")

            routes_plan = ":".join(route_points)

            routes = self.tomtom_service.generate_routes(routes_plan, depart_at)

            tomtom_responses.append(routes)

            summary = routes["routes"][0]["summary"]

            vehicle_routes.append(
                CreateVehicleRoute(
                    solution_id=solution.id,
                    vehicle_id=solution.vehicle_id,
                    route_version=1,
                    is_active=True,
                    total_distance_in_meters=summary["lengthInMeters"],
                    total_time_in_seconds=summary["travelTimeInSeconds"]
                )
            )
            
            if index < len(solutions) - 1:
                await asyncio.sleep(self.ROUTE_GENERATION_SUBMISSION_DELAY_IN_SECONDS)

        vehicle_route_objects = self.vehicle_repository.bulk_insert_vehicle_routes(vehicle_routes)

        route_legs: list[CreateRouteLeg] = []

        for i, solution in enumerate(solutions):

            vehicle_route = vehicle_route_objects[i]
            routes = tomtom_responses[i]

            legs = routes["routes"][0]["legs"]

            for seq, leg in enumerate(legs):
                origin_node = node_map.get(solution.routes[seq])
                destination_node = node_map.get(solution.routes[seq + 1])

                if origin_node is None or destination_node is None:
                    continue

                summary = leg["summary"]

                route_legs.append(
                    CreateRouteLeg(
                        vehicle_route_id=vehicle_route.id,
                        origin_node_id=origin_node.id,
                        destination_node_id=destination_node.id,
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
                        live_traffic_incidents_travel_time_in_seconds=summary["liveTrafficIncidentsTravelTimeInSeconds"]
                    )
                )

        self.route_repository.bulk_insert_route_legs(route_legs)
        
        await self.simulation_repository.update_simulation_status(simulation_id, SimulationStatusEnum.running)

        self.vehicle_repository.db.commit()