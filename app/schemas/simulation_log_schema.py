from uuid import UUID
from pydantic import BaseModel


class SimulationLogBase(BaseModel):
    simulation_id: UUID
    courier_route_id: int | None = None
    courier_id: int | None = None
    log_level: str
    event_type: str
    title: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    log_metadata: str | None = None


class SimulationLogCreate(SimulationLogBase):
    pass