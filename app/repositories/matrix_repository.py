from sqlalchemy.orm import Session

from app.models.matrix import MatrixResult, MatrixTypeEnum
from app.schemas.matrix_schema import MatrixResultInsert

class MatrixRepository:
    def __init__(self, db: Session):
        self.db = db
        
    async def create_matrix_result(self, data: MatrixResultInsert):
        matrix_data = data.model_dump()
        
        db_matrix_result = MatrixResult(**matrix_data)
        
        self.db.add(db_matrix_result)
        self.db.commit()
        
        self.db.refresh(db_matrix_result)
        
        return db_matrix_result
    
    async def bulk_create_matrix_results(self, data_list: list[MatrixResultInsert]):
        db_objects = [MatrixResult(**data.model_dump()) for data in data_list]
        self.db.add_all(db_objects)
        self.db.commit()
        
    async def get_latest_matrix_stage(self, simulation_id: str, courier_id: int, matrix_type: MatrixTypeEnum) -> int | None:
        result = self.db.query(MatrixResult).filter_by(
            simulation_id=simulation_id,
            courier_id=courier_id,
            matrix_type=matrix_type
        ).order_by(MatrixResult.matrix_stage.desc()).first()
        
        return result.matrix_stage if result else None