from sqlalchemy.orm import Session

from app.models.courier_route import CourierRoute
from app.schemas.courier_route_schema import CreateCourierRoute

from app.schemas.courier_route_schema import CreateCourierRoute

class CourierRouteRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def bulk_insert_courier_routes(self, courier_routes: list[CreateCourierRoute]):
        courier_route_objects = [
            CourierRoute(
                solution_id=route.solution_id,
                courier_id=route.courier_id,
                route_version=route.route_version,
                is_active=route.is_active,
                total_distance_in_meters=route.total_distance_in_meters,
                total_time_in_seconds=route.total_time_in_seconds,
                reoptimized_from_route_id=route.reoptimized_from_route_id,
                trigger_node_id=route.trigger_node_id,
                triggered_by_traffic=route.triggered_by_traffic,
                is_initial_route=route.is_initial_route,
            )
            for route in courier_routes
        ]
        
        self.db.add_all(courier_route_objects)
        self.db.flush()  # To get the generated IDs for the inserted courier routes
        
        return courier_route_objects

    async def insert_courier_route(self, courier_route: CreateCourierRoute) -> CourierRoute:
        courier_route_object = CourierRoute(
            solution_id=courier_route.solution_id,
            courier_id=courier_route.courier_id,
            route_version=courier_route.route_version,
            is_active=courier_route.is_active,
            total_distance_in_meters=courier_route.total_distance_in_meters,
            total_time_in_seconds=courier_route.total_time_in_seconds,
            reoptimized_from_route_id=courier_route.reoptimized_from_route_id,
            trigger_node_id=courier_route.trigger_node_id,
            triggered_by_traffic=courier_route.triggered_by_traffic,
            is_initial_route=courier_route.is_initial_route,
        )
        
        self.db.add(courier_route_object)
        self.db.flush()  # To get the generated ID for the inserted courier route
        
        return courier_route_object
    
    async def deactivate_courier_route(self, courier_route_id: int):
        courier_route = self.db.query(CourierRoute).filter(CourierRoute.id == courier_route_id).first()
        if courier_route:
            courier_route.is_active = False
            self.db.add(courier_route)
            self.db.flush()