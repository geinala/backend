
from typing import Any

from sqlalchemy.orm import Session
from app.models.simulation import Simulation, SimulationStatusEnum
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

class SimulationRepository:
    def __init__(self, db: Session): 
        self.db = db
        
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