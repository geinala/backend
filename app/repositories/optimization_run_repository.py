from sqlalchemy import func
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
                run_type=optimization_run.run_type,
                algorithm=optimization_run.algorithm,
                trigger_type=optimization_run.trigger_type,
                total_distance_in_meters=optimization_run.total_distance_in_meters,
                total_travel_time_in_seconds=optimization_run.total_travel_time_in_seconds,
                computation_time_in_ms=optimization_run.computation_time_in_ms,
                total_nodes_explored=optimization_run.total_nodes_explored,
                triggered_at=optimization_run.triggered_at,
                congestion_check_id=optimization_run.congestion_check_id,
                before_total_distance_in_meters=optimization_run.before_total_distance_in_meters,
                before_total_travel_time_in_seconds=optimization_run.before_total_travel_time_in_seconds,
                courier_id=optimization_run.courier_id,
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
        
    def get_latest_total_times_per_algorithm(
        self, simulation_id: str, courier_id: int
    ) -> dict[str, int]:
        
        subq = (
            self.db.query(
                OptimizationRun.algorithm,
                func.max(OptimizationRun.id).label("max_id"),
            )
            .filter(
                OptimizationRun.simulation_id == simulation_id,
                OptimizationRun.courier_id == courier_id,
                OptimizationRun.algorithm.in_(["greedy", "tabu_search"]),
                OptimizationRun.run_type.in_(
                    ["initial", "duration_update", "reoptimization", "baseline_tracking"]
                ),
            )
            .group_by(OptimizationRun.algorithm)
            .subquery()
        )
    
        rows = (
            self.db.query(
                OptimizationRun.algorithm,
                OptimizationRun.total_travel_time_in_seconds,
            )
            .join(subq, OptimizationRun.id == subq.c.max_id)
            .all()
        )
    
        return {row.algorithm: int(row.total_travel_time_in_seconds) for row in rows}