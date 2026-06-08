from .solver_worker import (
	get_solution_with_or_tools as or_tools_solver,
	get_solution_with_manual_solver as manual_solver,
)
from .optimization_worker import optimize as optimization_worker_optimize
from .dvrp_reoptimization_worker import process_congestion_reoptimization as dvrp_reoptimization_worker_process_congestion
from .matrix_worker import (
	generate_matrices as _matrix_worker_generate_matrices,
	get_matrix_results as _matrix_worker_get_matrix_results,
)
from .simulation_progress_worker import (
	process_running_simulation_arrivals as simulation_progress_worker_process_running_simulation_arrivals,
)
from .simulation_engine_worker import run_simulation_engine as simulation_engine_worker_run_simulation_engine
from .solver_finalize_worker import finalize_simulation as solver_finalize_worker_finalize_simulation


async def matrix_worker_generate_matrices(simulation_id: str, start_pair_index: int = 0):
	return await _matrix_worker_generate_matrices(simulation_id, start_pair_index=start_pair_index)


async def matrix_worker_get_matrix_results(simulation_id: str):
	return await _matrix_worker_get_matrix_results(simulation_id)

__all__ = [
	"or_tools_solver",
	"manual_solver",
	"optimization_worker_optimize",
	"dvrp_reoptimization_worker_process_congestion",
	"matrix_worker_generate_matrices",
	"matrix_worker_get_matrix_results",
	"simulation_progress_worker_process_running_simulation_arrivals",
	"simulation_engine_worker_run_simulation_engine",
	"solver_finalize_worker_finalize_simulation",
]
