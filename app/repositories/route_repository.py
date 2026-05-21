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