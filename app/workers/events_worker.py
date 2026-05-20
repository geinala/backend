from app.lib.logging.logging import get_logger
from app.services.realtime_event_service import publish_realtime_event

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


def emit_vehicle_arrived_event(simulation_id: str, courier_id: int, node_id: int) -> None:
    publish_realtime_event(
        "VEHICLE_ARRIVED",
        {
            "simulationId": simulation_id,
            "courierId": courier_id,
            "nodeId": node_id,
        },
        simulation_id=simulation_id,
    )

    logger.info(
        {
            "event_type": "vehicle_arrived_emitted",
            "simulation_id": simulation_id,
            "courier_id": courier_id,
            "node_id": node_id,
        }
    )