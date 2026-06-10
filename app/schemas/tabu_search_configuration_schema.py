import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TabuSearchConfigurationBase(BaseModel):
    it_max_multiplier: float
    tab_tenure_divider: float
    it_cons_multiplier: float
    it_div_divider: float
    is_active: bool = True


class TabuSearchConfigurationCreate(TabuSearchConfigurationBase):
    pass


class TabuSearchConfigurationUpdate(BaseModel):
    it_max_multiplier: Optional[float] = None
    tab_tenure_divider: Optional[float] = None
    it_cons_multiplier: Optional[float] = None
    it_div_divider: Optional[float] = None
    is_active: Optional[bool] = None


class TabuSearchConfigurationResponse(TabuSearchConfigurationBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)