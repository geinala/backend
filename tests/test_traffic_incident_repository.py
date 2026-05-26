from datetime import datetime, timezone
from types import SimpleNamespace

from app.repositories.traffic_incident_repository import TrafficIncidentRepository


class FakeExecuteResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id

    def scalar_one_or_none(self):
        return self.inserted_id


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class FakeDb:
    def __init__(self, existing_incident, inserted_id=None):
        self.existing_incident = existing_incident
        self.inserted_id = inserted_id
        self.executed_statements = []

    def execute(self, statement):
        self.executed_statements.append(statement)
        return FakeExecuteResult(self.inserted_id)

    def query(self, model):
        return FakeQuery(self.existing_incident)

    def flush(self):
        return None

    def refresh(self, obj):
        return None


def test_store_congestion_incident_keeps_existing_row_on_conflict():
    existing_incident = SimpleNamespace(
        id=44,
        tomtom_incident_id="TTI-OLD",
        simulation_id="sim-old",
        category=3,
        delay_in_seconds=80,
        geometry="{}",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=None,
        length_in_meters=120,
        from_address="old-from",
        to_address="old-to",
        detected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        incident_description="old",
    )
    db = FakeDb(existing_incident=existing_incident, inserted_id=None)
    repository = TrafficIncidentRepository(db)

    incident = {
        "properties": {
            "id": "TTI-NEW",
            "iconCategory": 5,
            "delay": 250,
            "length": 450,
            "startTime": "2026-01-01T00:00:00Z",
            "events": [{"description": "new incident"}],
            "from": "new-from",
            "to": "new-to",
        },
        "geometry": {"type": "LineString", "coordinates": [[112.6, -7.9], [112.7, -7.8]]},
    }

    result = repository.store_congestion_incident(
        simulation_id="sim-uuid",
        detected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        incident=incident,  # type: ignore[arg-type]
    )

    assert result is existing_incident
    assert result.tomtom_incident_id == "TTI-OLD"
    assert result.category == 3
    assert result.delay_in_seconds == 80
    assert len(db.executed_statements) == 1