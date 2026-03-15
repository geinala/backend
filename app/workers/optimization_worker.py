from app.services.matrix_service import MatrixService
from app.repositories.matrix_repository import MatrixRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.services.optimization_service import OptimizationService
from app.services.tomtom_service import TomTomService
from app.lib.db import get_db
from app.lib.logging.logging import get_logger


logger = get_logger(__name__)

async def optimize(simulation_id: str):
        try:
            db = next(get_db())
            simulation_repository = SimulationRepository(db)
            optimization_service = OptimizationService(
                matrix_service = MatrixService(
                matrix_repository = MatrixRepository(db),
                node_repository = NodeRepository(db),
                tomtom_service = TomTomService(),
                simulation_repository = simulation_repository
                ),
                simulation_repository = simulation_repository
            )
            
            await optimization_service.optimize(simulation_id)
            
        except Exception as e:
            logger.error(f"Error optimizing simulation {simulation_id}: {str(e)}")
            raise e