from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle, CreateVehicleRoute, VehicleRoute

class VehicleRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def get_all_active_vehicles_by_simulation_id(self, simulation_id: str):
        return self.db.query(Vehicle).filter_by(simulation_id=simulation_id, is_active=True).all()
    
    def bulk_insert_vehicle_routes(self, vehicle_routes: list[CreateVehicleRoute]):
        vehicle_route_objects = [
            VehicleRoute(
                solution_id=route.solution_id,
                vehicle_id=route.vehicle_id,
                route_version=route.route_version,
                is_active=route.is_active,
                total_distance_in_meters=route.total_distance_in_meters,
                total_time_in_seconds=route.total_time_in_seconds,
                reoptimized_from_route_id=route.reoptimized_from_route_id,
                trigger_node_id=route.trigger_node_id,
                triggered_by_traffic=route.triggered_by_traffic,
            )
            for route in vehicle_routes
        ]
        
        self.db.add_all(vehicle_route_objects)
        self.db.flush()  # To get the generated IDs for the inserted vehicle routes
        
        return vehicle_route_objects