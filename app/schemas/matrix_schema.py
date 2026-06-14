import enum
import uuid

from pydantic import BaseModel
from app.models.matrix import MatrixTypeEnum

class MatrixResultBase(BaseModel):
    simulation_id: uuid.UUID | None = None
    courier_id: int
    origin_index: int
    destination_index: int
    length_in_meters: int
    travel_time_in_seconds: int
    matrix_type: MatrixTypeEnum
    matrix_stage: int

class MatrixResultInsert(MatrixResultBase):
    pass