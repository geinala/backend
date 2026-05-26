import asyncio
import json
from types import SimpleNamespace
from typing import Any, cast

from app.models.reoptimization_event import ReoptimizationOutcomeEnum
from app.services.dvrp_reoptimization_service import DVRPReoptimizationService


class FakeQuery:
    def __init__(self, result: Any) -> None:
        self._result = result

    def filter_by(self, **kwargs: Any) -> "FakeQuery":
        return self

    def filter(self, *args: Any, **kwargs: Any) -> "FakeQuery":
        return self

    def first(self) -> Any:
        return self._result


class FakeDb:
    def __init__(self, simulation: Any, route_leg: Any) -> None:
        self.simulation = simulation
        self.route_leg = route_leg
        self.added_objects: list[Any] = []
        self.executed_statements: list[Any] = []

    def query(self, model: Any) -> FakeQuery:
        if getattr(model, "__name__", None) == "Simulation":
            return FakeQuery(self.simulation)

        return FakeQuery(self.route_leg)

    def add(self, obj: Any) -> None:
        self.added_objects.append(obj)

    def execute(self, statement: Any) -> SimpleNamespace:
        self.executed_statements.append(statement)
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    def commit(self) -> None:
        return None

    def refresh(self, obj: Any) -> None:
        return None

    def rollback(self) -> None:
        return None


class FakeSimulationRepository:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.updated_fields: tuple[str, dict[str, Any]] | None = None

    async def update_simulation_fields(self, simulation_id: str, fields: dict[str, Any]) -> None:
        self.updated_fields = (simulation_id, fields)


class FakeRouteRepository:
    def __init__(self, db: Any) -> None:
        self.db = db


class FakeNodeRepository:
    pass


class FakeMatrixService:
    pass


class FakeTomTomService:
    pass


class FakeOptimizationRunRepository:
    def bulk_insert_optimization_runs(self, runs: list[Any]) -> list[Any]:
        created_runs: list[Any] = []
        for index, run in enumerate(runs, start=1):
            created_runs.append(SimpleNamespace(id=index, **run.model_dump()))
        return created_runs


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
    simulation_repository = FakeSimulationRepository(simulation_db)

    service = cast(
        Any,
        DVRPReoptimizationService(
            route_repository=cast(Any, FakeRouteRepository(route_db)),
            node_repository=cast(Any, FakeNodeRepository()),
            simulation_repository=cast(Any, simulation_repository),
            matrix_service=cast(Any, FakeMatrixService()),
            tomtom_service=cast(Any, FakeTomTomService()),
            optimization_run_repository=cast(Any, FakeOptimizationRunRepository()),
        ),
    )

    result = asyncio.run(
        service._finalize_reoptimization(
            simulation_id="sim-123",
            courier_route_id=11,
            courier_id=1,
            current_sequence=3,
            delay_seconds=12,
            route_leg_id=7,
            optimization_run_id=42,
            algorithm_used="tabu_search",
            outcome=ReoptimizationOutcomeEnum.duration_updated,
            before_total_distance_in_meters=1000,
            before_total_time_in_seconds=600,
            after_total_distance_in_meters=1000,
            after_total_time_in_seconds=612,
            before_computation_time_in_ms=42.0,
            total_nodes_explored=8,
            current_route_leg=route_leg,
            congestion_check_id=None,
        )
    )

    assert result["outcome"] == "duration_updated"
    assert len(route_db.added_objects) == 2

    event = route_db.added_objects[0]
    assert event.optimization_run_id == 42
    assert event.distance_saved_in_meters == 0
    assert event.time_saved_in_seconds == -12
    assert json.loads(event.courier_position) == [
        {
            "courier_id": 1,
            "lat": 0.0,
            "lng": 0.0,
            "bearing": 90,
        }
    ]

    simulation_log = route_db.added_objects[1]
    assert simulation_log.event_type == "route_reoptimized"
    assert simulation_log.courier_route_id == 11
    assert json.loads(simulation_log.log_metadata)["delay_seconds"] == 12
    assert simulation_repository.updated_fields == (
        "sim-123",
        {
            "final_total_distance_in_meters": 1000,
            "final_total_duration_in_seconds": 612,
            "distance_improvement_in_meters": 0,
            "duration_improvement_in_seconds": -12,
            "total_reoptimized_routes": 1,
            "total_incidents_affecting_routes": 1,
        },
    )


def test_store_final_reoptimization_run_uses_traffic_incident_trigger_type():
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
    simulation_repository = FakeSimulationRepository(route_db)

    service = cast(
        Any,
        DVRPReoptimizationService(
            route_repository=cast(Any, FakeRouteRepository(route_db)),
            node_repository=cast(Any, FakeNodeRepository()),
            simulation_repository=cast(Any, simulation_repository),
            matrix_service=cast(Any, FakeMatrixService()),
            tomtom_service=cast(Any, FakeTomTomService()),
            optimization_run_repository=cast(Any, FakeOptimizationRunRepository()),
        ),
    )

    run = service._store_final_reoptimization_run(
        simulation_id="sim-123",
        congestion_check_id=9,
        before_total_distance_in_meters=1000,
        before_total_time_in_seconds=600,
        after_total_distance_in_meters=1000,
        after_total_time_in_seconds=612,
        algorithm_used="tabu_search",
        computation_time_in_ms=7.5,
        total_nodes_explored=3,
    )

    assert run.trigger_type == "traffic_incident"
    assert run.total_distance_in_meters == 1000
    assert run.total_travel_time_in_seconds == 612