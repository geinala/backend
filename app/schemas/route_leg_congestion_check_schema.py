from typing import TypedDict


class CongestionCheckIncidentRow(TypedDict):
    traffic_incident_id: int | None
    tomtom_incident_id: str
    delay_in_seconds: int
    overlap_ratio: float | None
    rejected_reasons: list[str]
    route_intersects: bool
    is_valid_congestion: bool
    direction_matches: bool | None
    route_point_count: int | None
    incident_point_count: int | None
    cluster_group: int | None
    chosen_for_reopt: bool
    delay_contribution_in_seconds: int
    delay_threshold_in_seconds: int
    overlap_threshold: float
    proximity_threshold_in_meters: int
