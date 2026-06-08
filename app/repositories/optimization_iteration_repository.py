from sqlalchemy.orm import Session

from app.models.optimization_iteration import OptimizationIteration
from app.schemas.optimization_iteration_schema import CreateOptimizationIterationSchema

class OptimizationIterationRepository:
    def __init__(self, db: Session):
        self.db = db
        
    async def bulk_insert_optimization_iterations(
        self, 
        optimization_iterations: list[CreateOptimizationIterationSchema]
    ):
        optimization_iteration_objects = [
            OptimizationIteration(**iteration.model_dump())
            for iteration in optimization_iterations
        ]
        
        self.db.add_all(optimization_iteration_objects)
        
        self.db.commit()