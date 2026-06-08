from datetime import datetime, timezone
from typing import List, Dict, Any
from collections import defaultdict
import math
import time
from dataclasses import dataclass

import json
from app.lib.logging.logging import get_logger

from app.models.node import Node
from app.models.tuning_experiment_uploaded_row import TuningExperimentUploadedRow
from app.repositories.depot_repository import DepotRepository
from app.repositories.tuning_experiment_dataset_repository import TuningExperimentDatasetRepository
from app.repositories.tuning_experiment_repository import TuningExperimentRepository
from app.repositories.tuning_experiment_run_repository import TuningExperimentRunRepository
from app.repositories.tuning_experiment_uploaded_row_repository import TuningExperimentUploadedRowRepository
from app.schemas.tuning_experiment_run_schema import TuningExperimentRunCreateSchema
from app.schemas.tuning_experiment_schema import TuningExperimentCreateSchema
from app.services.manual_solver.manual_solver import TabuSearchSolver
from app.services.manual_solver.types import ManualSolverProblem
from app.services.manual_solver.types import FirstSolutionStrategy
from app.services.matrix_service import MatrixService
from app.models.tuning_experiment_dataset import TuningExperimentDatasetStatusEnum

@dataclass
class GridConfig:
    it_max: int
    tab_tenure: int
    it_cons: int
    it_div: int
    
@dataclass
class TuningExperimentResult:
    config: GridConfig
    fitness: float
    route: Dict[str, list[int]]
    execution_ms: float
    convergence_iteration: int
    history: list[float]

logger = get_logger(__name__)

