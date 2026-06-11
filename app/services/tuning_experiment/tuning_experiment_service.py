from datetime import datetime, timezone
from typing import List, Dict
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
            hour=1, minute=0, second=0, microsecond=0,
        )

        start_datetime = (
            rows[0].start_datetime.replace(hour=1, minute=0, second=0, microsecond=0)
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

        logger.info("Starting pre-computation of distance and time matrices from TomTom...")
        for courier, c_rows in courier_groups.items():
            logger.info(f"\n{'='*50}\n[COURIER] Memulai tuning rute untuk Kurir: {courier}\n{'='*50}")
            
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
                logger.warning(f"[SKIP] Kurir '{courier}' dilewati (Jumlah nodes tidak mencukupi untuk dioptimasi: {len(nodes)}).")
                continue

            nc_courier = len(nodes) - 1
            
            logger.info(f"[API] Menarik Matrix Jarak & Waktu dari TomTom untuk {len(nodes)} nodes... (Mohon tunggu)")
            
            time_matrix, distance_matrix = await self.matrix_service.generate_live_distance_matrix_and_time_matrix_for_tuning_experiment(
                nodes=nodes,
                departure_time=start_datetime
            )

            configs = self.generate_grid_configs(nc_courier)
            logger.info(f"[CONFIG] Kurir {courier} memiliki {nc_courier} nodes. Menyiapkan {len(configs)} iterasi grid search.")

            best_fitness = float("inf")
            best_result: TuningExperimentResult | None = None
            all_runs_payload: list[TuningExperimentRunCreateSchema] = []
            max_convergence = 0

            for i, config in enumerate(configs, start=1):
                logger.info(f"[EVAL {i}/{len(configs)}] Evaluating config: it_max={config.it_max}, tab_tenure={config.tab_tenure}, it_cons={config.it_cons}, it_div={config.it_div}")
                started = time.time()
                
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
                    time_matrix=[[float(x) for x in row] for row in time_matrix],
                    distance_matrix=[[float(x) for x in row] for row in distance_matrix],
                    start_index=0,
                    end_index=0,
                ))
                
                if assignment is None:
                    logger.warning(f"[EVAL {i}/{len(configs)}] Gagal menemukan solusi untuk config ini.")
                    continue
                
                fitness = assignment.total_duration_in_seconds
                execution_ms = (time.time() - started) * 1000
                
                logger.info(f"[EVAL {i}/{len(configs)}] Config completed in {execution_ms:.2f}ms. Total fitness: {fitness} seconds. Convergence at iter: {max_convergence}")

                conv_iter = assignment.iterations
                for log in reversed(assignment.logs):
                    if log.get("is_new_best"):
                        conv_iter = log.get("iteration", assignment.iterations)
                        break
                max_convergence = max(max_convergence, conv_iter)

                all_runs_payload.append(
                    TuningExperimentRunCreateSchema(
                        convergence_iteration=conv_iter,
                        execution_time_ms=execution_ms,
                        fitness_score=fitness,
                        it_max=config.it_max,
                        tab_tenure=config.tab_tenure,
                        it_cons=config.it_cons,
                        it_div=config.it_div,
                        tuning_experiment_id=None,
                    )
                )
                
                log_msg = f"[EVAL {i:02d}/{len(configs)}] " \
                          f"it_max:{config.it_max:<4} | tenure:{config.tab_tenure:<3} | cons:{config.it_cons:<3} | div:{config.it_div:<3} " \
                          f"➜ Fit: {fitness:.2f}s | Conv at: {conv_iter} | Exec: {execution_ms:.0f}ms"
                logger.info(log_msg)

                if fitness < best_fitness:
                    logger.info(f"🌟 [NEW BEST] Fitness membaik! {best_fitness if best_fitness != float('inf') else 'N/A'}s 📉 {fitness:.2f}s")
                    best_fitness = fitness
                    best_result = TuningExperimentResult(
                        config=config,
                        fitness=fitness,
                        route={courier: assignment.tour},
                        execution_ms=execution_ms,
                        convergence_iteration=conv_iter,
                        history=assignment.history,
                    )

            if best_result:
                initial_fitness = best_result.history[0] if best_result.history else best_result.fitness
                improvement_pct = ((initial_fitness - best_result.fitness) / initial_fitness * 100) if initial_fitness > 0 else 0.0

                logger.info(f"[SAVING] Menyimpan hasil eksperimen terbaik Kurir {courier} (Peningkatan: {improvement_pct:.2f}%)...")

                tuning_experiment = await self.tuning_experiment_repository.create_tuning_experiment(
                    tuning_experiment=TuningExperimentCreateSchema(
                        base_n_c=nc_courier,
                        best_fitness_score=best_result.fitness,
                        dataset_id=dataset.id.__str__(),
                        it_max=best_result.config.it_max,
                        tab_tenure=best_result.config.tab_tenure,
                        it_cons=best_result.config.it_cons,
                        it_div=best_result.config.it_div,
                        best_route_payload=json.dumps(best_result.route),
                        best_iteration_history_payload=json.dumps(best_result.history),
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
                
                logger.info(f"[COMPLETED] Seluruh proses tuning selesai! Status dataset diperbarui ke 'completed'.")
                
        await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
            tuning_experiment_dataset_id=dataset.id.__str__(),
            new_status=TuningExperimentDatasetStatusEnum.completed
        )
        
        logger.info(f"All couriers tuned successfully for dataset {dataset.id}.")
    
    def generate_grid_configs(self, nc: int) -> List[GridConfig]:
        it_max_options = [5 * nc, 10 * nc, 15 * nc]
        tab_tenure_options = [max(1, math.floor(nc / 6)), max(1, math.floor(nc / 3)), max(1, math.floor(nc / 2)), nc]
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