import json
from typing import Mapping, Any

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.constants.simulation_log_event_types import (
    INCIDENT_DETECTED,
    VEHICLE_ARRIVED_AT_NODE,
    VEHICLE_DEPARTED_DEPOT,
    VEHICLE_DEPARTED_NODE,
    VEHICLE_RETURNED_TO_DEPOT,
)
from app.lib.logging.logging import get_logger
from app.schemas.simulation_log_schema import CreateSimulationLog
from app.services.job_service import enqueue_job
from app.services.realtime_event_service import publish_realtime_event
from app.workers.log_worker import create_simulation_log

logger = get_logger(__name__)

def emit_route_initialized_event(simulation_id: str, total_arrival_events: int) -> None:
    publish_realtime_event(
        "ROUTE_INITIALIZED",
        {
            "simulationId": simulation_id,
            "totalArrivalEvents": total_arrival_events,
        },
        simulation_id=simulation_id,
    )

    logger.info(
        {
            "event_type": "route_initialized_emitted",
            "simulation_id": simulation_id,
            "total_arrival_events": total_arrival_events,
        }
    )


def emit_vehicle_departed_depot_event(
    simulation_id: str,
    courier_route_id: int,
    courier_id: int,
) -> None:
    _enqueue_vehicle_simulation_log(
        simulation_id=simulation_id,
        event_type=VEHICLE_DEPARTED_DEPOT,
        title=f"Vehicle departed depot for courier route {courier_route_id}",
        description=f"Vehicle has departed from the depot for courier route {courier_route_id}.",
        courier_route_id=courier_route_id,
        courier_id=courier_id,
    )

    logger.info(
        {
            "event_type": "vehicle_departed_depot_emitted",
            "simulation_id": simulation_id,
            "courier_route_id": courier_route_id,
            "courier_id": courier_id,
        }
    )


def emit_vehicle_arrived_event(
    simulation_id: str,
    courier_route_id: int,
    courier_id: int,
    node_id: int,
    record_log: bool = False,
) -> None:
    publish_realtime_event(
        "VEHICLE_ARRIVED",
        {
            "simulationId": simulation_id,
            "courierRouteId": courier_route_id,
            "courierId": courier_id,
            "nodeId": node_id,
        },
        simulation_id=simulation_id,
    )

    if record_log:
        _enqueue_vehicle_simulation_log(
            simulation_id=simulation_id,
            event_type=VEHICLE_ARRIVED_AT_NODE,
            title=f"Vehicle arrived at node {node_id}",
            description=f"Vehicle has arrived at node {node_id} for courier route {courier_route_id}.",
            courier_route_id=courier_route_id,
            courier_id=courier_id,
        )

    logger.info(
        {
            "event_type": "vehicle_arrived_emitted",
            "simulation_id": simulation_id,
            "courier_route_id": courier_route_id,
            "courier_id": courier_id,
            "node_id": node_id,
        }
    )


def emit_next_route_congestion_detected_event(
    simulation_id: str,
    courier_route_id: int,
    courier_id: int,
    route_leg_id: int,
    sequence: int,
    traffic_delay_in_seconds: int,
    threshold_seconds: int,
    latitude: float,
    longitude: float,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    delay_minutes = traffic_delay_in_seconds / 60
    threshold_minutes = threshold_seconds / 60

    _enqueue_vehicle_simulation_log(
        simulation_id=simulation_id,
        event_type=INCIDENT_DETECTED,
        title=f"Traffic delay detected for courier route {courier_route_id}",
        description=(
            f"Next route leg {route_leg_id} has a traffic delay of {traffic_delay_in_seconds} seconds "
            f"({delay_minutes:.1f} minutes), which exceeds the {threshold_minutes:.1f}-minute threshold."
        ),
        courier_route_id=courier_route_id,
        courier_id=courier_id,
    )

    log_metadata: dict[str, Any] = {
        "threshold_seconds": threshold_seconds,
        "traffic_delay_in_seconds": traffic_delay_in_seconds,
        "traffic_delay_in_minutes": round(delay_minutes, 2),
        "route_leg_id": route_leg_id,
        "sequence": sequence,
    }

    # `update` accepts a Mapping; use empty dict when metadata is None
    log_metadata.update(metadata or {})

    logger.warning(
        {
            "event_type": "next_route_congestion_detected",
            "simulation_id": simulation_id,
            "courier_route_id": courier_route_id,
            "courier_id": courier_id,
            "route_leg_id": route_leg_id,
            "sequence": sequence,
            "traffic_delay_in_seconds": traffic_delay_in_seconds,
            "threshold_seconds": threshold_seconds,
            "latitude": latitude,
            "longitude": longitude,
            "metadata": json.dumps(log_metadata),
        }
    )


def emit_vehicle_departed_node_event(
    simulation_id: str,
    courier_route_id: int,
    courier_id: int,
    node_id: int,
) -> None:
    _enqueue_vehicle_simulation_log(
        simulation_id=simulation_id,
        event_type=VEHICLE_DEPARTED_NODE,
        title=f"Vehicle departed node {node_id}",
        description=f"Vehicle has departed from node {node_id} for courier route {courier_route_id}.",
        courier_route_id=courier_route_id,
        courier_id=courier_id,
    )

    logger.info(
        {
            "event_type": "vehicle_departed_node_emitted",
            "simulation_id": simulation_id,
            "courier_route_id": courier_route_id,
            "courier_id": courier_id,
            "node_id": node_id,
        }
    )


def emit_vehicle_returned_to_depot_event(
    simulation_id: str,
    courier_route_id: int,
    courier_id: int,
) -> None:
    _enqueue_vehicle_simulation_log(
        simulation_id=simulation_id,
        event_type=VEHICLE_RETURNED_TO_DEPOT,
        title=f"Vehicle returned to depot for courier route {courier_route_id}",
        description=f"Vehicle has returned to the depot for courier route {courier_route_id}.",
        courier_route_id=courier_route_id,
        courier_id=courier_id,
    )

    logger.info(
        {
            "event_type": "vehicle_returned_to_depot_emitted",
            "simulation_id": simulation_id,
            "courier_route_id": courier_route_id,
            "courier_id": courier_id,
        }
    )
    
def _enqueue_vehicle_simulation_log(
    simulation_id: str,
    event_type: str,
    title: str,
    description: str,
    courier_route_id: int,
    courier_id: int,
) -> None:
    enqueue_job(
        create_simulation_log,
        job_type=JobType.LIGHT,
        job_prefix=JOB_PREFIXES_ENUM.SIMULATION_LOG,
        log_payload=CreateSimulationLog(
            simulation_id=simulation_id,
            courier_route_id=courier_route_id,
            courier_id=courier_id,
            event_type=event_type,
            title=title,
            description=description,
        ),
    )
