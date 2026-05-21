from datetime import datetime
from typing import TypedDict

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.node import Node
from app.models.simulation import Simulation, SimulationStatusEnum
from app.models.solution import Solution
from app.models.route import CreateRouteLeg, RouteLeg, RouteStatusEnum
from app.models.courier_route import CourierRoute


class DueArrivalEvent(TypedDict):
    route_leg_id: int
    simulation_id: str
    courier_id: int
    node_id: int
    courier_route_id: int
    sequence: int


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

    def get_due_arrival_events_for_running_simulations(self, reference_time: datetime) -> list[DueArrivalEvent]:
        rows = (
            self.db.query(
                RouteLeg.id,
                Solution.simulation_id,
                CourierRoute.courier_id,
                Node.id,
                RouteLeg.courier_route_id,
                RouteLeg.sequence,
            )
            .join(CourierRoute, CourierRoute.id == RouteLeg.courier_route_id)
            .join(Solution, Solution.id == CourierRoute.solution_id)
            .join(Simulation, Simulation.id == Solution.simulation_id)
            .outerjoin(
                Node,
                and_(
                    Node.simulation_id == Solution.simulation_id,
                    Node.latitude == RouteLeg.destination_latitude,
                    Node.longitude == RouteLeg.destination_longitude,
                ),
            )
            .filter(Simulation.status == SimulationStatusEnum.running)
            .filter(RouteLeg.arrival_time <= reference_time)
            .filter(RouteLeg.route_status.in_([RouteStatusEnum.planned, RouteStatusEnum.running]))
            .order_by(Solution.simulation_id.asc(), CourierRoute.courier_id.asc(), RouteLeg.sequence.asc())
            .all()
        )

        events: list[DueArrivalEvent] = [
            {
                "route_leg_id": int(row[0]),
                "simulation_id": str(row[1]),
                "courier_id": int(row[2]),
                "node_id": int(row[3]) if row[3] is not None else -1,
                "courier_route_id": int(row[4]),
                "sequence": int(row[5]),
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
                "encoded_polyline": str(row[9]),
                "encoded_polyline_precision": int(row[10]),
                "departure_time": row[11],
                "arrival_time": row[12],
                "travel_time_in_seconds": int(row[13]),
                "distance_in_meters": int(row[14]),
                "route_status": row[15].value if isinstance(row[15], RouteStatusEnum) else str(row[15]),
            }
            for row in rows
        ]

    def mark_route_leg_as_visited(self, route_leg_id: int) -> bool:
        route_leg = self.db.query(RouteLeg).filter(RouteLeg.id == route_leg_id).first()

        if route_leg is None:
            return False

        route_leg.route_status = RouteStatusEnum.completed
        return True

    def promote_next_route_leg_to_in_progress(self, courier_route_id: int, current_sequence: int) -> bool:
        next_leg = (
            self.db.query(RouteLeg)
            .filter(RouteLeg.courier_route_id == courier_route_id)
            .filter(RouteLeg.sequence > current_sequence)
            .filter(RouteLeg.route_status == RouteStatusEnum.planned)
            .order_by(RouteLeg.sequence.asc())
            .first()
        )

        if next_leg is None:
            return False

        next_leg.route_status = RouteStatusEnum.running
        return True