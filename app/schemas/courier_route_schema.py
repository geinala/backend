
from pydantic import BaseModel

class CreateCourierRoute(BaseModel):
    solution_id: int
    courier_id: int
    route_version: int
    is_active: bool
    total_distance_in_meters: int
    total_time_in_seconds: int
    reoptimized_from_route_id: int | None = None
    trigger_node_id: int | None = None
    triggered_by_traffic: bool = False
    is_initial_route: bool