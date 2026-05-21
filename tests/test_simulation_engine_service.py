from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.simulation_engine_service import SimulationEngineService


class FakeSimulationRepository:
    def __init__(self, simulations):
        self._simulations = simulations

    def get_running_simulations(self):
        return self._simulations


class FakeRouteRepository:
    def __init__(self, snapshots):
        self._snapshots = snapshots

    def get_running_vehicle_snapshots_for_simulation(self, simulation_id):
        return self._snapshots.get(simulation_id, [])


def test_tick_once_publishes_interpolated_tick(monkeypatch):
    published_events = []

    def fake_publish_realtime_event(event_type, payload, simulation_id=None):
        published_events.append((event_type, payload, simulation_id))

    monkeypatch.setattr(
        "app.services.simulation_engine_service.publish_realtime_event",
        fake_publish_realtime_event,
    )

    simulation = SimpleNamespace(
        id="sim-123",
        status=SimpleNamespace(value="running"),
        started_at=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
        total_duration_in_seconds=100,
        total_completed_nodes=20,
        total_nodes=40,
        total_active_couriers=3,
    )

    vehicle_snapshot = {
        "simulation_id": "sim-123",
        "courier_route_id": 1,
        "courier_id": 10,
        "route_leg_id": 42,
        "sequence": 0,
        "origin_latitude": -7.9821,
        "origin_longitude": 112.6302,
        "destination_latitude": -7.9788,
        "destination_longitude": 112.6344,
        "encoded_polyline": "_flwF~qspM??",
        "encoded_polyline_precision": 5,
        "departure_time": datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
        "arrival_time": datetime(2026, 5, 21, 12, 1, tzinfo=timezone.utc),
        "travel_time_in_seconds": 60,
        "distance_in_meters": 1200,
        "route_status": "running",
    }

    service = SimulationEngineService(
        FakeSimulationRepository([simulation]),
        FakeRouteRepository({"sim-123": [vehicle_snapshot]}),
        tick_interval_seconds=0.5,
    )

    count = service.tick_once(reference_time=datetime(2026, 5, 21, 12, 0, 30, tzinfo=timezone.utc))

    assert count == 1
    assert published_events == [
        (
            "SIMULATION_TICK",
            {
                "simulationId": "sim-123",
                    "tick": 30,
                "status": "running",
                "tickAt": "2026-05-21T12:00:30+00:00",
                "elapsedSeconds": 30,
                "tickIntervalSeconds": 0.5,
                "totalDurationSeconds": 100,
                "completedNodes": 20,
                "totalNodes": 40,
                "activeCouriers": 3,
                "actualProgress": 0.5,
                "timeProgress": 0.3,
                "interpolatedProgress": 0.5,
                    "vehicles": [
                        {
                            "id": 1,
                            "courierId": 10,
                            "courierRouteId": 1,
                            "routeLegId": 42,
                            "sequence": 0,
                            "lat": -7.9821,
                            "lng": 112.6302,
                            "speed": 20.0,
                            "progress": 0.5,
                            "status": "running",
                        }
                    ],
            },
            "sim-123",
        )
    ]


def test_tick_once_no_running_simulations(monkeypatch):
    monkeypatch.setattr(
        "app.services.simulation_engine_service.publish_realtime_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not publish")),
    )

    service = SimulationEngineService(FakeSimulationRepository([]))

    assert service.tick_once(reference_time=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)) == 0