from sqlalchemy.orm import Session, class_mapper

from app.models.simulation_uploaded_row import SimulationUploadedRow
from app.schemas.simulation_job_uploaded_row_schema import CreateSimulationUploadedRowSchema


class SimulationUploadedRowRepository:
    def __init__(self, db: Session):
        self.db = db

    async def insert_uploaded_rows(self, rows: list[CreateSimulationUploadedRowSchema]) -> None:
        row_objects: list[dict[str, object]] = []

        for row in rows:
            row_objects.append(row.model_dump())

        try:
            self.db.execute(SimulationUploadedRow.__table__.insert(), row_objects)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    async def get_uploaded_rows_by_simulation_job_id(self, simulation_job_id: str) -> list[SimulationUploadedRow]:
        return (
            self.db.query(SimulationUploadedRow)
            .filter(SimulationUploadedRow.simulation_job_id == simulation_job_id)
            .order_by(SimulationUploadedRow.id.asc())
            .all()
        )
        
    async def get_validated_rows_by_simulation_job_id(self, simulation_job_id: str) -> list[SimulationUploadedRow]:
        return (
            self.db.query(SimulationUploadedRow)
            .filter(
                SimulationUploadedRow.simulation_job_id == simulation_job_id,
                SimulationUploadedRow.is_ignored == False,
                SimulationUploadedRow.latitude.isnot(None),
                SimulationUploadedRow.longitude.isnot(None),
            )
            .order_by(SimulationUploadedRow.id.asc())
            .all()
        )
        
    async def get_uploaded_rows_by_simulation_job_id_and_resolution_status(
        self, simulation_job_id: str, resolution_status: str
    ) -> list[SimulationUploadedRow]:
        return (
            self.db.query(SimulationUploadedRow)
            .filter(
                SimulationUploadedRow.simulation_job_id == simulation_job_id,
                SimulationUploadedRow.resolution_status == resolution_status,
                SimulationUploadedRow.is_ignored == False,
                SimulationUploadedRow.final_address.isnot(None),
                SimulationUploadedRow.suggested_address.isnot(None)
            )
            .order_by(SimulationUploadedRow.id.asc())
            .all()
        )

    async def update_cleaned_rows(
        self,
        cleaned_rows: list[dict[str, object]],
    ) -> None:
        if not cleaned_rows:
            return

        try:
            self.db.bulk_update_mappings(class_mapper(SimulationUploadedRow), cleaned_rows)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    async def update_geocoded_rows(self, updated_rows: list[dict[str, object]]) -> None:
        if not updated_rows:
            return

        try:
            self.db.bulk_update_mappings(class_mapper(SimulationUploadedRow), updated_rows)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
