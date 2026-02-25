from pydantic import BaseModel, Field

class SimulationIdRequestDTO(BaseModel):
    simulation_id: str = Field(..., description="ID of the simulation")