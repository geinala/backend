from sqlalchemy.orm import Session

from app.models.solution import CreateSolution, Solution

class SolutionRepository:
    def __init__(self, db: Session):
        self.db = db
        
    async def bulk_insert_solutions(self, solutions_data: list[CreateSolution]):
        new_solutions = [
            Solution(
                simulation_id=solution_data.simulation_id,
                courier_id=solution_data.courier_id,
                routes=solution_data.routes,
                demand_in_kilograms=solution_data.demand_in_kilograms,
                time_in_seconds=solution_data.time_in_seconds
            )
            for solution_data in solutions_data
        ]
        self.db.bulk_save_objects(new_solutions)
        self.db.commit()
        return new_solutions
        
    async def insert_solution(self, solution_data: CreateSolution):
        new_solution: Solution = Solution(
            simulation_id=solution_data.simulation_id,
            courier_id=solution_data.courier_id,
            routes=solution_data.routes,
            demand_in_kilograms=solution_data.demand_in_kilograms,
            time_in_seconds=solution_data.time_in_seconds
        )
        self.db.add(new_solution)
        self.db.commit()
        self.db.refresh(new_solution)
        return new_solution
    
    async def get_solutions_by_simulation_id(self, simulation_id: str) -> list[Solution]:
        return self.db.query(Solution).filter(Solution.simulation_id == simulation_id).all()