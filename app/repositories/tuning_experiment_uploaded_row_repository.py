from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.models.tuning_experiment_uploaded_row import TuningExperimentUploadedRow
from app.schemas.tuning_experiment_uploaded_row_schema import CreateTuningExperimentUploadedRowSchema, UpdateTuningExperimentUploadedRowSchema, UpdateGeocodedTuningExperimentUploadedRowSchema


class TuningExperimentUploadedRowRepository:
    def __init__(self, db: Session):
        self.db = db

    async def insert_uploaded_rows(self, rows: list[CreateTuningExperimentUploadedRowSchema]) -> None:
        row_objects: list[dict[str, object]] = []

        for row in rows:
            row_objects.append(row.model_dump())

        try:
            self.db.execute(TuningExperimentUploadedRow.__table__.insert(), row_objects)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    async def get_uploaded_rows_by_tuning_experiment_id(self, tuning_experiment_id: str) -> list[TuningExperimentUploadedRow]:
        return (
            self.db.query(TuningExperimentUploadedRow)
            .filter(TuningExperimentUploadedRow.tuning_experiment_id == tuning_experiment_id)
            .order_by(TuningExperimentUploadedRow.id.asc())
            .all()
        )
        
    async def get_uploaded_rows_by_tuning_experiment_id_and_resolution_status(
        self, tuning_experiment_id: str
    ) -> list[TuningExperimentUploadedRow]:
        return (
            self.db.query(TuningExperimentUploadedRow)
            .filter(
                TuningExperimentUploadedRow.tuning_experiment_id == tuning_experiment_id,
            )
            .order_by(TuningExperimentUploadedRow.id.asc())
            .all()
        )

    async def update_cleaned_rows(
        self,
        cleaned_rows: list[UpdateTuningExperimentUploadedRowSchema],
    ) -> None:
        if not cleaned_rows:
            return

        try:
            self.db.bulk_update_mappings(
                inspect(TuningExperimentUploadedRow),
                [
                    row.model_dump(exclude_unset=True)
                    for row in cleaned_rows
                ],
            )
            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

    async def update_geocoded_rows(
        self,
        updated_rows: list[UpdateGeocodedTuningExperimentUploadedRowSchema],
    ) -> None:
        if not updated_rows:
            return

        try:
            self.db.bulk_update_mappings(
                inspect(TuningExperimentUploadedRow),
                [
                    row.model_dump(exclude_unset=True)
                    for row in updated_rows
                ],
            )
            self.db.commit()

        except Exception:
            self.db.rollback()
            raise
