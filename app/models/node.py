from datetime import datetime
import uuid

from sqlalchemy import UUID, DateTime, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.lib.db import Base

class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    simulation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulations.id"),
        nullable=True,
    )
    courier_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("couriers.id"),
        nullable=True,
        index=True,
    )
    
    matrix_index: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    is_completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("couriers.id"),
        nullable=True,        
        index=True,
    )
    demand: Mapped[float] = mapped_column(Float, nullable=False)

    details = relationship(
        "NodeDetail",
        back_populates="node",
        cascade="all, delete-orphan"
    )


class NodeDetail(Base):
    __tablename__ = "node_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nodes.id"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)

    node = relationship("Node", back_populates="details")
