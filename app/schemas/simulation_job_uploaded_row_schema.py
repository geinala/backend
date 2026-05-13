

from pydantic import BaseModel
from datetime import datetime

from app.models.simulation_uploaded_row import ResolutionStatusEnum

class CreateSimulationUploadedRowSchema(BaseModel):
    simulation_job_id: str
    nosi: str | None = None
    courier: str | None = None
    customer_name: str | None = None
    address: str | None = None
    normalized_address: str | None = None
    suggested_address: str | None = None
    final_address: str | None = None
    city: str | None = None
    weight: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    geocode_score: float | None = None
    geocode_provider: str | None = None
    geocode_response: str | None = None
    resolution_status: ResolutionStatusEnum = ResolutionStatusEnum.pending
    resolution_source: str | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    error_details: str | None = None
    created_at: datetime
    
    class Config:
        from_attributes = True