

from pydantic import BaseModel
from datetime import datetime

class CreateSimulationUploadedRowSchema(BaseModel):
    simulation_job_id: str
    nosi: str | None = None
    courier: str | None = None
    customer_name: str | None = None
    address: str | None = None
    city: str | None = None
    weight: float | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    error_details: str | None = None
    created_at: datetime
    
    class Config:
        from_attributes = True