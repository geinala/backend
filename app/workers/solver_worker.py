from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.services.solver_service import SolverService
from app.services.matrix_service import MatrixService
from app.repositories.matrix_repository import MatrixRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.courier_repository import CourierRepository
from app.services.tomtom_service import TomTomService
from app.lib.db import get_db
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

async def get_solution(simulation_id: str):
        try:
            solver_service = SolverService(
                matrix_service = MatrixService(
                    matrix_repository = MatrixRepository(next(get_db())),
                    node_repository = NodeRepository(next(get_db())),
                    tomtom_service = TomTomService(),
                    simulation_repository=SimulationRepository(next(get_db())),
                ),
                courier_repository = CourierRepository(next(get_db())),
                node_repository = NodeRepository(next(get_db())),
                solution_repository = SolutionRepository(next(get_db())
                ),
                simulation_repository=SimulationRepository(next(get_db())),
            )
            
            await solver_service.solve(simulation_id)
            
        except Exception as e:
            logger.error(f"Error solving optimization for simulation {simulation_id}: {str(e)}")
            raise e