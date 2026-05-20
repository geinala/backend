import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, Boolean, ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.lib.db import Base

if TYPE_CHECKING:
    from app.models.solution import Solution


class Courier(Base):
    __tablename__ = 'couriers'
    
    id: Mapped[int] = mapped_column (Integer, primary_key=True)
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('simulations.id'), nullable=False)
    name: Mapped[str] = mapped_column(String    , nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    solutions: Mapped[list["Solution"]] = relationship("Solution", back_populates="courier")