
from typing import Any

from sqlalchemy.orm import Session
from app.models.simulation import Simulation, SimulationStatusEnum
from app.lib.logging.logging import get_logger

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
    
    async def update_simulation_status(self, simulation_id: str, status: SimulationStatusEnum) -> Simulation | None:
        simulation = self.db.query(Simulation).filter(Simulation.id == simulation_id).first()
        if not simulation:
            return None
        simulation.status = status
        self.db.commit()
        self.db.refresh(simulation)
        return simulation

    async def update_simulation_fields(self, simulation_id: str, fields: dict[str, Any]) -> Simulation | None:
        simulation = self.db.query(Simulation).filter(Simulation.id == simulation_id).first()
        if not simulation:
            return None

        for key, value in fields.items():
            if hasattr(simulation, key):
                setattr(simulation, key, value)

        self.db.commit()
        self.db.refresh(simulation)
        return simulation

    def apply_arrival_progress(self, simulation_id: str, has_next_leg: bool) -> Simulation | None:
        simulation = self.db.query(Simulation).filter(Simulation.id == simulation_id).first()
        if not simulation:
            return None

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