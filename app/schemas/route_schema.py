from datetime import datetime

from pydantic import BaseModel

from app.models.route import RouteStatusEnum


class CreateRouteLeg(BaseModel):
    courier_route_id: int
    from_node_id: int
    to_node_id: int
    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    sequence: int
    encoded_polyline: str
    encoded_polyline_precision: int
    distance_in_meters: int
    travel_time_in_seconds: int
    traffic_delay_in_seconds: int
    traffic_distance_in_meters: int
    departure_time: datetime
    arrival_time: datetime
    no_traffic_travel_time_in_seconds: int
    historic_traffic_travel_time_in_seconds: int
    live_traffic_incidents_travel_time_in_seconds: int
    route_status: RouteStatusEnum = RouteStatusEnum.planned
