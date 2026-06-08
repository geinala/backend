from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.lib.db import Base

class TuningExperimentRun(Base):
    __tablename__ = "tuning_experiment_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tuning_experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tuning_experiments.id", ondelete="CASCADE"), nullable=False
    )
    
    # Hyperparameters tested
    it_max: Mapped[int] = mapped_column(Integer, nullable=False)
    tab_tenure: Mapped[int] = mapped_column(Integer, nullable=False)
    it_cons: Mapped[int] = mapped_column(Integer, nullable=False)
    it_div: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Metrics obtained
    fitness_score: Mapped[float] = mapped_column(Float, nullable=False)
    execution_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    convergence_iteration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)