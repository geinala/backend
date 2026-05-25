from datetime import datetime

from sqlalchemy.orm import Session

from app.models.route_leg_congestion_check import RouteLegCongestionCheck
from app.models.route_leg_congestion_check_incident import RouteLegCongestionCheckIncident
from app.schemas.route_leg_congestion_check_schema import CongestionCheckIncidentRow


class RouteLegCongestionCheckRepository:
    def __init__(self, db: Session):
        self.db = db

    def store_congestion_check(
        self,
        simulation_id: str,
        route_leg_id: int,
        courier_id: int,
        checked_at: datetime,
        bbox: tuple[float, float, float, float],
        incidents_found: int,
        accepted_incident_count: int | None = None,
        total_delay_in_seconds: int | None = None,
    ) -> RouteLegCongestionCheck:
        congestion_check = RouteLegCongestionCheck(
            simulation_id=simulation_id,
            route_leg_id=route_leg_id,
            courier_id=courier_id,
            checked_at=checked_at,
            bbox_min_lng=bbox[0],
            bbox_min_lat=bbox[1],
            bbox_max_lng=bbox[2],
            bbox_max_lat=bbox[3],
            incidents_found=incidents_found,
            accepted_incident_count=accepted_incident_count or 0,
            total_delay_in_seconds=total_delay_in_seconds,
        )
        self.db.add(congestion_check)
        self.db.flush()
        self.db.refresh(congestion_check)
        return congestion_check

    def store_congestion_check_incidents(
        self,
        congestion_check_id: int,
        incident_rows: list[CongestionCheckIncidentRow],
    ) -> list[RouteLegCongestionCheckIncident]:
        """Store one row per TomTom incident linked to the congestion_check."""
        created: list[RouteLegCongestionCheckIncident] = []
        for incident_row in incident_rows:
            row = RouteLegCongestionCheckIncident(
                congestion_check_id=congestion_check_id,
                traffic_incident_id=incident_row.get("traffic_incident_id"),
                tomtom_incident_id=incident_row["tomtom_incident_id"],
                delay_in_seconds=incident_row["delay_in_seconds"],
                overlap_ratio=incident_row["overlap_ratio"],
                rejected_reasons=list(incident_row.get("rejected_reasons", [])),
                route_intersects=incident_row["route_intersects"],
                is_valid_congestion=incident_row["is_valid_congestion"],
                direction_matches=incident_row["direction_matches"],
                route_point_count=incident_row["route_point_count"],
                incident_point_count=incident_row["incident_point_count"],
                cluster_group=incident_row["cluster_group"],
                chosen_for_reopt=incident_row["chosen_for_reopt"],
                delay_contribution_in_seconds=incident_row["delay_contribution_in_seconds"],
                delay_threshold_in_seconds=incident_row["delay_threshold_in_seconds"],
                overlap_threshold=incident_row["overlap_threshold"],
                proximity_threshold_in_meters=incident_row["proximity_threshold_in_meters"],
            )
            self.db.add(row)
            created.append(row)

        self.db.flush()
        return created