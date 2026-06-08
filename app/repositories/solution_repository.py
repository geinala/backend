from sqlalchemy.orm import Session

from app.models.solution import Solution
from app.schemas.solution_schema import CreateSolution

class SolutionRepository:
    def __init__(self, db: Session):
        self.db = db
        
    async def bulk_insert_solutions(self, solutions: list[CreateSolution]):
        new_solutions = [
            Solution(**solution.model_dump()) for solution in solutions
        ]
        
        self.db.bulk_save_objects(new_solutions)
        self.db.commit()
        return new_solutions
        
    async def insert_solution(self, solution: CreateSolution):
        new_solution: Solution = Solution(
            **solution.model_dump()
        )
        self.db.add(new_solution)
        self.db.commit()
        self.db.refresh(new_solution)
        return new_solution
    
    async def get_solutions_by_simulation_id(self, simulation_id: str) -> list[Solution]:
        return self.db.query(Solution).filter(Solution.simulation_id == simulation_id).all()