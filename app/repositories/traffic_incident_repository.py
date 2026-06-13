import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.traffic_incident import TrafficIncident
from app.services.tomtom_service import IncidentFeature


class TrafficIncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _parse_tomtom_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None

        normalized_value = value.replace("Z", "+00:00")
        parsed_value = datetime.fromisoformat(normalized_value)

        if parsed_value.tzinfo is None:
            return parsed_value.replace(tzinfo=timezone.utc)

        return parsed_value

    def store_congestion_incident(
        self,
        simulation_id: str,
        detected_at: datetime,
        incident: IncidentFeature,
    ) -> TrafficIncident:
        incident_properties = incident["properties"]
        tomtom_incident_id = incident_properties["id"]
        length_in_meters = int(round(incident_properties["length"]))
        event_descriptions = [
            event["description"]
            for event in incident_properties.get("events", [])
            if event.get("description")
        ]

        payload: dict[str, object] = {
            "tomtom_incident_id": tomtom_incident_id,
            "simulation_id": uuid.UUID(simulation_id),
            "detected_at": detected_at,
            "category": int(incident_properties["iconCategory"]),
            "delay_in_seconds": int(incident_properties["delay"] or 0),
            "geometry": json.dumps(incident["geometry"]),
            "start_time": self._parse_tomtom_datetime(incident_properties["startTime"]) or datetime.now(timezone.utc),
            "end_time": self._parse_tomtom_datetime(incident_properties.get("endTime")),
            "length_in_meters": length_in_meters,
            "from_address": incident_properties.get("from"),
            "to_address": incident_properties.get("to"),
            "incident_description": "; ".join(event_descriptions) if event_descriptions else None,
        }

        insert_stmt = (
            insert(TrafficIncident)
            .values(**payload)
            .on_conflict_do_nothing(index_elements=[TrafficIncident.tomtom_incident_id])
            .returning(TrafficIncident.id)
        )

        inserted_incident_id = self.db.execute(insert_stmt).scalar_one_or_none()

        if inserted_incident_id is not None:
            traffic_incident = (
                self.db.query(TrafficIncident)
                .filter(TrafficIncident.id == int(inserted_incident_id))
                .first()
            )
        else:
            traffic_incident = (
                self.db.query(TrafficIncident)
                .filter(TrafficIncident.tomtom_incident_id == tomtom_incident_id)
                .first()
            )

        if traffic_incident is None:
            raise RuntimeError(f"Failed to persist traffic incident {tomtom_incident_id}.")

        self.db.flush()
        self.db.refresh(traffic_incident)
        return traffic_incident