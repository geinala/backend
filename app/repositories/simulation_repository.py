
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from app.models.simulation import Simulation, SimulationStatusEnum
from app.lib.logging.logging import get_logger
from app.models.simulation_job import SimulationJob
from app.schemas.simulation_schema import UpdateSimulationSchema

logger = get_logger(__name__)

class SimulationRepository:
    def __init__(self, db: Session): 
        self.db = db

    def get_running_simulations(self) -> list[Simulation]:
        return (
            self.db.query(Simulation)
            .filter(Simulation.status == SimulationStatusEnum.running)
            .order_by(Simulation.started_at.asc().nullslast(), Simulation.created_at.asc())
            .all()
        )
        
    async def get_simulation_by_id(self, simulation_id: str) -> Simulation | None:
        result = self.db.query(Simulation).filter(Simulation.id == simulation_id).first()
        return result
    
    async def get_simulation_by_simulation_job_id(self, simulation_job_id: str) -> Simulation | None:
        result = self.db.query(Simulation).filter(Simulation.simulation_job_id == simulation_job_id).first()
        return result
    
    async def update_simulation_status(self, simulation_id: str, status: SimulationStatusEnum) -> Simulation | None:
        simulation = self.db.query(Simulation).filter(Simulation.id == simulation_id).first()
        if not simulation:
            return None

        if status == SimulationStatusEnum.running and simulation.started_at is None:
            simulation.started_at = datetime.now(timezone.utc)

        simulation.status = status
        self.db.commit()
        self.db.refresh(simulation)
        return simulation

    async def update_simulation(self, simulation_id: str, update_data: UpdateSimulationSchema) -> Simulation | None:
        simulation = (
            self.db.query(Simulation)
            .filter(Simulation.id == simulation_id)
            .first()
        )

        if not simulation:
            return None

        update_fields = update_data.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        for field, value in update_fields.items():
            setattr(simulation, field, value)

        self.db.commit()
        self.db.refresh(simulation)

        return simulation

    def apply_arrival_progress(self, simulation_id: str, has_next_leg: bool, is_baseline: bool = False, is_real_node: bool = True) -> Simulation | None:
        simulation = self.db.query(Simulation).filter(Simulation.id == simulation_id).first()
        if not simulation:
            return None

        if not is_baseline:
            if is_real_node:
                simulation.total_completed_nodes += 1

            if not has_next_leg:
                simulation.total_active_couriers = max(simulation.total_active_couriers - 1, 0)

        if simulation.total_active_couriers == 0:
            simulation.status = SimulationStatusEnum.completed
            if simulation.completed_at is None:
                from datetime import datetime, timezone

                simulation.completed_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(simulation)
        return simulation
    
    async def create_simulation_from_simulation_job(
        self,
        simulation_job_id: str,
    ) -> Simulation | None:
        simulation_job = (
            self.db.query(SimulationJob)
            .filter(SimulationJob.id == simulation_job_id)
            .first()
        )

        if not simulation_job:
            return None

        simulation = Simulation(
            id=simulation_job.id,
            status="optimizing",
            simulation_job_id=simulation_job.id,
            user_id=simulation_job.user_id,
            title=simulation_job.title,
            depot_location_address=simulation_job.depot_location_address,
            depot_location_latitude=simulation_job.depot_location_latitude,
            depot_location_longitude=simulation_job.depot_location_longitude,
            started_at=simulation_job.started_at,
            depot_id=simulation_job.depot_id,
            is_with_adaptive_parameters=simulation_job.is_with_adaptive_parameters,
        )

        self.db.add(simulation)
        self.db.commit()
        self.db.refresh(simulation)

        return simulation