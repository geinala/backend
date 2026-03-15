
from sqlalchemy.orm import Session
from app.models.simulation import Simulation, SimulationStatusEnum, SimulationUploadedFile, SimulationUploadedFileUpdateData
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

class SimulationRepository:
    def __init__(self, db: Session): 
        self.db = db
        
    async def get_simulation_by_id(self, simulation_id: str) -> Simulation | None:
        result = self.db.query(Simulation).filter(Simulation.id == simulation_id).first()
        return result
    
    async def get_simulation_uploaded_file_by_id(self, uploaded_file_id: int):
        result = self.db.query(SimulationUploadedFile).filter(SimulationUploadedFile.id == uploaded_file_id).first()
        return result
    
    async def update_simulation_status(self, simulation_id: str, status: SimulationStatusEnum) -> Simulation | None:
        simulation = self.db.query(Simulation).filter(Simulation.id == simulation_id).first()
        if not simulation:
            return None
        simulation.status = status
        self.db.commit()
        self.db.refresh(simulation)
        return simulation

    async def update_simulation_uploaded_file(self, id: int, uploaded_file: SimulationUploadedFileUpdateData):
        existing_file = await self.get_simulation_uploaded_file_by_id(id)
        
        if not existing_file:
            logger.warning(f"Simulation uploaded file with ID {id} not found for update.")
            raise ValueError(f"Simulation uploaded file with ID {id} not found")
        
        for key, value in uploaded_file.model_dump(exclude_unset=True).items():
            setattr(existing_file, key, value)
        
        self.db.commit()
        self.db.refresh(existing_file)
        return existing_file