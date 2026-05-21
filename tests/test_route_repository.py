from app.repositories.route_repository import RouteRepository


def test_deduplicate_due_arrival_events_keeps_first_occurrence_per_route_leg() -> None:
    events = [
        {
            "route_leg_id": 11,
            "simulation_id": "sim-1",
            "courier_id": 7,
            "node_id": 101,
            "courier_route_id": 22,
            "sequence": 0,
        },
        {
            "route_leg_id": 11,
            "simulation_id": "sim-1",
            "courier_id": 7,
            "node_id": 102,
            "courier_route_id": 22,
            "sequence": 0,
        },
        {
            "route_leg_id": 12,
            "simulation_id": "sim-1",
            "courier_id": 7,
            "node_id": 103,
            "courier_route_id": 22,
            "sequence": 1,
        },
    ]

    deduplicated_events = RouteRepository._deduplicate_due_arrival_events(events)

    assert deduplicated_events == [events[0], events[2]]
