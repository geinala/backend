import time
from datetime import datetime, timezone
from typing import Any

from app.lib.logging.logging import get_logger
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.route_repository import RouteRepository, RunningVehicleSnapshot
from app.services.realtime_event_service import publish_realtime_event

logger = get_logger(__name__)


class SimulationEngineService:
    def __init__(
        self,
        simulation_repository: SimulationRepository,
        route_repository: RouteRepository,
        tick_interval_seconds: float = 5.0,
    ):
        self.simulation_repository = simulation_repository
        self.route_repository = route_repository
        self.tick_interval_seconds = max(tick_interval_seconds, 0.1)

    def tick_once(self, reference_time: datetime | None = None) -> int:
        now = reference_time or datetime.now(timezone.utc)
        running_simulations = self.simulation_repository.get_running_simulations()

        for simulation in running_simulations:
            running_vehicle_snapshots = self.route_repository.get_running_vehicle_snapshots_for_simulation(
                str(simulation.id)
            )

            publish_realtime_event(
                "SIMULATION_TICK",
                self._build_tick_payload(
                    simulation=simulation,
                    reference_time=now,
                    tick_interval_seconds=self.tick_interval_seconds,
                    vehicle_snapshots=running_vehicle_snapshots,
                ),
                simulation_id=str(simulation.id),
            )

        logger.info(
            {
                "event_type": "simulation_engine_tick",
                "running_simulation_count": len(running_simulations),
                "tick_interval_seconds": self.tick_interval_seconds,
                "tick_at": now.isoformat(),
            }
        )

        return len(running_simulations)

    def run_forever(self) -> None:
        while True:
            self.tick_once()
            time.sleep(self.tick_interval_seconds)

    @staticmethod
    def _build_tick_payload(
        simulation: Any,
        reference_time: datetime,
        tick_interval_seconds: float,
        vehicle_snapshots: list[RunningVehicleSnapshot],
    ) -> dict[str, Any]:
        started_at = getattr(simulation, "started_at", None) or reference_time
        elapsed_seconds = max(int((reference_time - started_at).total_seconds()), 0)

        total_duration = max(
            int(
                getattr(simulation, "initial_total_duration_in_seconds", None)
                or getattr(simulation, "final_total_duration_in_seconds", None)
                or 0
            ),
            0,
        )
        time_progress = 0.0
        if total_duration > 0:
            time_progress = min(elapsed_seconds / total_duration, 1.0)

        total_nodes = max(int(getattr(simulation, "total_nodes", 0) or 0), 0)
        completed_nodes = max(int(getattr(simulation, "total_completed_nodes", 0) or 0), 0)
        actual_progress = (completed_nodes / total_nodes) if total_nodes > 0 else 0.0
        interpolated_progress = min(max(actual_progress, time_progress), 1.0)

        vehicles = [
            SimulationEngineService._build_vehicle_payload(vehicle_snapshot, reference_time)
            for vehicle_snapshot in vehicle_snapshots
        ]

        return {
            "simulationId": str(getattr(simulation, "id")),
            "tick": elapsed_seconds,
            "status": getattr(simulation.status, "value", str(getattr(simulation, "status", "unknown"))),
            "tickAt": reference_time.isoformat(),
            "elapsedSeconds": elapsed_seconds,
            "tickIntervalSeconds": tick_interval_seconds,
            "totalDurationSeconds": total_duration,
            "completedNodes": completed_nodes,
            "totalNodes": total_nodes,
            "activeCouriers": int(getattr(simulation, "total_active_couriers", 0) or 0),
            "actualProgress": round(actual_progress, 4),
            "timeProgress": round(time_progress, 4),
            "interpolatedProgress": round(interpolated_progress, 4),
            "vehicles": vehicles,
        }

    @staticmethod
    def _build_vehicle_payload(
        vehicle_snapshot: RunningVehicleSnapshot,
        reference_time: datetime,
    ) -> dict[str, Any]:
        departure_time = vehicle_snapshot["departure_time"]
        arrival_time = vehicle_snapshot["arrival_time"]
        travel_duration_seconds = max(int((arrival_time - departure_time).total_seconds()), 1)
        elapsed_vehicle_seconds = max(int((reference_time - departure_time).total_seconds()), 0)
        vehicle_progress = min(max(elapsed_vehicle_seconds / travel_duration_seconds, 0.0), 1.0)

        route_points = SimulationEngineService._decode_polyline(
            vehicle_snapshot["encoded_polyline"],
            vehicle_snapshot["encoded_polyline_precision"],
        )
        interpolated_position = SimulationEngineService._interpolate_path(route_points, vehicle_progress)

        if interpolated_position is None:
            interpolated_position = (
                vehicle_snapshot["origin_latitude"],
                vehicle_snapshot["origin_longitude"],
            )

        speed_meters_per_second = 0.0
        if vehicle_snapshot["travel_time_in_seconds"] > 0:
            speed_meters_per_second = (
                vehicle_snapshot["distance_in_meters"] / vehicle_snapshot["travel_time_in_seconds"]
            )

        return {
            "id": vehicle_snapshot["courier_route_id"],
            "courierId": vehicle_snapshot["courier_id"],
            "courierRouteId": vehicle_snapshot["courier_route_id"],
            "routeLegId": vehicle_snapshot["route_leg_id"],
            "sequence": vehicle_snapshot["sequence"],
            "lat": round(interpolated_position[0], 6),
            "lng": round(interpolated_position[1], 6),
            "speed": round(speed_meters_per_second, 2),
            "progress": round(vehicle_progress, 4),
            "status": vehicle_snapshot["route_status"],
        }

    @staticmethod
    def _decode_polyline(encoded_polyline: str, precision: int) -> list[tuple[float, float]]:
        if not encoded_polyline:
            return []

        scale = 10 ** max(precision, 0)
        index = 0
        latitude = 0
        longitude = 0
        coordinates: list[tuple[float, float]] = []

        while index < len(encoded_polyline):
            shift = 0
            result = 0

            while True:
                chunk = ord(encoded_polyline[index]) - 63
                index += 1
                result |= (chunk & 0x1F) << shift
                shift += 5
                if chunk < 0x20:
                    break

            delta_latitude = ~(result >> 1) if result & 1 else (result >> 1)
            latitude += delta_latitude

            shift = 0
            result = 0

            while True:
                chunk = ord(encoded_polyline[index]) - 63
                index += 1
                result |= (chunk & 0x1F) << shift
                shift += 5
                if chunk < 0x20:
                    break

            delta_longitude = ~(result >> 1) if result & 1 else (result >> 1)
            longitude += delta_longitude

            coordinates.append((latitude / scale, longitude / scale))

        return coordinates

    @staticmethod
    def _interpolate_path(
        coordinates: list[tuple[float, float]],
        progress: float,
    ) -> tuple[float, float] | None:
        if not coordinates:
            return None

        if len(coordinates) == 1:
            return coordinates[0]

        if progress <= 0:
            return coordinates[0]

        if progress >= 1:
            return coordinates[-1]

        segment_distances: list[float] = [0.0]
        total_distance = 0.0

        for index in range(1, len(coordinates)):
            previous_latitude, previous_longitude = coordinates[index - 1]
            current_latitude, current_longitude = coordinates[index]
            distance = ((current_longitude - previous_longitude) ** 2 + (current_latitude - previous_latitude) ** 2) ** 0.5

            total_distance += distance
            segment_distances.append(total_distance)

        if total_distance == 0:
            return coordinates[-1]

        target_distance = total_distance * progress

        for index in range(1, len(segment_distances)):
            start_distance = segment_distances[index - 1]
            end_distance = segment_distances[index]

            if target_distance > end_distance and index < len(segment_distances) - 1:
                continue

            segment_length = end_distance - start_distance
            segment_progress = 0.0 if segment_length == 0 else (target_distance - start_distance) / segment_length
            start_latitude, start_longitude = coordinates[index - 1]
            end_latitude, end_longitude = coordinates[index]

            return (
                start_latitude + (end_latitude - start_latitude) * segment_progress,
                start_longitude + (end_longitude - start_longitude) * segment_progress,
            )

        return coordinates[-1]