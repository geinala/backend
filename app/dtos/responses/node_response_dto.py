from pydantic import BaseModel

class NodeResponseDTO(BaseModel):
    id: int
    simulation_id: str
    latitude: float
    longitude: float
    demand: float
    details: list["NodeDetailDTO"] | None

class NodeDetailDTO(BaseModel):
    name: str
    address: str
    city: str
    district: str
    weight: float