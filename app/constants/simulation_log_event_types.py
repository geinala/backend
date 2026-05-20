"""Centralized event type constants used across the application."""

SIMULATION_CREATED = "simulation_created"
MATRIX_GENERATION_STARTED = "matrix_generation_started"
MATRIX_GENERATION_COMPLETED = "matrix_generation_completed"
MATRIX_RESULTS_PROCESSING_STARTED = "matrix_results_processing_started"
MATRIX_RESULTS_PROCESSING_COMPLETED = "matrix_results_processing_completed"
OPTIMIZATION_STARTED = "optimization_started"
OPTIMIZATION_COMPLETED = "optimization_completed"
ROUTE_GENERATION_STARTED = "route_generation_started"
INITIAL_ROUTE_GENERATED = "initial_route_generated"
SIMULATION_STARTED = "simulation_started"
SIMULATION_COMPLETED = "simulation_completed"
SIMULATION_FAILED = "simulation_failed"
VEHICLE_DEPARTED_DEPOT = "vehicle_departed_depot"
VEHICLE_ARRIVED_AT_NODE = "vehicle_arrived_at_node"
VEHICLE_DEPARTED_NODE = "vehicle_departed_node"
VEHICLE_RETURNED_TO_DEPOT = "vehicle_returned_to_depot"
INCIDENT_DETECTED = "incident_detected"
REOPTIMIZATION_TRIGGERED = "reoptimization_triggered"
ROUTE_REOPTIMIZED = "route_reoptimized"

__all__ = [
    "SIMULATION_CREATED",
    "MATRIX_GENERATION_STARTED",
    "MATRIX_GENERATION_COMPLETED",
    "MATRIX_RESULTS_PROCESSING_STARTED",
    "MATRIX_RESULTS_PROCESSING_COMPLETED",
    "OPTIMIZATION_STARTED",
    "OPTIMIZATION_COMPLETED",
    "ROUTE_GENERATION_STARTED",
    "INITIAL_ROUTE_GENERATED",
    "SIMULATION_STARTED",
    "SIMULATION_COMPLETED",
    "SIMULATION_FAILED",
    "VEHICLE_DEPARTED_DEPOT",
    "VEHICLE_ARRIVED_AT_NODE",
    "VEHICLE_DEPARTED_NODE",
    "VEHICLE_RETURNED_TO_DEPOT",
    "INCIDENT_DETECTED",
    "REOPTIMIZATION_TRIGGERED",
    "ROUTE_REOPTIMIZED",
]
