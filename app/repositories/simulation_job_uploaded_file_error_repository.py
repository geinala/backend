from sqlalchemy.orm import Session

from app.models.simulation_job_uploaded_file_error import SimulationJobUploadedFileError
from app.schemas.simulation_job_uploaded_file_error_schema import SimulationJobUploadedFileErrorCreate

class SimulationJobUploadedFileErrorRepository:
    def __init__(self, db: Session): 
        self.db = db
        
    async def insert_uploaded_file_errors(self, errors: list[SimulationJobUploadedFileErrorCreate]):
        try:
            error_objects = [error.model_dump() for error in errors]
            self.db.execute(SimulationJobUploadedFileError.__table__.insert(), error_objects)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        