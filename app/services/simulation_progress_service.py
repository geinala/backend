import time
from datetime import datetime, timezone
from typing import Sequence

from app.configs.environment_configuration import get_environment_configuration
from app.lib.logging.logging import get_logger
from app.lib.route_geometry import build_coordinate_points, build_incident_bbox, decode_polyline, incident_matches_route
from app.models.traffic_incident import TrafficIncident
from app.repositories.node_repository import NodeRepository
from app.repositories.route_leg_congestion_check_repository import RouteLegCongestionCheckRepository
from app.repositories.route_repository import DueArrivalEvent, NextRouteLegSnapshot, RouteRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.traffic_incident_repository import TrafficIncidentRepository
from app.services.tomtom_service import IncidentFeature, TomTomService
from app.workers.events_worker import (
    emit_next_route_congestion_detected_event,
    emit_vehicle_arrived_event,
    emit_vehicle_departed_node_event,
    emit_vehicle_returned_to_depot_event,
)

logger = get_logger(__name__)
CONGESTION_CHECK_DELAY_SECONDS = 5
settings = get_environment_configuration()


class SimulationProgressService:
    def __init__(
        self,
        route_repository: RouteRepository,
        route_leg_congestion_check_repository: RouteLegCongestionCheckRepository,
        node_repository: NodeRepository,
        simulation_repository: SimulationRepository,
        traffic_incident_repository: TrafficIncidentRepository,
        tomtom_service: TomTomService,
    ):
        self.route_repository = route_repository
        self.route_leg_congestion_check_repository = route_leg_congestion_check_repository
        self.node_repository = node_repository
        self.simulation_repository = simulation_repository
        self.traffic_incident_repository = traffic_incident_repository
        self.tomtom_service = tomtom_service

    def process_running_simulation_arrivals(
        self,
        reference_time: datetime,
        job_id: str | None = None,
    ) -> dict[str, int]:
        start_time = time.time()

        wide_event: dict[str, object] = {
            "event_type": "worker_process_running_simulation_arrivals",
            "job_id": job_id,
            "status": "processing",
        }

        try:
            due_arrivals = self.route_repository.get_due_arrival_events_for_running_simulations(reference_time)

            transitioned_arrivals: list[tuple[DueArrivalEvent, bool]] = []
            for arrival in due_arrivals:
                updated = self.route_repository.mark_route_leg_as_visited(arrival["route_leg_id"])
                if not updated:
                    continue

                if arrival["node_id"] >= 0:
                    self.node_repository.mark_node_as_completed(
                        node_id=arrival["node_id"],
                        courier_id=arrival["courier_id"],
                        completed_at=datetime.now(timezone.utc),
                    )

                has_next_leg = self.route_repository.promote_next_route_leg_to_in_progress(
                    courier_route_id=arrival["courier_route_id"],
                    current_sequence=arrival["sequence"],
                )

                next_route_leg = None
                if has_next_leg:
                    next_route_leg = self.route_repository.get_next_route_leg_after_sequence(
                        courier_route_id=arrival["courier_route_id"],
                        current_sequence=arrival["sequence"],
                    )

                    if next_route_leg is not None:
                        self._process_next_route_leg(arrival, next_route_leg)

                self.simulation_repository.apply_arrival_progress(
                    simulation_id=arrival["simulation_id"],
                    has_next_leg=has_next_leg,
                )
                transitioned_arrivals.append((arrival, has_next_leg))

            emitted_count = 0
            for arrival, has_next_leg in transitioned_arrivals:
                if arrival["node_id"] < 0:
                    continue

                emit_vehicle_arrived_event(
                    simulation_id=arrival["simulation_id"],
                    courier_route_id=arrival["courier_route_id"],
                    courier_id=arrival["courier_id"],
                    node_id=arrival["node_id"],
                    record_log=True,
                )

                if has_next_leg:
                    emit_vehicle_departed_node_event(
                        simulation_id=arrival["simulation_id"],
                        courier_route_id=arrival["courier_route_id"],
                        courier_id=arrival["courier_id"],
                        node_id=arrival["node_id"],
                    )
                else:
                    emit_vehicle_returned_to_depot_event(
                        simulation_id=arrival["simulation_id"],
                        courier_route_id=arrival["courier_route_id"],
                        courier_id=arrival["courier_id"],
                    )
                emitted_count += 1

            wide_event["status"] = "success"
            wide_event["due_arrival_count"] = len(due_arrivals)
            wide_event["transitioned_count"] = len(transitioned_arrivals)
            wide_event["emitted_count"] = emitted_count
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.info(wide_event)

            return {
                "due_arrival_count": len(due_arrivals),
                "transitioned_count": len(transitioned_arrivals),
                "emitted_count": emitted_count,
            }
        except Exception as exc:
            wide_event["status"] = "failed"
            wide_event["error"] = str(exc)
            wide_event["error_type"] = type(exc).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            logger.error(wide_event)
            raise

    def _process_next_route_leg(
        self,
        arrival: DueArrivalEvent,
        next_route_leg: NextRouteLegSnapshot,
    ) -> None:
        route_points = decode_polyline(
            next_route_leg["encoded_polyline"],
            next_route_leg["encoded_polyline_precision"],
        )
        incident_bbox = build_incident_bbox(
            route_points=route_points,
            origin_latitude=next_route_leg["origin_latitude"],
            origin_longitude=next_route_leg["origin_longitude"],
            destination_latitude=next_route_leg["destination_latitude"],
            destination_longitude=next_route_leg["destination_longitude"],
        )
        logger.info(
            {
                "event_type": "congestion_check_started",
                "simulation_id": arrival["simulation_id"],
                "courier_route_id": arrival["courier_route_id"],
                "courier_id": arrival["courier_id"],
                "route_leg_id": next_route_leg["route_leg_id"],
                "sequence": next_route_leg["sequence"],
                "route_point_count": len(route_points),
                "incident_bbox": incident_bbox,
            }
        )

        time.sleep(CONGESTION_CHECK_DELAY_SECONDS)
        incident_details = self.tomtom_service.get_incident_details(incident_bbox)
        incidents = incident_details["incidents"]
        detection_time = datetime.now(timezone.utc)
        stored_incidents_by_tomtom_id: dict[str, TrafficIncident] = {}

        for incident in incidents:
            stored_incident = self.traffic_incident_repository.store_congestion_incident(
                simulation_id=arrival["simulation_id"],
                detected_at=detection_time,
                incident=incident,
            )
            stored_incidents_by_tomtom_id[incident["properties"]["id"]] = stored_incident

        logger.info(
            {
                "event_type": "congestion_check_incidents_received",
                "simulation_id": arrival["simulation_id"],
                "courier_route_id": arrival["courier_route_id"],
                "courier_id": arrival["courier_id"],
                "route_leg_id": next_route_leg["route_leg_id"],
                "sequence": next_route_leg["sequence"],
                "incident_count": len(incidents),
                "incident_details": incidents,
            }
        )

        congestion_incident, incident_match_debugs = self._find_congestion_incident(
            incidents,
            route_points,
            threshold_seconds=settings.TRAFFIC_CONGESTION_THRESHOLD_SECONDS,
        )

        accepted_incident_id: int | None = None
        if congestion_incident is not None:
            incident_properties = congestion_incident["properties"]
            stored_incident = stored_incidents_by_tomtom_id.get(incident_properties["id"])
            accepted_incident_id = stored_incident.id if stored_incident is not None else None

        self.route_leg_congestion_check_repository.store_congestion_check(
            simulation_id=arrival["simulation_id"],
            route_leg_id=next_route_leg["route_leg_id"],
            courier_id=arrival["courier_id"],
            checked_at=detection_time,
            bbox=incident_bbox,
            incidents_found=len(incidents),
            accepted_incident_id=accepted_incident_id,
            match_details={
                "incident_count": len(incidents),
                "accepted_incident_id": accepted_incident_id,
                "congestion_detected": congestion_incident is not None,
                "threshold_seconds": settings.TRAFFIC_CONGESTION_THRESHOLD_SECONDS,
                "incident_match_debugs": incident_match_debugs,
            },
        )

        if congestion_incident is not None:
            incident_properties = congestion_incident["properties"]
            incident_match_debug = next(
                (
                    incident_match_debug
                    for incident_match_debug in incident_match_debugs
                    if incident_match_debug["incident_id"] == incident_properties["id"]
                ),
                None,
            )
            stored_incident = stored_incidents_by_tomtom_id.get(incident_properties["id"])
            traffic_incident_db_id = stored_incident.id if stored_incident is not None else None

            logger.info(
                {
                    "event_type": "congestion_check_valid_incident_found",
                    "simulation_id": arrival["simulation_id"],
                    "courier_route_id": arrival["courier_route_id"],
                    "courier_id": arrival["courier_id"],
                    "route_leg_id": next_route_leg["route_leg_id"],
                    "sequence": next_route_leg["sequence"],
                    "incident_delay_seconds": incident_properties["delay"],
                    "incident_id": incident_properties["id"],
                    "incident_type": congestion_incident["type"],
                    "incident_match_debug": incident_match_debug,
                    "incident_match_debugs": incident_match_debugs,
                    "traffic_incident_db_id": traffic_incident_db_id,
                    "detected_at": detection_time.isoformat(),
                }
            )

            emit_next_route_congestion_detected_event(
                simulation_id=arrival["simulation_id"],
                courier_route_id=arrival["courier_route_id"],
                courier_id=arrival["courier_id"],
                route_leg_id=next_route_leg["route_leg_id"],
                sequence=next_route_leg["sequence"],
                traffic_delay_in_seconds=incident_properties["delay"],
                threshold_seconds=settings.TRAFFIC_CONGESTION_THRESHOLD_SECONDS,
                latitude=next_route_leg["destination_latitude"],
                longitude=next_route_leg["destination_longitude"],
            )
        else:
            logger.info(
                {
                    "event_type": "congestion_check_no_valid_incident",
                    "simulation_id": arrival["simulation_id"],
                    "courier_route_id": arrival["courier_route_id"],
                    "courier_id": arrival["courier_id"],
                    "route_leg_id": next_route_leg["route_leg_id"],
                    "sequence": next_route_leg["sequence"],
                    "threshold_seconds": settings.TRAFFIC_CONGESTION_THRESHOLD_SECONDS,
                    "incident_match_debugs": incident_match_debugs,
                }
            )

    def _build_incident_match_debug(
        self,
        incident: IncidentFeature,
        route_points: list[tuple[float, float]],
        threshold_seconds: int,
        overlap_threshold_ratio: float = 0.20,
        proximity_threshold_m: float = 30.0,
    ) -> dict[str, object]:
        incident_properties = incident["properties"]
        incident_points = build_coordinate_points(incident["geometry"]["coordinates"])
        is_valid_congestion, overlap_ratio, route_intersects = incident_matches_route(
            route_points=route_points,
            incident_points=incident_points,
            overlap_threshold_ratio=overlap_threshold_ratio,
            proximity_threshold_m=proximity_threshold_m,
        )

        rejected_reasons: list[str] = []
        if incident_properties["delay"] <= threshold_seconds:
            rejected_reasons.append("delay_below_threshold")
        if not route_intersects and overlap_ratio < overlap_threshold_ratio:
            rejected_reasons.append("insufficient_route_overlap")

        return {
            "incident_id": incident_properties["id"],
            "incident_delay_seconds": incident_properties["delay"],
            "route_point_count": len(route_points),
            "incident_point_count": len(incident_points),
            "route_intersects": route_intersects,
            "overlap_ratio": overlap_ratio,
            "overlap_threshold_ratio": overlap_threshold_ratio,
            "proximity_threshold_m": proximity_threshold_m,
            "delay_threshold_seconds": threshold_seconds,
            "is_valid_congestion": is_valid_congestion,
            "rejected_reasons": rejected_reasons,
        }

    def _find_congestion_incident(
        self,
        incidents: Sequence[IncidentFeature],
        route_points: list[tuple[float, float]],
        threshold_seconds: int = 420,
    ) -> tuple[IncidentFeature | None, list[dict[str, object]]]:
        congested_incidents: list[IncidentFeature] = []
        incident_match_debugs: list[dict[str, object]] = []

        for incident in incidents:
            incident_match_debug = self._build_incident_match_debug(
                incident=incident,
                route_points=route_points,
                threshold_seconds=threshold_seconds,
            )
            incident_match_debugs.append(incident_match_debug)

            if not incident_match_debug["is_valid_congestion"]:
                continue

            congested_incidents.append(incident)

        if not congested_incidents:
            return None, incident_match_debugs

        return max(congested_incidents, key=lambda incident: incident["properties"]["delay"]), incident_match_debugs