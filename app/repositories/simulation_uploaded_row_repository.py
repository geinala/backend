from sqlalchemy.orm import Session

from app.models.simulation_uploaded_row import SimulationUploadedRow
from app.schemas.simulation_job_uploaded_row_schema import CreateSimulationUploadedRowSchema


class SimulationUploadedRowRepository:
    def __init__(self, db: Session):
        self.db = db

    async def insert_uploaded_rows(self, rows: list[CreateSimulationUploadedRowSchema]) -> None:
        row_objects: list[dict[str, object]] = []

        for row in rows:
            row_data = row.model_dump()
            row_data["error_details"] = row_data["error_details"] or "[]"
            row_objects.append(row_data)

        try:
            self.db.execute(SimulationUploadedRow.__table__.insert(), row_objects)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise