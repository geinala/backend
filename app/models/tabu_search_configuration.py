import uuid
from datetime import datetime

from sqlalchemy import Float, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class TabuSearchConfiguration(Base):
    __tablename__ = "tabu_search_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    it_max_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    tab_tenure_divider: Mapped[float] = mapped_column(Float, nullable=False)
    it_cons_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    it_div_divider: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

