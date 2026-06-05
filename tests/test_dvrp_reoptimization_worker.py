import inspect

import app.workers.dvrp_reoptimization_worker as worker_module


def test_process_congestion_reoptimization_wraps_async_implementation(monkeypatch):
    called = {}

    async def fake_process_congestion_reoptimization(**kwargs):
        called["kwargs"] = kwargs
        return {"outcome": "duration_updated"}

    def fake_asyncio_run(coro):
        assert inspect.iscoroutine(coro)
        called["ran"] = True
        return {"status": "success"}

    monkeypatch.setattr(worker_module, "_process_congestion_reoptimization", fake_process_congestion_reoptimization)
    monkeypatch.setattr(worker_module.asyncio, "run", fake_asyncio_run)

    result = worker_module.process_congestion_reoptimization(
        simulation_id="sim-1",
        route_leg_id=11,
        courier_route_id=22,
        courier_id=3,
        current_sequence=4,
        delay_seconds=120,
        traffic_incident_id=7,
        congestion_check_id=8,
        force_duration_update_only=True,
    )

    assert result == {"status": "success"}
    assert called["ran"] is True
    assert called["kwargs"] == {
        "simulation_id": "sim-1",
        "route_leg_id": 11,
        "courier_route_id": 22,
        "courier_id": 3,
        "current_sequence": 4,
        "delay_seconds": 120,
        "traffic_incident_id": 7,
        "congestion_check_id": 8,
        "force_duration_update_only": True,
    }
