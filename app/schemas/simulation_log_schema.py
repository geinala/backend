from pydantic import BaseModel

class CreateSimulationLog(BaseModel):
    simulation_id: str
    courier_route_id: int | None = None
    courier_id: int | None = None
    log_level: str = "INFO"
    event_type: str | None = None
    title: str | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    metadata: str | None = None
    
    class Config:
        from_attributes = True
