from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    func,
    Boolean,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.lib.db import Base

class AlgorithmConfig(Base):
    __tablename__ = "algorithm_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # it_max = multiplier * n_c
    it_max_multiplier: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")

    # tab_tenure = n_c / divider
    tab_tenure_divider: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")

    # it_cons = multiplier * n_c
    it_cons_multiplier: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    # it_div = n_c / divider
    it_div_divider: Mapped[int] = mapped_column(Integer, nullable=False, default=5,server_default="5")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


