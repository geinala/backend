from pydantic import BaseModel
from datetime import datetime

    
class SimulationJobUploadedFileErrorCreate(BaseModel):
    simulation_job_id: str
    row_number: int
    error_message: str
    field_name: str
    invalid_value: str
    created_at: datetime
    
    class Config:
        from_attributes = True