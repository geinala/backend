import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.route_leg_congestion_check import RouteLegCongestionCheck


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
        accepted_incident_id: int | None,
        match_details: dict[str, object],
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
            accepted_incident_id=accepted_incident_id,
            match_details=json.dumps(match_details, default=str),
        )
        self.db.add(congestion_check)
        self.db.flush()
        self.db.refresh(congestion_check)
        return congestion_check