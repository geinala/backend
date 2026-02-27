from typing import TypedDict

from pydantic import BaseModel
from sqlalchemy import UUID, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column

Base = declarative_base()

class Node(Base):
    __tablename__ = 'nodes'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    simulation_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    demand: Mapped[float] = mapped_column(Float, nullable=False)
    is_depot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    details = relationship("NodeDetail", back_populates="node", cascade="all, delete-orphan")
    
class NodeDetail(Base):
    __tablename__ = 'node_details'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey('nodes.id'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)
    district: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    
    node = relationship("Node", back_populates="details")
    
class NodeDetailCreate(BaseModel):
    name: str
    address: str
    city: str
    district: str
    weight: float
    
class GroupedNodeData(TypedDict):
    latitude: str
    longitude: str
    total_demand: float
    details: list[NodeDetailCreate]