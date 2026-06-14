from typing import TypedDict

import asyncio
from uuid import UUID
from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.repositories.matrix_repository import MatrixRepository
from app.workers.matrix_worker import process_matrix_results_batch_job
from app.repositories.simulation_repository import SimulationRepository
from app.models.node import Node
from app.schemas.matrix_schema import MatrixResultInsert
from app.models.matrix import MatrixTypeEnum
from app.services.job_service import enqueue_job
from app.services.tomtom_service import STATE_ENUM, TomTomService
from datetime import datetime, timedelta
from app.lib.logging.logging import get_logger
from app.lib.date_converter import format_departure_time

logger = get_logger(__name__)


class Point(TypedDict):
    latitude: float
    longitude: float


class LocationPayload(TypedDict):
    point: Point
    
class MatrixJobInfo(TypedDict):
    job_id: str
    o_indices: list[int]
    d_indices: list[int]

class MatrixService:
    MATRIX_SUBMISSION_DELAY = timedelta(seconds=10)
    MATRIX_CACHE_KEY_PREFIX = "simulation:matrix-time-matrix:"

    def __init__(
        self, 
        tomtom_service: TomTomService, 
        simulation_repository: SimulationRepository,
        matrix_repository: MatrixRepository         
    ):
        self.tomtom_service = tomtom_service
        self.simulation_repository = simulation_repository
        self.matrix_repository = matrix_repository

    async def generate_live_distance_matrix_and_time_matrix(
        self,
        nodes: list[Node],
        departure_time: datetime
    ) -> tuple[list[list[int]], list[list[int]]]:
        num_nodes = len(nodes)
        matrix_size = 30 if num_nodes > 30 else num_nodes

        chunk_indices = [
            list(range(i, min(i + matrix_size, num_nodes))) 
            for i in range(0, num_nodes, matrix_size)
        ]
        
        job_ids: list[MatrixJobInfo] = []
        is_first_batch = True
        
        for o_indices in chunk_indices:
            for d_indices in chunk_indices:
                if not is_first_batch:
                    logger.info(f"Menunggu {self.MATRIX_SUBMISSION_DELAY.total_seconds()} detik sebelum submit live batch berikutnya...")
                    await asyncio.sleep(self.MATRIX_SUBMISSION_DELAY.total_seconds())

                origin_locations = [self._node_to_location_payload(nodes[i]) for i in o_indices]
                destination_locations = [self._node_to_location_payload(nodes[i]) for i in d_indices]

                logger.info(
                    f"Submitting live matrix batch (Origins: {len(origin_locations)}, "
                    f"Destinations: {len(destination_locations)}) at {format_departure_time(departure_time)} for reoptimization"
                )

                response = self.tomtom_service.submit_matrix(
                    origins=origin_locations,
                    destinations=destination_locations,
                    departure_time=format_departure_time(departure_time)
                )
                
                job_id = response.get("jobId")
                if not job_id:
                    raise ValueError("Gagal mendapatkan jobId dari TomTom saat live matrix generation.")

                job_ids.append({
                    "job_id": job_id,
                    "o_indices": o_indices,
                    "d_indices": d_indices
                })
                
                is_first_batch = False

        logger.info(f"Total {len(job_ids)} batch(es) disubmit ke TomTom. Memulai polling...")

        time_matrix = [[0] * num_nodes for _ in range(num_nodes)]
        distance_matrix = [[0] * num_nodes for _ in range(num_nodes)]
        pending_jobs = list(job_ids)
        max_retries = 30

        for _ in range(max_retries):
            if not pending_jobs:
                break

            await asyncio.sleep(10)

            still_pending: list[MatrixJobInfo] = []
            for job_info in pending_jobs:
                job_id = job_info["job_id"]
                status_response = self.tomtom_service.get_matrix_status(job_id)
                state = status_response.get("state")

                if state == STATE_ENUM.Completed.value:
                    matrix_result = self.tomtom_service.get_matrix_result(job_id)
                    
                    for result in matrix_result.get("data", []):
                        local_o_idx = result.get("originIndex")
                        local_d_idx = result.get("destinationIndex")
                        summary = result.get("routeSummary", {})
                        
                        global_o_idx = job_info["o_indices"][local_o_idx]
                        global_d_idx = job_info["d_indices"][local_d_idx]
                        
                        time_matrix[global_o_idx][global_d_idx] = summary.get("travelTimeInSeconds", 0)
                        distance_matrix[global_o_idx][global_d_idx] = summary.get("lengthInMeters", 0)

                elif state == STATE_ENUM.Failed.value:
                    raise RuntimeError(f"Live matrix generation failed di TomTom untuk job {job_id}")
                else:
                    still_pending.append(job_info)

            pending_jobs = still_pending

        if pending_jobs:
            raise TimeoutError("Polling live matrix generation dari TomTom timeout.")
        
        logger.info("Live matrix generation completed, returning time and distance matrices")
        logger.info(f"Generated time matrix: {time_matrix}")
        logger.info(f"Generated distance matrix: {distance_matrix}")

        return time_matrix, distance_matrix
    
    async def dispatch_matrix_saving_job(
        self,
        time_matrix: list[list[int]],
        distance_matrix: list[list[int]],
        simulation_id: str,
        courier_id: int,
        matrix_type: MatrixTypeEnum,
        matrix_stage: int
    ):
        data_to_save_batch: list[MatrixResultInsert] = []
        num_nodes = len(time_matrix)

        for o_idx in range(num_nodes):
            for d_idx in range(num_nodes):
                data_to_save_batch.append(
                    MatrixResultInsert(
                        simulation_id=UUID(simulation_id),
                        courier_id=courier_id,
                        origin_index=o_idx,
                        destination_index=d_idx,
                        travel_time_in_seconds=time_matrix[o_idx][d_idx],
                        length_in_meters=distance_matrix[o_idx][d_idx],
                        matrix_type=matrix_type,
                        matrix_stage=matrix_stage
                    )
                )

        if data_to_save_batch:
            logger.info(f"Mengantrekan job background untuk menyimpan {len(data_to_save_batch)} baris matriks...")
            
            enqueue_job(
                process_matrix_results_batch_job,
                job_type=JobType.LIGHT,
                job_prefix=JOB_PREFIXES_ENUM.SAVE_MATRIX,
                matrix_payloads=data_to_save_batch
            )
            
    async def get_latest_matrix_stage(self, simulation_id: str, courier_id: int, matrix_type: MatrixTypeEnum) -> int:
        latest_stage = await self.matrix_repository.get_latest_matrix_stage(simulation_id, courier_id, matrix_type)
        return latest_stage if latest_stage is not None else 0

    def _node_to_location_payload(self, node: Node) -> LocationPayload:
        return LocationPayload(
            point=Point(
                latitude=node.latitude,
                longitude=node.longitude
            )
        )
