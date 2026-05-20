from typing import TypedDict

from pydantic import BaseModel

class NodeDetailCreate(BaseModel):
    name: str
    address: str
    city: str
    weight: float
    
class GroupedNodeData(TypedDict):
    latitude: float
    longitude: float
    total_demand: float
    matrix_index: int
    details: list[NodeDetailCreate]