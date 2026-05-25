from datetime import datetime

from pydantic import BaseModel

from app.models.matrix import MatrixBatchStatusEnum


class CreateMatrixBatchData(BaseModel):
    simulation_id: str
    origin_start_index: int
    origin_end_index: int
    destination_start_index: int
    destination_end_index: int
    tomtom_job_id: str
    status: MatrixBatchStatusEnum = MatrixBatchStatusEnum.submitted


class UpdateMatrixBatchStatusData(BaseModel):
    status: MatrixBatchStatusEnum
    completed_at: datetime | None = None


class CreateMatrixResultData(BaseModel):
    simulation_id: str
    origin_index: int
    destination_index: int
    length_in_meters: int
    travel_time_in_seconds: int
    traffic_delay_in_seconds: int
    matrix_batch_id: int
