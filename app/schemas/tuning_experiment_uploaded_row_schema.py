from datetime import datetime

from pydantic import BaseModel


class TuningExperimentUploadedRowBaseSchema(BaseModel):
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
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None


class CreateTuningExperimentUploadedRowSchema(
    TuningExperimentUploadedRowBaseSchema
):
    tuning_experiment_id: str
    created_at: datetime


class UpdateTuningExperimentUploadedRowSchema(BaseModel):
    id: int

    normalized_address: str | None = None
    suggested_address: str | None = None
    final_address: str | None = None
    
class UpdateGeocodedTuningExperimentUploadedRowSchema(BaseModel):
    id: int

    latitude: float | None = None
    longitude: float | None = None
    geocode_score: float | None = None
    geocode_provider: str | None = None
    geocode_response: str | None = None
