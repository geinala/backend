from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel
from uuid import UUID

class NodeDetailBase(BaseModel):
    name: str
    address: str
    city: str
    weight: float
    
class GroupedNodeData(TypedDict):
    latitude: float
    longitude: float
    total_demand: float
    matrix_index: int
    details: list[NodeDetailBase]


class NodeDetailCreate(NodeDetailBase):
    pass


class NodeDetailUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    weight: float | None = None


class NodeBase(BaseModel):
    simulation_id: UUID | None = None
    courier_id: int | None = None
    matrix_index: int
    latitude: float
    longitude: float
    demand: float

class NodeCreate(NodeBase):
    details: list[NodeDetailCreate] = []


class NodeUpdate(BaseModel):
    simulation_id: UUID | None = None
    courier_id: int | None = None
    matrix_index: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    demand: float | None = None
    is_completed: bool | None = None
    completed_at: datetime | None = None
    completed_by: int | None = None
    details: list[NodeDetailUpdate] | None = None