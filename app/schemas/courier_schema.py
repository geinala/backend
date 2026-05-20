import uuid
from pydantic import BaseModel

class CreateCourier(BaseModel):
    simulation_id: uuid.UUID
    name: str
    is_active: bool = True