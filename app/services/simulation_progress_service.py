import json
import time
import re
from datetime import datetime, timezone
from typing import Sequence, cast

from rq import get_current_job
from rq.job import Job

from app.configs.environment_configuration import get_environment_configuration
from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.lib.logging.logging import get_logger
from app.lib.route_geometry import (
    build_coordinate_points,
    build_incident_bbox,
    decode_polyline,
    incident_matches_route,
    route_direction_matches_incident,
)
from app.services.job_service import enqueue_job
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.models.traffic_incident import TrafficIncident
from app.repositories.node_repository import NodeRepository
from app.repositories.route_repository import DueArrivalEvent, NextRouteLegSnapshot, RouteRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.traffic_incident_repository import TrafficIncidentRepository
from app.repositories.route_leg_congestion_check_repository import RouteLegCongestionCheckRepository
from app.schemas.route_leg_congestion_check_schema import CongestionCheckIncidentRow
from app.services.matrix_service import MatrixService
from app.services.tomtom_service import IncidentFeature, TomTomService
from app.workers import dvrp_reoptimization_worker_process_congestion
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
        optimization_run_repository: OptimizationRunRepository,
        simulation_repository: SimulationRepository,
        traffic_incident_repository: TrafficIncidentRepository,
        matrix_service: MatrixService,
        tomtom_service: TomTomService,
    ):
        self.route_repository = route_repository
        self.route_leg_congestion_check_repository = route_leg_congestion_check_repository
        self.node_repository = node_repository
        self.optimization_run_repository = optimization_run_repository
        self.simulation_repository = simulation_repository
        self.traffic_incident_repository = traffic_incident_repository
        self.matrix_service = matrix_service
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
            
            logger.info(f"Due arrivals fetched: {json.dumps(due_arrivals, default=str)}")

            # Menyimpan tuple dengan struktur: (arrival, has_next_leg, reopt_queued)
            transitioned_arrivals: list[tuple[DueArrivalEvent, bool, bool]] = []
            current_job: Job | None = get_current_job()

            for arrival in due_arrivals:
                updated = self.route_repository.mark_route_leg_as_visited(arrival["route_leg_id"], arrival["is_baseline"])
                if not updated:
                    continue

                if arrival["node_id"] >= 0 and not arrival["is_baseline"]:
                    self.node_repository.mark_node_as_completed(
                        node_id=arrival["node_id"],
                        courier_id=arrival["courier_id"],
                        completed_at=datetime.now(timezone.utc),
                    )

                # ==========================================================
                # CEK KEMACETAN DULU SEBELUM KURIR DISURUH JALAN
                # ==========================================================
                next_route_leg = self.route_repository.get_next_route_leg_after_sequence(
                    courier_route_id=arrival["courier_route_id"],
                    current_sequence=arrival["sequence"],
                )
                
                has_next_leg = next_route_leg is not None
                reopt_queued = False

                if has_next_leg and next_route_leg is not None:
                    reopt_queued = self._process_next_route_leg(
                        arrival, 
                        next_route_leg, 
                        current_job=current_job, 
                        traffic_congestion_threshold_seconds=arrival["congestion_delay_threshold_in_seconds"]
                    )

                # HANYA jadikan route leg selanjutnya in-progress jika TIDAK ADA reoptimisasi yang masuk antrean
                if has_next_leg and not reopt_queued:
                    self.route_repository.promote_next_route_leg_to_in_progress(
                        courier_route_id=arrival["courier_route_id"],
                        current_sequence=arrival["sequence"],
                        is_baseline=arrival["is_baseline"],
                    )

                self.simulation_repository.apply_arrival_progress(
                    simulation_id=arrival["simulation_id"],
                    has_next_leg=has_next_leg,
                    is_baseline=arrival["is_baseline"],
                )
                
                transitioned_arrivals.append((arrival, has_next_leg, reopt_queued))

            emitted_count = 0
            for arrival, has_next_leg, reopt_queued in transitioned_arrivals:
                if arrival["node_id"] < 0:
                    continue
                
                if arrival.get("is_baseline", False):
                    continue

                emit_vehicle_arrived_event(
                    simulation_id=arrival["simulation_id"],
                    courier_route_id=arrival["courier_route_id"],
                    courier_id=arrival["courier_id"],
                    node_id=arrival["node_id"],
                    record_log=True,
                )

                if has_next_leg:
                    # TAHAN EVENT KE FRONTEND JIKA REOPTIMISASI MASUK ANTREAN
                    if not reopt_queued:
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
        current_job: Job | None = None,
        traffic_congestion_threshold_seconds: int = settings.TRAFFIC_CONGESTION_THRESHOLD_SECONDS,
    ) -> bool:
        # logger.info(f"TESTING MODE: Force reoptimization for leg {next_route_leg['route_leg_id']}")
        
        # next_next_leg = self.route_repository.get_next_route_leg_after_sequence(
        #     courier_route_id=arrival["courier_route_id"],
        #     current_sequence=next_route_leg["sequence"],
        # )
        # is_last_leg = next_next_leg is None

        # enqueue_job(
        #     dvrp_reoptimization_worker_process_congestion,
        #     job_type=JobType.HEAVY,
        #     job_prefix=JOB_PREFIXES_ENUM.DVRP_REOPTIMIZATION,
        #     depends_on=current_job,
        #     simulation_id=arrival["simulation_id"],
        #     congestion_check_id=None,
        #     route_leg_id=next_route_leg["route_leg_id"],
        #     courier_route_id=arrival["courier_route_id"],
        #     courier_id=arrival["courier_id"],
        #     current_sequence=next_route_leg["sequence"],
        #     delay_seconds=1,
        #     force_duration_update_only=is_last_leg,  # Force duration update only for last leg to speed up testing
        #     is_baseline=arrival["is_baseline"],
        # )
        
        # return True
        
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

        result: tuple[IncidentFeature | list[IncidentFeature] | None, list[dict[str, object]]]
        result = self._find_congestion_incident(
            incidents,
            route_points,
            threshold_seconds=traffic_congestion_threshold_seconds,
        )
        congestion_result, incident_match_debugs = result

        accepted_incident_id: int | None = None
        selected_tomtom_incident_id: str | None = None
        accepted_incident_ids: list[int] = []
        accepted_incidents: list[IncidentFeature] = []
        if congestion_result is not None:
            if isinstance(congestion_result, list):
                accepted_incidents = congestion_result
            else:
                accepted_incidents = [congestion_result]

            selected_incident = max(accepted_incidents, key=lambda inc: inc["properties"]["delay"])
            selected_tomtom_incident_id = selected_incident["properties"]["id"]

            for inc in accepted_incidents:
                incident_properties = inc["properties"]
                stored_incident = stored_incidents_by_tomtom_id.get(incident_properties["id"])
                if stored_incident is not None:
                    accepted_incident_ids.append(stored_incident.id)

            stored_selected_incident = stored_incidents_by_tomtom_id.get(selected_tomtom_incident_id)
            accepted_incident_id = stored_selected_incident.id if stored_selected_incident is not None else None

        congestion_detected = len(accepted_incidents) > 0
        incident_rows, aggregated_delay, selected_traffic_incident_id = self._build_congestion_check_incident_rows(
            incidents=incidents,
            incident_match_debugs=incident_match_debugs,
            stored_incidents_by_tomtom_id=stored_incidents_by_tomtom_id,
        )

        accepted_incident_ids = [
            row["traffic_incident_id"]
            for row in incident_rows
            if row["is_valid_congestion"] and row["traffic_incident_id"] is not None
        ]
        accepted_incident_count = len(accepted_incident_ids)

        if selected_traffic_incident_id is not None:
            accepted_incident_id = selected_traffic_incident_id

        force_duration_update_only = (
            congestion_detected
            and aggregated_delay <= traffic_congestion_threshold_seconds
        )

        congestion_check = self.route_leg_congestion_check_repository.store_congestion_check(
            simulation_id=arrival["simulation_id"],
            route_leg_id=next_route_leg["route_leg_id"],
            courier_id=arrival["courier_id"],
            checked_at=detection_time,
            bbox=incident_bbox,
            incidents_found=len(incidents),
            accepted_incident_count=accepted_incident_count,
            total_delay_in_seconds=aggregated_delay,
        )

        # If research multi-accept mode, persist per-incident association rows
        if incident_rows:
            try:
                self.route_leg_congestion_check_repository.store_congestion_check_incidents(
                    congestion_check.id,
                    incident_rows,
                )
            except Exception:
                # Don't fail the whole worker if persisting association rows fails; log and continue
                logger.exception("Failed storing congestion check incident associations")

        if congestion_detected:
            # Prepare metadata and aggregated values for event/enqueue
            tomtom_ids = [inc["properties"]["id"] for inc in accepted_incidents]
            incident_match_debug = next(
                (
                    imd for imd in incident_match_debugs if imd["incident_id"] == selected_tomtom_incident_id
                ),
                None,
            )

            logger.info(
                {
                    "event_type": "congestion_check_valid_incident_found",
                    "simulation_id": arrival["simulation_id"],
                    "courier_route_id": arrival["courier_route_id"],
                    "courier_id": arrival["courier_id"],
                    "route_leg_id": next_route_leg["route_leg_id"],
                    "sequence": next_route_leg["sequence"],
                    "incident_delay_seconds": [row["delay_in_seconds"] for row in incident_rows if row["is_valid_congestion"]],
                    "incident_ids": tomtom_ids,
                    "incident_type": [inc.get("type") for inc in accepted_incidents],
                    "incident_match_debug": incident_match_debug,
                    "incident_match_debugs": incident_match_debugs,
                    "accepted_incident_db_ids": accepted_incident_ids,
                    "detected_at": detection_time.isoformat(),
                    "total_delay_in_seconds": aggregated_delay,
                    "force_duration_update_only": force_duration_update_only,
                    "resequence_threshold_seconds": traffic_congestion_threshold_seconds,
                }
            )

            emit_next_route_congestion_detected_event(
                simulation_id=arrival["simulation_id"],
                courier_route_id=arrival["courier_route_id"],
                courier_id=arrival["courier_id"],
                route_leg_id=next_route_leg["route_leg_id"],
                sequence=next_route_leg["sequence"],
                traffic_delay_in_seconds=aggregated_delay,
                threshold_seconds=traffic_congestion_threshold_seconds,
                latitude=next_route_leg["destination_latitude"],
                longitude=next_route_leg["destination_longitude"],
                metadata={
                    "multi_accept": settings.TRAFFIC_CONGESTION_MULTI_ACCEPT_MODE,
                    "accepted_tomtom_ids": tomtom_ids,
                    "accepted_db_ids": accepted_incident_ids,
                    "accepted_delays": [row["delay_in_seconds"] for row in incident_rows if row["is_valid_congestion"]],
                    "chosen_tomtom_id": selected_tomtom_incident_id,
                    "chosen_db_id": accepted_incident_id,
                    "total_delay_in_seconds": aggregated_delay,
                    "force_duration_update_only": force_duration_update_only,
                },
            )

            enqueue_job(
                dvrp_reoptimization_worker_process_congestion,
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.DVRP_REOPTIMIZATION,
                depends_on=current_job,
                simulation_id=arrival["simulation_id"],
                congestion_check_id=congestion_check.id,
                route_leg_id=next_route_leg["route_leg_id"],
                courier_route_id=arrival["courier_route_id"],
                courier_id=arrival["courier_id"],
                current_sequence=next_route_leg["sequence"],
                delay_seconds=aggregated_delay,
                force_duration_update_only=force_duration_update_only,
                is_baseline=arrival["is_baseline"],
            )
            return True
        else:
            logger.info(
                {
                    "event_type": "congestion_check_no_valid_incident",
                    "simulation_id": arrival["simulation_id"],
                    "courier_route_id": arrival["courier_route_id"],
                    "courier_id": arrival["courier_id"],
                    "route_leg_id": next_route_leg["route_leg_id"],
                    "sequence": next_route_leg["sequence"],
                    "threshold_seconds": traffic_congestion_threshold_seconds,
                    "incident_match_debugs": incident_match_debugs,
                }
            )
            return False

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
            strict_mode=settings.TRAFFIC_CONGESTION_STRICT_MODE,
        )
        direction_matches = route_direction_matches_incident(
            route_points=route_points,
            incident_points=incident_points,
        )

        rejected_reasons: list[str] = []
        if incident_properties["delay"] <= threshold_seconds:
            rejected_reasons.append("delay_below_threshold")
        if not route_intersects and overlap_ratio < overlap_threshold_ratio:
            rejected_reasons.append("insufficient_route_overlap")
        if overlap_ratio >= overlap_threshold_ratio and not direction_matches:
            rejected_reasons.append("direction_mismatch")

        return {
            "incident_id": incident_properties["id"],
            "incident_delay_seconds": incident_properties["delay"],
            "route_point_count": len(route_points),
            "incident_point_count": len(incident_points),
            "route_intersects": route_intersects,
            "overlap_ratio": overlap_ratio,
            "overlap_threshold_ratio": overlap_threshold_ratio,
            "direction_matches": direction_matches,
            "proximity_threshold_m": proximity_threshold_m,
            "delay_threshold_seconds": threshold_seconds,
            "is_valid_congestion": is_valid_congestion,
            "rejected_reasons": rejected_reasons,
        }

    @staticmethod
    def _normalize_cluster_label(value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.strip().lower()
        normalized_value = normalized_value.replace(".", " ")
        normalized_value = re.sub(r"\b(jl|jln|jalan|street|road|rd|ave|avenue)\b", "", normalized_value)
        normalized_value = re.sub(r"\b(north|south|east|west|utara|selatan|timur|barat)\b", "", normalized_value)
        normalized_value = re.sub(r"[^\w\s-]+", " ", normalized_value)
        normalized_value = re.sub(r"\s+", " ", normalized_value).strip()

        return normalized_value or None

    @staticmethod
    def _build_incident_cluster_key(incident: IncidentFeature) -> str | None:
        properties = incident["properties"]
        candidates = (
            properties.get("from"),
            properties.get("to"),
        )

        for candidate in candidates:
            normalized_label = SimulationProgressService._normalize_cluster_label(candidate)
            if normalized_label:
                return f"road:{normalized_label}"

        coordinates = incident["geometry"].get("coordinates", [])
        if not coordinates:
            return None

        latitudes = [float(point[1]) for point in coordinates]
        longitudes = [float(point[0]) for point in coordinates]
        centroid_latitude = sum(latitudes) / len(latitudes)
        centroid_longitude = sum(longitudes) / len(longitudes)
        return f"geo:{round(centroid_latitude, 3)}:{round(centroid_longitude, 3)}"

    def _build_congestion_check_incident_rows(
        self,
        *,
        incidents: Sequence[IncidentFeature],
        incident_match_debugs: list[dict[str, object]],
        stored_incidents_by_tomtom_id: dict[str, TrafficIncident],
    ) -> tuple[list[CongestionCheckIncidentRow], int, int | None]:
        rows: list[CongestionCheckIncidentRow] = []
        valid_cluster_keys: list[str] = []
        rows_by_cluster_key: dict[str, list[CongestionCheckIncidentRow]] = {}

        for incident, incident_match_debug in zip(incidents, incident_match_debugs):
            tomtom_incident_id = incident["properties"]["id"]
            stored_incident = stored_incidents_by_tomtom_id.get(tomtom_incident_id)
            is_valid_congestion = bool(incident_match_debug["is_valid_congestion"])
            cluster_key = self._build_incident_cluster_key(incident) if is_valid_congestion else None
            overlap_ratio = cast(float | None, incident_match_debug.get("overlap_ratio"))
            rejected_reasons = cast(list[str], incident_match_debug.get("rejected_reasons", []))
            direction_matches = cast(bool | None, incident_match_debug.get("direction_matches"))
            route_point_count = cast(int | None, incident_match_debug.get("route_point_count"))
            incident_point_count = cast(int | None, incident_match_debug.get("incident_point_count"))
            delay_threshold_seconds = cast(int, incident_match_debug["delay_threshold_seconds"])
            overlap_threshold_ratio = cast(float, incident_match_debug["overlap_threshold_ratio"])
            proximity_threshold_m = cast(int, incident_match_debug["proximity_threshold_m"])
            row: CongestionCheckIncidentRow = {
                "traffic_incident_id": stored_incident.id if stored_incident is not None else None,
                "delay_in_seconds": int(incident["properties"]["delay"]),
                "overlap_ratio": overlap_ratio,
                "rejected_reasons": rejected_reasons,
                "route_intersects": bool(incident_match_debug.get("route_intersects", False)),
                "is_valid_congestion": is_valid_congestion,
                "direction_matches": direction_matches,
                "route_point_count": route_point_count,
                "incident_point_count": incident_point_count,
                "cluster_group": None,
                "chosen_for_reopt": False,
                "delay_contribution_in_seconds": 0,
                "delay_threshold_in_seconds": delay_threshold_seconds,
                "overlap_threshold": overlap_threshold_ratio,
                "proximity_threshold_in_meters": proximity_threshold_m,
            }
            rows.append(row)

            if cluster_key is None:
                continue

            if cluster_key not in rows_by_cluster_key:
                valid_cluster_keys.append(cluster_key)
                rows_by_cluster_key[cluster_key] = []

            rows_by_cluster_key[cluster_key].append(row)

        total_delay_in_seconds = 0
        selected_traffic_incident_id: int | None = None
        selected_delay_in_seconds = -1

        for cluster_group, cluster_key in enumerate(valid_cluster_keys, start=1):
            cluster_rows = rows_by_cluster_key[cluster_key]
            winner = max(
                cluster_rows,
                key=lambda row: (
                    int(row["delay_in_seconds"]),
                    bool(row["direction_matches"]),
                    float(row["overlap_ratio"] or 0.0),
                    bool(row["route_intersects"]),
                ),
            )

            for row in cluster_rows:
                row["cluster_group"] = cluster_group

            winner["chosen_for_reopt"] = True
            winner["delay_contribution_in_seconds"] = int(winner["delay_in_seconds"])
            total_delay_in_seconds += int(winner["delay_in_seconds"])

            winner_traffic_incident_id = winner["traffic_incident_id"]
            if winner_traffic_incident_id is not None and int(winner["delay_in_seconds"]) > selected_delay_in_seconds:
                selected_delay_in_seconds = int(winner["delay_in_seconds"])
                selected_traffic_incident_id = winner_traffic_incident_id

        return rows, total_delay_in_seconds, selected_traffic_incident_id

    def _find_congestion_incident(
        self,
        incidents: Sequence[IncidentFeature],
        route_points: list[tuple[float, float]],
        threshold_seconds: int = 420,
    ) -> tuple[IncidentFeature | list[IncidentFeature] | None, list[dict[str, object]]]:
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

        # If multi-accept mode is enabled, return all congested incidents (research mode)
        if settings.TRAFFIC_CONGESTION_MULTI_ACCEPT_MODE:
            return congested_incidents, incident_match_debugs

        # Default behavior: return single incident with max delay
        return max(congested_incidents, key=lambda incident: incident["properties"]["delay"]), incident_match_debugs