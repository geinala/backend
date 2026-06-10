from app.repositories.daily_optimization_log_repository import DailyOptimizationLogRepository
from app.repositories.optimization_iteration_repository import OptimizationIterationRepository
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.solution_repository import SolutionRepository
from app.repositories.tabu_search_configuration_repository import TabuSearchConfigurationRepository
from app.services.manual_solver.service import ManualSolverService
from app.services.manual_solver.types import ComparisonScenario
from app.services.or_tools_solver import OrToolsSolverService
from app.repositories.optimization_run_repository import OptimizationRunRepository
from app.services.matrix_service import MatrixService
from app.repositories.matrix_repository import MatrixRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.courier_repository import CourierRepository
from app.services.tomtom_service import TomTomService
from app.lib.db import get_db
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

async def get_solution_with_or_tools(simulation_id: str):
        try:
            db = next(get_db())
            solver_service = OrToolsSolverService(
                matrix_service = MatrixService(
                    matrix_repository = MatrixRepository(db),
                    node_repository = NodeRepository(db),
                    tomtom_service = TomTomService(),
                    simulation_repository=SimulationRepository(db),
                ),
                courier_repository = CourierRepository(db),
                node_repository = NodeRepository(db),
                solution_repository = SolutionRepository(db),
                simulation_repository=SimulationRepository(db),
                optimization_run_repository=OptimizationRunRepository(db)
            )
            
            await solver_service.solve(simulation_id)
            
        except Exception as e:
            logger.error(f"Error solving optimization for simulation {simulation_id}: {str(e)}")
            raise e
        
async def get_solution_with_manual_solver(simulation_id: str, scenario: ComparisonScenario):
        try:
            db = next(get_db())
            solver_service = ManualSolverService(
                matrix_service = MatrixService(
                    matrix_repository = MatrixRepository(db),
                    node_repository = NodeRepository(db),
                    tomtom_service = TomTomService(),
                    simulation_repository=SimulationRepository(db),
                ),
                courier_repository = CourierRepository(db),
                node_repository = NodeRepository(db),
                solution_repository = SolutionRepository(db),
                simulation_repository=SimulationRepository(db),
                optimization_iteration_repository=OptimizationIterationRepository(db),
                optimization_run_repository=OptimizationRunRepository(db),
                daily_optimization_log_repository=DailyOptimizationLogRepository(db),
                tabu_search_configuration_repository=TabuSearchConfigurationRepository(db)
            )
            
            await solver_service.solve(simulation_id, scenario=scenario)
            
        except Exception as e:
            logger.error(f"Error solving optimization for simulation {simulation_id}: {str(e)}")
            raise e