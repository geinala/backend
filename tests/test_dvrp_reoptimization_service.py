from types import SimpleNamespace
import asyncio
import json

from app.models.reoptimization_event import ReoptimizationOutcomeEnum
from app.services.dvrp_reoptimization_service import DVRPReoptimizationService


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter_by(self, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class FakeDb:
    def __init__(self, simulation, route_leg):
        self.simulation = simulation
        self.route_leg = route_leg
        self.added_objects = []

    def query(self, model):
        if getattr(model, "__name__", None) == "Simulation":
            return FakeQuery(self.simulation)

        return FakeQuery(self.route_leg)

    def add(self, obj):
        self.added_objects.append(obj)


class FakeSimulationRepository:
    def __init__(self, db):
        self.db = db
        self.updated_fields = None

    async def update_simulation_fields(self, simulation_id, fields):
        self.updated_fields = (simulation_id, fields)


class FakeRouteRepository:
    def __init__(self, db):
        self.db = db


class FakeNodeRepository:
    pass


class FakeMatrixService:
    pass


class FakeTomTomService:
    pass


class FakeOptimizationRunRepository:
    pass


def test_finalize_reoptimization_stores_courier_position_as_marker_payload():
    simulation = SimpleNamespace(
        id="sim-123",
        total_reoptimized_routes=0,
        total_incidents_affecting_routes=0,
        initial_total_distance_in_meters=1000,
        initial_total_duration_in_seconds=600,
    )
    route_leg = SimpleNamespace(
        id=7,
        courier_route_id=11,
        origin_latitude=0.0,
        origin_longitude=0.0,
        destination_latitude=0.0,
        destination_longitude=1.0,
        encoded_polyline="",
        encoded_polyline_precision=5,
    )

    route_db = FakeDb(simulation=simulation, route_leg=route_leg)
    simulation_db = FakeDb(simulation=simulation, route_leg=route_leg)

    service = DVRPReoptimizationService(
        route_repository=FakeRouteRepository(route_db),
        node_repository=FakeNodeRepository(),
        simulation_repository=FakeSimulationRepository(simulation_db),
        matrix_service=FakeMatrixService(),
        tomtom_service=FakeTomTomService(),
        optimization_run_repository=FakeOptimizationRunRepository(),
    )

    result = asyncio.run(
        service._finalize_reoptimization(  # noqa: SLF001
            simulation_id="sim-123",
            courier_route_id=11,
            courier_id=1,
            current_sequence=3,
            delay_seconds=12,
            traffic_incident_id=None,
            route_leg_id=7,
            algorithm_used="tabu_search",
            outcome=ReoptimizationOutcomeEnum.duration_updated,
            before_total_distance_in_meters=1000,
            before_total_time_in_seconds=600,
            after_total_distance_in_meters=950,
            after_total_time_in_seconds=580,
            before_computation_time_in_ms=42.0,
            total_nodes_explored=8,
        )
    )

    assert result["outcome"] == "duration_updated"
    assert len(route_db.added_objects) == 1

    event = route_db.added_objects[0]
    assert json.loads(event.courier_position) == [
        {
            "courier_id": 1,
            "lat": 0.0,
            "lng": 0.0,
            "bearing": 90,
        }
    ]