from datetime import datetime, timedelta
from typing import TypedDict

from sqlalchemy.orm import Session

from app.models.simulation import Simulation, SimulationStatusEnum
from app.models.solution import Solution
from app.models.courier_route import CourierRoute
from app.models.route import RouteLeg, RouteStatusEnum
from app.schemas.route_schema import CreateRouteLeg


class CourierRouteSnapshot(TypedDict):
    courier_route_id: int
    solution_id: int
    simulation_id: str
    courier_id: int
    route_version: int
    total_distance_in_meters: int
    total_time_in_seconds: int
    routes: list[int]


class DueArrivalEvent(TypedDict):
    route_leg_id: int
    simulation_id: str
    courier_id: int
    node_id: int
    from_node_id: int
    to_node_id: int
    courier_route_id: int
    sequence: int
    is_baseline: bool
    congestion_delay_threshold_in_seconds: int
    resequence_improvement_threshold_percent: float


class NextRouteLegSnapshot(TypedDict):
    route_leg_id: int
    courier_route_id: int
    sequence: int
    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    from_node_id: int
    to_node_id: int
    encoded_polyline: str
    encoded_polyline_precision: int
    traffic_delay_in_seconds: int
    travel_time_in_seconds: int
    distance_in_meters: int


class RunningVehicleSnapshot(TypedDict):
    simulation_id: str
    courier_route_id: int
    courier_id: int
    route_leg_id: int
    sequence: int
    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    from_node_id: int
    to_node_id: int
    encoded_polyline: str
    encoded_polyline_precision: int
    departure_time: datetime
    arrival_time: datetime
    travel_time_in_seconds: int
    distance_in_meters: int
    route_status: str


class RouteRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _deduplicate_due_arrival_events(rows: list[DueArrivalEvent]) -> list[DueArrivalEvent]:
        unique_rows: list[DueArrivalEvent] = []
        seen_route_leg_ids: set[int] = set()

        for row in rows:
            route_leg_id = row["route_leg_id"]
            if route_leg_id in seen_route_leg_ids:
                continue

            seen_route_leg_ids.add(route_leg_id)
            unique_rows.append(row)

        return unique_rows
        
    def bulk_insert_route_legs(self, route_legs: list[CreateRouteLeg]):
        objects: list[RouteLeg] = []

        for leg in route_legs:
            leg_data = leg.model_dump()
            route_status = leg_data.get("route_status")

            if isinstance(route_status, RouteStatusEnum):
                leg_data["route_status"] = route_status.value

            objects.append(RouteLeg(**leg_data))

        self.db.bulk_save_objects(objects)

    def get_courier_route_snapshot(self, courier_route_id: int) -> CourierRouteSnapshot | None:
        row = (
            self.db.query(
                CourierRoute.id,
                CourierRoute.solution_id,
                Solution.simulation_id,
                CourierRoute.courier_id,
                CourierRoute.route_version,
                CourierRoute.total_distance_in_meters,
                CourierRoute.total_time_in_seconds,
                Solution.routes,
            )
            .join(Solution, Solution.id == CourierRoute.solution_id)
            .filter(CourierRoute.id == courier_route_id)
            .first()
        )

        if row is None:
            return None

        return {
            "courier_route_id": int(row[0]),
            "solution_id": int(row[1]),
            "simulation_id": str(row[2]),
            "courier_id": int(row[3]),
            "route_version": int(row[4]),
            "total_distance_in_meters": int(row[5]),
            "total_time_in_seconds": int(row[6]),
            "routes": list(row[7]),
        }

    def get_route_leg_by_id(self, route_leg_id: int) -> RouteLeg | None:
        return self.db.query(RouteLeg).filter(RouteLeg.id == route_leg_id).first()

    def get_route_legs_by_courier_route_id(self, courier_route_id: int) -> list[RouteLeg]:
        return (
            self.db.query(RouteLeg)
            .filter(RouteLeg.courier_route_id == courier_route_id)
            .order_by(RouteLeg.sequence.asc())
            .all()
        )

    async def update_route_legs_after_sequence(self, courier_route_id: int, sequence: int, is_initial_route: bool) -> None:  
        next_status = (
            RouteStatusEnum.baseline_planned
            if is_initial_route
            else RouteStatusEnum.cancelled
        )
        
        self.db.query(RouteLeg)\
            .filter(RouteLeg.courier_route_id == courier_route_id)\
            .filter(RouteLeg.sequence > sequence)\
            .update(
                {RouteLeg.route_status: next_status},
                synchronize_session=False
            )

    def shift_route_legs_after_sequence(self, courier_route_id: int, sequence: int, delay_seconds: int) -> int:
        route_legs = (
            self.db.query(RouteLeg)
            .filter(RouteLeg.courier_route_id == courier_route_id)
            .filter(RouteLeg.sequence >= sequence)
            .filter(
                RouteLeg.route_status.in_([
                    RouteStatusEnum.running,
                    RouteStatusEnum.planned,
                    RouteStatusEnum.baseline_planned,
                    RouteStatusEnum.baseline_running,
                ])
            )
            .order_by(RouteLeg.sequence.asc())
            .all()
        )

        if not route_legs:
            return 0

        for route_leg in route_legs:
            if route_leg.sequence == sequence:
                route_leg.travel_time_in_seconds += delay_seconds
                route_leg.traffic_delay_in_seconds += delay_seconds
                route_leg.live_traffic_incidents_travel_time_in_seconds += delay_seconds
                route_leg.arrival_time = route_leg.arrival_time + timedelta(seconds=delay_seconds)
            else:
                route_leg.departure_time = route_leg.departure_time + timedelta(seconds=delay_seconds)
                route_leg.arrival_time = route_leg.arrival_time + timedelta(seconds=delay_seconds)

        return len(route_legs)

    def update_route_leg_delay(self, route_leg_id: int, delay_seconds: int) -> bool:
        route_leg = self.get_route_leg_by_id(route_leg_id)

        if route_leg is None:
            return False

        route_leg.travel_time_in_seconds += delay_seconds
        route_leg.traffic_delay_in_seconds += delay_seconds
        route_leg.live_traffic_incidents_travel_time_in_seconds += delay_seconds
        route_leg.arrival_time = route_leg.arrival_time + timedelta(seconds=delay_seconds)
        return True

    def get_due_arrival_events_for_running_simulations(self, reference_time: datetime) -> list[DueArrivalEvent]:
        rows = (
            self.db.query(
                RouteLeg.id,
                Solution.simulation_id,
                CourierRoute.courier_id,
                RouteLeg.from_node_id,
                RouteLeg.to_node_id,
                RouteLeg.courier_route_id,
                RouteLeg.sequence,
                RouteLeg.route_status,
                Simulation.congestion_delay_threshold_in_seconds,
                Simulation.resequence_improvement_threshold_percent
            )
            .join(CourierRoute, CourierRoute.id == RouteLeg.courier_route_id)
            .join(Solution, Solution.id == CourierRoute.solution_id)
            .join(Simulation, Simulation.id == Solution.simulation_id)
            .filter(Simulation.status == SimulationStatusEnum.running)
            .filter(RouteLeg.arrival_time <= reference_time)
            .filter(RouteLeg.route_status.in_([RouteStatusEnum.planned, RouteStatusEnum.running, RouteStatusEnum.baseline_planned, RouteStatusEnum.baseline_running]))
            .order_by(Solution.simulation_id.asc(), CourierRoute.courier_id.asc(), RouteLeg.sequence.asc())
            .all()
        )

        events: list[DueArrivalEvent] = [
            {
                "route_leg_id": int(row[0]),
                "simulation_id": str(row[1]),
                "courier_id": int(row[2]),
                "node_id": int(row[4]) if row[4] is not None else -1,
                "from_node_id": int(row[3]),
                "to_node_id": int(row[4]),
                "courier_route_id": int(row[5]),
                "sequence": int(row[6]),
                "is_baseline": row[7] in [RouteStatusEnum.baseline_planned, RouteStatusEnum.baseline_running],
                "congestion_delay_threshold_in_seconds": int(row[8]),
                "resequence_improvement_threshold_percent": int(row[9]),
            }
            for row in rows
        ]

        return self._deduplicate_due_arrival_events(events)

    def get_running_vehicle_snapshots_for_simulation(self, simulation_id: str) -> list[RunningVehicleSnapshot]:
        rows = (
            self.db.query(
                Simulation.id,
                CourierRoute.id,
                CourierRoute.courier_id,
                RouteLeg.id,
                RouteLeg.sequence,
                RouteLeg.origin_latitude,
                RouteLeg.origin_longitude,
                RouteLeg.destination_latitude,
                RouteLeg.destination_longitude,
                RouteLeg.from_node_id,
                RouteLeg.to_node_id,
                RouteLeg.encoded_polyline,
                RouteLeg.encoded_polyline_precision,
                RouteLeg.departure_time,
                RouteLeg.arrival_time,
                RouteLeg.travel_time_in_seconds,
                RouteLeg.distance_in_meters,
                RouteLeg.route_status,
            )
            .select_from(RouteLeg)
            .join(CourierRoute, CourierRoute.id == RouteLeg.courier_route_id)
            .join(Solution, Solution.id == CourierRoute.solution_id)
            .join(Simulation, Simulation.id == Solution.simulation_id)
            .filter(Simulation.id == simulation_id)
            .filter(Simulation.status == SimulationStatusEnum.running)
            .filter(RouteLeg.route_status == RouteStatusEnum.running)
            .order_by(CourierRoute.courier_id.asc(), RouteLeg.sequence.asc())
            .all()
        )

        return [
            {
                "simulation_id": str(row[0]),
                "courier_route_id": int(row[1]),
                "courier_id": int(row[2]),
                "route_leg_id": int(row[3]),
                "sequence": int(row[4]),
                "origin_latitude": float(row[5]),
                "origin_longitude": float(row[6]),
                "destination_latitude": float(row[7]),
                "destination_longitude": float(row[8]),
                "from_node_id": int(row[9]),
                "to_node_id": int(row[10]),
                "encoded_polyline": str(row[11]),
                "encoded_polyline_precision": int(row[12]),
                "departure_time": row[13],
                "arrival_time": row[14],
                "travel_time_in_seconds": int(row[15]),
                "distance_in_meters": int(row[16]),
                "route_status": row[17].value if isinstance(row[17], RouteStatusEnum) else str(row[17]),
            }
            for row in rows
        ]

    def mark_route_leg_as_visited(self, route_leg_id: int, is_baseline: bool) -> bool:
        expected_status = RouteStatusEnum.baseline_running if is_baseline else RouteStatusEnum.running
        new_status = RouteStatusEnum.baseline_completed if is_baseline else RouteStatusEnum.completed

        updated_count = self.db.query(RouteLeg).filter(
            RouteLeg.id == route_leg_id,
            RouteLeg.route_status == expected_status
        ).update(
            {RouteLeg.route_status: new_status},
            synchronize_session=False
        )

        return updated_count > 0

    def promote_next_route_leg_to_in_progress(self, courier_route_id: int, current_sequence: int, is_baseline: bool = False) -> bool:
        running_status = RouteStatusEnum.baseline_running if is_baseline else RouteStatusEnum.running
        target_status = RouteStatusEnum.baseline_planned if is_baseline else RouteStatusEnum.planned

        next_leg = (
            self.db.query(RouteLeg)
            .filter(RouteLeg.courier_route_id == courier_route_id)
            .filter(RouteLeg.sequence > current_sequence)
            .filter(RouteLeg.route_status == target_status)
            .order_by(RouteLeg.sequence.asc())
            .first()
        )

        if next_leg is None:
            return False

        next_leg.route_status = running_status
        return True
    
    def transition_current_route_leg_for_reoptimization(self, route_leg_id: int, is_initial_route: bool) -> None:
        next_status = (
            RouteStatusEnum.baseline_running
            if is_initial_route
            else RouteStatusEnum.cancelled
        )
        self.db.query(RouteLeg).filter(RouteLeg.id == route_leg_id).update(
            {RouteLeg.route_status: next_status},
            synchronize_session=False
        )

    def get_next_route_leg_after_sequence(
        self,
        courier_route_id: int,
        current_sequence: int,
    ) -> NextRouteLegSnapshot | None:
        next_leg = (
            self.db.query(RouteLeg)
            .filter(RouteLeg.courier_route_id == courier_route_id)
            .filter(RouteLeg.sequence > current_sequence)
            .filter(RouteLeg.route_status.in_([RouteStatusEnum.baseline_planned, RouteStatusEnum.baseline_running, RouteStatusEnum.planned, RouteStatusEnum.running]))
            .order_by(RouteLeg.sequence.asc())
            .first()
        )

        if next_leg is None:
            return None

        return {
            "route_leg_id": int(next_leg.id),
            "courier_route_id": int(next_leg.courier_route_id),
            "sequence": int(next_leg.sequence),
            "origin_latitude": float(next_leg.origin_latitude),
            "origin_longitude": float(next_leg.origin_longitude),
            "destination_latitude": float(next_leg.destination_latitude),
            "destination_longitude": float(next_leg.destination_longitude),
            "from_node_id": int(next_leg.from_node_id),
            "to_node_id": int(next_leg.to_node_id),
            "encoded_polyline": str(next_leg.encoded_polyline),
            "encoded_polyline_precision": int(next_leg.encoded_polyline_precision),
            "traffic_delay_in_seconds": int(next_leg.traffic_delay_in_seconds),
            "travel_time_in_seconds": int(next_leg.travel_time_in_seconds),
            "distance_in_meters": int(next_leg.distance_in_meters),
        }