class TuningExperimentService:
    def __init__(
        self,
        tuning_experiment_repository: TuningExperimentRepository,
        tuning_experiment_uploaded_row_repository: TuningExperimentUploadedRowRepository,
        tuning_experiment_run_repository: TuningExperimentRunRepository,
        tuning_experiment_dataset_repository: TuningExperimentDatasetRepository,
        depot_repository: DepotRepository,
        matrix_service: MatrixService
    ) -> None:
        self.tuning_experiment_repository = tuning_experiment_repository
        self.tuning_experiment_uploaded_row_repository = tuning_experiment_uploaded_row_repository
        self.tuning_experiment_run_repository = tuning_experiment_run_repository
        self.matrix_service = matrix_service
        self.tuning_experiment_dataset_repository = tuning_experiment_dataset_repository
        self.depot_repository = depot_repository
        
    async def run_experiment(
        self,
        tuning_experiment_dataset_id: str,
    ):
        logger.info(f"Starting tuning experiment for dataset: {tuning_experiment_dataset_id}")
        
        dataset = await self.tuning_experiment_dataset_repository.get_tuning_experiment_dataset_by_id(
            tuning_experiment_dataset_id=tuning_experiment_dataset_id
        )
        
        if not dataset:
            logger.error(f"Tuning experiment dataset with id {tuning_experiment_dataset_id} not found.")
            raise Exception("Dataset not found")
        
        depot = await self.depot_repository.get_depot_by_id(depot_id=dataset.depot_id)
        
        if not depot:
            logger.error(f"Depot with id {dataset.depot_id} not found for dataset {tuning_experiment_dataset_id}.")
            raise Exception("Depot not found")
        
        rows = await self.tuning_experiment_uploaded_row_repository.get_uploaded_rows_by_tuning_experiment_dataset_id(
            tuning_experiment_dataset_id=tuning_experiment_dataset_id
        )
        
        if len(rows) == 0:
            logger.warning(
                f"No uploaded rows found for tuning experiment dataset id: {tuning_experiment_dataset_id}"
            )
            return
        
        logger.info(f"Successfully loaded {len(rows)} rows from dataset.")

        default_datetime = datetime.now(timezone.utc).replace(
            hour=8, minute=0, second=0, microsecond=0,
        )

        start_datetime = (
            rows[0].start_datetime.replace(hour=8, minute=0, second=0, microsecond=0)
            if rows and rows[0].start_datetime is not None
            else default_datetime
        )

        courier_groups: defaultdict[str, list[TuningExperimentUploadedRow]] = defaultdict(list)
        for row in rows:
            c_name = row.courier or "Unassigned"
            courier_groups[c_name].append(row)
            
        logger.info(f"Grouped rows into {len(courier_groups)} couriers.")

        # 2. HITUNG RATA-RATA JUMLAH NODE (NC) UNTUK GRID CONFIG
        total_unique_nodes = 0
        for c_rows in courier_groups.values():
            nc_courier = len(set((round(r.latitude, 5), round(r.longitude, 5)) for r in c_rows if r.latitude and r.longitude))
            total_unique_nodes += nc_courier
            
        avg_nc = max(1, round(total_unique_nodes / len(courier_groups)))
        configs = self.generate_grid_configs(avg_nc)
        
        logger.info(f"Calculated average NC: {avg_nc}. Generated {len(configs)} grid configurations to evaluate.")

        # 3. PRE-COMPUTE MATRIKS UNTUK MASING-MASING KURIR (MENGHEMAT API CALL)
        logger.info("Starting pre-computation of distance and time matrices from TomTom...")
        courier_matrices: Dict[str, Any] = {}
        for courier, c_rows in courier_groups.items():
            nodes: list[Node] = []
            
            depot_node = Node(
                matrix_index=0,
                latitude=depot.latitude,
                longitude=depot.longitude,
                demand=0.0,
                is_completed=False,
            )
            nodes.append(depot_node)
            
            matrix_index = 1
            for row in c_rows:
                node = self._map_row_to_node(row, matrix_index)
                if node:
                    nodes.append(node)
                    matrix_index += 1
                    
            if len(nodes) < 3:
                logger.warning(
                    f"Skipping courier '{courier}' because they only have {len(nodes)} nodes "
                    "(Depot + Packages). Tabu Search requires at least 1 Depot and 2 Packages."
                )
                continue
                
            time_matrix, distance_matrix = await self.matrix_service.generate_live_distance_matrix_and_time_matrix_for_tuning_experiment(
                nodes=nodes,
                departure_time=start_datetime
            )
            
            logger.info(f"Received time matrix for courier '{courier}': {time_matrix}")
            logger.info(f"Received distance matrix for courier '{courier}': {distance_matrix}")
            
            courier_matrices[courier] = {
                "time_matrix": time_matrix,
                "distance_matrix": distance_matrix,
                "nodes_count": len(nodes)
            }
            
            logger.info(f"Successfully generated matrix for courier '{courier}' with {len(nodes)} nodes.")

        best_fitness = float("inf")
        best_result: TuningExperimentResult | None = None
        all_runs_payload: list[TuningExperimentRunCreateSchema] = []

        # 4. LOOPING GRID SEARCH
        logger.info("Starting grid search evaluation...")
        for i, config in enumerate(configs, start=1):
            logger.info(f"Evaluating config {i}/{len(configs)}: it_max={config.it_max}, tab_tenure={config.tab_tenure}, it_cons={config.it_cons}, it_div={config.it_div}")
            started = time.time()
            
            current_total_fitness = 0.0
            routes_payload: Dict[str, list[int]] = {}
            histories: list[list[float]] = []
            max_convergence = 0
            
            # Eksekusi Tabu Search untuk setiap kurir dengan config yang sama
            for courier, matrices in courier_matrices.items():
                solver = TabuSearchSolver(
                    enable_aspiration=True,
                    random_seed=42,
                    first_solution_strategy=FirstSolutionStrategy.NEAREST_NEIGHBOR,
                    max_local_search_iterations=config.it_max,
                    early_stop_no_improvement_iterations=round(config.it_max * 0.2),
                    tabu_tenure=config.tab_tenure,
                    diversify_after_iterations=config.it_cons,
                    diversification_strength=config.it_div,
                    optimization_target="time",
                    track_iteration_history=True,
                )
                
                _, assignment = solver.solve(problem=ManualSolverProblem(
                    depot=0,
                    time_matrix=matrices["time_matrix"],
                    distance_matrix=matrices["distance_matrix"],
                ))
                
                if assignment is None:
                    logger.warning(f"Solver failed to find a valid assignment for courier '{courier}' under current config.")
                    continue
                
                current_total_fitness += assignment.total_duration_in_seconds
                routes_payload[courier] = assignment.tour
                histories.append(assignment.history)
                
                conv_iter = assignment.iterations
                for log in reversed(assignment.logs):
                    if log.get("is_new_best"):
                        conv_iter = log.get("iteration", assignment.iterations)
                        break
                max_convergence = max(max_convergence, conv_iter)

            if current_total_fitness == 0.0 or not histories:
                logger.warning(f"Skipping config {i} because all couriers failed.")
                continue

            execution_ms = (time.time() - started) * 1000
            logger.info(f"Config {i} completed in {execution_ms:.2f}ms. Total fitness: {current_total_fitness} seconds. Convergence at iter: {max_convergence}")

            # 5. GABUNGKAN HISTORY KONVERGENSI SELURUH KURIR (Padding Element-wise Sum)
            # Jika Kurir A konvergen di iterasi 50 dan B di iterasi 100, nilai A akan di-pad (diperpanjang) 
            # menggunakan nilai terbaik terakhirnya untuk dijumlahkan secara fair dengan B.
            max_hist_len = max((len(h) for h in histories), default=0)
            summed_history: list[float] = []
            for i in range(max_hist_len):
                sum_val = 0
                for h in histories:
                    if i < len(h):
                        sum_val += h[i]
                    else:
                        sum_val += h[-1] if h else 0
                summed_history.append(sum_val)

            all_runs_payload.append(
                TuningExperimentRunCreateSchema(
                    convergence_iteration=max_convergence,
                    execution_time_ms=execution_ms,
                    fitness_score=current_total_fitness,
                    it_max=config.it_max,
                    tab_tenure=config.tab_tenure,
                    it_cons=config.it_cons,
                    it_div=config.it_div,
                    tuning_experiment_id=None,
                )
            )

            if current_total_fitness < best_fitness:
                logger.info(f"🌟 New best config found! Fitness improved from {best_fitness} to {current_total_fitness}")
                best_fitness = current_total_fitness
                best_result = TuningExperimentResult(
                    config=config,
                    fitness=current_total_fitness,
                    route=routes_payload,
                    execution_ms=execution_ms,
                    convergence_iteration=max_convergence,
                    history=summed_history,
                )

        if not best_result:
            logger.error("Grid search completed but no valid results were generated.")
            raise Exception("No result generated for any configuration")
        
        logger.info(f"Grid search complete! Best fitness: {best_result.fitness}. Calculating improvement...")
        
        # Kalkulasi perbaikan fitness (Initial - Best) / Initial * 100
        initial_fitness = best_result.history[0] if best_result.history else best_result.fitness
        improvement_pct = ((initial_fitness - best_result.fitness) / initial_fitness * 100) if initial_fitness > 0 else 0.0

        logger.info("Saving experiment results to database...")
        tuning_experiment = await self.tuning_experiment_repository.create_tuning_experiment(
            tuning_experiment=TuningExperimentCreateSchema(
                base_n_c=total_unique_nodes,
                best_fitness_score=best_result.fitness,
                dataset_id=dataset.id.__str__(),
                it_max=best_result.config.it_max,
                tab_tenure=best_result.config.tab_tenure,
                it_cons=best_result.config.it_cons,
                it_div=best_result.config.it_div,
                best_route_payload=json.dumps(best_result.route),
                completed_at=datetime.now(timezone.utc),
                convergence_iteration=best_result.convergence_iteration,
                execution_time_ms=best_result.execution_ms,
                early_stop_no_improvement_iterations=round(best_result.config.it_max * 0.2),
                improvement_percentage=improvement_pct,
                initial_fitness_score=initial_fitness,
                random_seed=42
            )
        )
        
        for payload in all_runs_payload:
            payload.tuning_experiment_id = tuning_experiment.id
            
        await self.tuning_experiment_run_repository.bulk_create_tuning_experiment_runs(
            tuning_experiment_runs=all_runs_payload
        )
        
        await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
            tuning_experiment_dataset_id=dataset.id.__str__(),
            new_status=TuningExperimentDatasetStatusEnum.completed
        )
        
        logger.info(f"Successfully saved {len(all_runs_payload)} run configurations to database. Experiment {tuning_experiment.id} is finalized.")
    
    def generate_grid_configs(self, nc: int) -> List[GridConfig]:
        it_max_options = [5 * nc, 10 * nc, 15 * nc]
        tab_tenure_options = [max(1, math.floor(nc / 6)), max(1, math.floor(nc / 3)), max(1, math.floor(nc / 2))]
        it_cons_options = [max(1, math.floor(nc / 2)), nc, 2 * nc]
        it_div_options = [max(1, math.floor(nc / 10)), max(1, math.floor(nc / 5)), max(1, math.floor(nc / 2)), nc]

        configs: List[GridConfig] = []
        for it_max in it_max_options:
            for tab_tenure in tab_tenure_options:
                for it_cons in it_cons_options:
                    for it_div in it_div_options:
                        configs.append(GridConfig(it_max=it_max, tab_tenure=tab_tenure, it_cons=it_cons, it_div=it_div))
        return configs
    
    def _map_row_to_node(self, row: TuningExperimentUploadedRow, matrix_index: int) -> Node | None:
        if row.latitude is None or row.longitude is None:
            return None

        return Node(
            matrix_index=matrix_index,
            latitude=row.latitude,
            longitude=row.longitude,
            demand=row.weight or 0.0,
            is_completed=False,
        )