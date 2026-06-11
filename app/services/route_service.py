import asyncio
from datetime import datetime

from app.lib.date_converter import format_departure_time
from app.models.node import Node
from app.models.simulation import SimulationStatusEnum
from app.models.route import RouteStatusEnum
from app.repositories.courier_route_repository import CourierRouteRepository
from app.schemas.courier_route_schema import CreateCourierRoute
from app.schemas.route_schema import CreateRouteLeg
from app.repositories.route_repository import RouteRepository
from app.repositories.courier_repository import CourierRepository
from app.schemas.simulation_schema import UpdateSimulationSchema
from app.services.tomtom_service import TomTomRouteResultResponse, TomTomService
from app.repositories.solution_repository import SolutionRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.services.realtime_event_service import CourierArrivalSchedule

class RouteService:
    ROUTE_GENERATION_SUBMISSION_DELAY_IN_SECONDS = 2
    
    def __init__(self, 
                 tomtom_service: TomTomService, 
                 solution_repository: SolutionRepository,
                 node_repository: NodeRepository,
                 courier_repository: CourierRepository,
                 route_repository: RouteRepository,
                 simulation_repository: SimulationRepository,
                 courier_route_repository: CourierRouteRepository,
                 ):
        self.tomtom_service = tomtom_service
        self.solution_repository = solution_repository
        self.node_repository = node_repository
        self.courier_repository = courier_repository
        self.route_repository = route_repository
        self.simulation_repository = simulation_repository
        self.courier_route_repository = courier_route_repository

    async def generate_routes(self, simulation_id: str) -> list[CourierArrivalSchedule]:
        simulation = await self.simulation_repository.get_simulation_by_id(simulation_id)
        if simulation is None:
            raise Exception(f"Simulation with id {simulation_id} not found.")

        solutions = await self.solution_repository.get_solutions_by_simulation_id(simulation_id)

        if not solutions:
            return []

        nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        node_map = {node.matrix_index: node for node in nodes}

        tomtom_responses: list[TomTomRouteResultResponse] = []
        courier_routes: list[CreateCourierRoute] = []

        for index, solution in enumerate(solutions):
            courier = solution.courier

            if courier is None:
                raise Exception(f"Courier {solution.courier_id} could not be loaded for simulation {simulation_id}.")

            routes_plan = ":".join(self._build_route_points(solution.routes, node_map))

            routes = self.tomtom_service.generate_routes(routes_plan, depart_at=format_departure_time(simulation.started_at))
            tomtom_responses.append(routes)

            summary = routes["routes"][0]["summary"]

            courier_routes.append(
                CreateCourierRoute(
                    solution_id=solution.id,
                    courier_id=courier.id,
                    route_version=1,
                    is_active=True,
                    total_distance_in_meters=summary["lengthInMeters"],
                    total_time_in_seconds=summary["travelTimeInSeconds"],
                    is_initial_route=True
                )
            )

            if index < len(solutions) - 1:
                await asyncio.sleep(self.ROUTE_GENERATION_SUBMISSION_DELAY_IN_SECONDS)

        courier_route_objects = self.courier_route_repository.bulk_insert_courier_routes(courier_routes)

        route_legs: list[CreateRouteLeg] = []
        arrival_schedules: list[CourierArrivalSchedule] = []

        for i, courier_route in enumerate(courier_route_objects):
            routes = tomtom_responses[i]
            solution = solutions[i]
            
            legs = routes["routes"][0]["legs"]
            cumulative_travel_time_seconds = 0

            for seq, leg in enumerate(legs):
                origin_node = node_map.get(solution.routes[seq])
                destination_node = node_map.get(solution.routes[seq + 1])

                if origin_node is None or destination_node is None:
                    continue

                summary = leg["summary"]
                cumulative_travel_time_seconds += int(summary["travelTimeInSeconds"])

                route_legs.append(
                    CreateRouteLeg(
                        courier_route_id=courier_route.id,
                        from_node_id=origin_node.id,
                        to_node_id=destination_node.id,
                        origin_latitude=origin_node.latitude,
                        origin_longitude=origin_node.longitude,
                        destination_latitude=destination_node.latitude,
                        destination_longitude=destination_node.longitude,
                        sequence=seq + 1, 
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
                        "courier_id": int(solution.courier_id),
                        "node_id": int(destination_node.id),
                        "eta_seconds": cumulative_travel_time_seconds,
                    }
                )

        self.route_repository.bulk_insert_route_legs(route_legs)

        await self.simulation_repository.update_simulation(
            simulation_id,
            UpdateSimulationSchema(
                initial_total_distance_in_meters=sum(route.total_distance_in_meters for route in courier_routes),
                initial_total_duration_in_seconds=sum(route.total_time_in_seconds for route in courier_routes),
                total_nodes=len(nodes),
                total_couriers=len(courier_routes),
                total_active_couriers=sum(1 for route in courier_routes if route.is_active),
            )
        )
        
        await self.simulation_repository.update_simulation_status(simulation_id, SimulationStatusEnum.running)

        self.courier_repository.db.commit()

        return arrival_schedules

    def _build_route_points(self, route_nodes: list[int], node_map: dict[int, Node]) -> list[str]:
        route_points: list[str] = []
        for node_index in route_nodes:
            node = node_map.get(node_index)
            if node:
                route_points.append(f"{node.latitude},{node.longitude}")
        return route_points