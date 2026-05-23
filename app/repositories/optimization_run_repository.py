from sqlalchemy.orm import Session

from app.models.optimization_run import OptimizationRun
from app.schemas.optimization_run_schema import CreateOptimizationRun


class OptimizationRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def bulk_insert_optimization_runs(self, optimization_runs: list[CreateOptimizationRun]):
        optimization_run_objects = [
            OptimizationRun(
                simulation_id=optimization_run.simulation_id,
                courier_route_id=optimization_run.courier_route_id,
                traffic_incident_id=optimization_run.traffic_incident_id,
                run_type=optimization_run.run_type,
                algorithm=optimization_run.algorithm,
                trigger_type=optimization_run.trigger_type,
                total_distance_in_meters=optimization_run.total_distance_in_meters,
                total_travel_time_in_seconds=optimization_run.total_travel_time_in_seconds,
                computation_time_in_ms=optimization_run.computation_time_in_ms,
                total_nodes_explored=optimization_run.total_nodes_explored,
                triggered_at=optimization_run.triggered_at,
                before_total_distance_in_meters=optimization_run.before_total_distance_in_meters,
                before_total_travel_time_in_seconds=optimization_run.before_total_travel_time_in_seconds,
                before_computation_time_in_ms=optimization_run.before_computation_time_in_ms,
                before_total_nodes_explored=optimization_run.before_total_nodes_explored,
            )
            for optimization_run in optimization_runs
        ]

        self.db.add_all(optimization_run_objects)

        try:
            self.db.commit()

            for optimization_run in optimization_run_objects:
                self.db.refresh(optimization_run)

            return optimization_run_objects
        except Exception:
            self.db.rollback()
            raise