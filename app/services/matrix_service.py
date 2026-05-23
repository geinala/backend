from typing import TypedDict
from app.models.matrix import CreateMatrixBatchData, CreateMatrixResultData, MatrixBatch, MatrixBatchStatusEnum, UpdateMatrixBatchStatusData
from app.repositories.matrix_repository import MatrixRepository
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_repository import SimulationRepository
from app.models.node import Node
from app.models.simulation import SimulationStatusEnum
from app.services.tomtom_service import STATE_ENUM, MatrixResponse, RouteSummary, TomTomService
from datetime import datetime, timedelta, timezone
from app.lib.logging.logging import get_logger
from app.services.job_service import enqueue_job
from app.constants.job_prefixes import JOB_PREFIXES_ENUM, JobType

logger = get_logger(__name__)


class Point(TypedDict):
    latitude: float
    longitude: float


class LocationPayload(TypedDict):
    point: Point


class MatrixService:
    MATRIX_SUBMISSION_DELAY = timedelta(seconds=60)

    def __init__(self, node_repository: NodeRepository, tomtom_service: TomTomService, matrix_repository: MatrixRepository, simulation_repository: SimulationRepository):
        self.node_repository = node_repository
        self.tomtom_service = tomtom_service
        self.matrix_repository = matrix_repository
        self.simulation_repository = simulation_repository

    async def submit_tomtom_matrix_requests(self, simulation_id: str, start_pair_index: int = 0):
        existing_batches = self.matrix_repository.get_batches_by_simulation_id(simulation_id)
        if start_pair_index == 0 and existing_batches:
            logger.info(f"Matrix batches already exist for simulation {simulation_id}, skipping submission")
            return

        nodes = self._get_all_nodes(simulation_id)
        
        logger.info(f"Retrieved {len(nodes)} nodes for simulation {simulation_id}")
        
        # TomTom API has a limit of 2500 elements per matrix
        # but to be safe and avoid hitting limits
        # we will use a smaller batch size of 50 nodes per matrix.
        matrix_size = 30 if len(nodes) > 30 else len(nodes)

        node_pairs = self._split_nodes_by_matrix(nodes, matrix_size)
        if start_pair_index >= len(node_pairs):
            logger.info(f"All matrix batches already submitted for simulation {simulation_id}")
            return

        if existing_batches and start_pair_index < len(existing_batches):
            start_pair_index = len(existing_batches)

        origins, destinations = node_pairs[start_pair_index]
        origin_locations = [self._node_to_location_payload(node) for node in origins]
        destination_locations = [self._node_to_location_payload(node) for node in destinations]

        logger.info(
            f"Submitting matrix {start_pair_index + 1}/{len(node_pairs)} for simulation {simulation_id} "
            f"with {len(origin_locations)} origin nodes and {len(destination_locations)} destination nodes"
        )

        logger.info(f"Submitting matrix at {datetime.now(timezone.utc)} for simulation {simulation_id} with node indices {origins[0].id} to {origins[-1].id}")
        response = self.tomtom_service.submit_matrix(origin_locations, destination_locations)

        batch_data = CreateMatrixBatchData(
            simulation_id=simulation_id,
            origin_start_index=origins[0].matrix_index,
            origin_end_index=origins[-1].matrix_index,
            destination_start_index=destinations[0].matrix_index,
            destination_end_index=destinations[-1].matrix_index,
            tomtom_job_id=response.get("jobId"),
        )
        self.matrix_repository.bulk_insert_matrix_batches([batch_data])

        next_pair_index = start_pair_index + 1
        
        logger.info(f"Submitted matrix batch for simulation {simulation_id}, next pair index is {next_pair_index}")
        logger.info(f"Total batches for simulation {simulation_id} is {len(node_pairs)}, submitted batches: {next_pair_index}")
        
        if next_pair_index < len(node_pairs):
            from app.workers import matrix_worker_generate_matrices

            enqueue_job(
                function_path=matrix_worker_generate_matrices,
                delay=self.MATRIX_SUBMISSION_DELAY,
                job_prefix=JOB_PREFIXES_ENUM.MATRIX_GENERATION,
                job_type=JobType.HEAVY,
                simulation_id=simulation_id,
                start_pair_index=next_pair_index,
            )
            logger.info(
                f"Scheduled next matrix submission for simulation {simulation_id} "
                f"after {self.MATRIX_SUBMISSION_DELAY}"
            )
        else:
            from app.workers import matrix_worker_get_matrix_results

            logger.info(f"All matrix batches submitted for simulation {simulation_id}")
            enqueue_job(
                function_path=matrix_worker_get_matrix_results,
                delay=timedelta(seconds=15),
                job_prefix=JOB_PREFIXES_ENUM.MATRIX_RESULT_PROCESSING,
                job_type=JobType.HEAVY,
                simulation_id=simulation_id,
            )
            logger.info(
                f"Scheduled matrix result processing for simulation {simulation_id} "
                f"after final batch submission"
            )
        
    async def get_matrix_results(self, simulation_id: str):
        batches = self.matrix_repository.get_batches_by_simulation_id(simulation_id, status=MatrixBatchStatusEnum.submitted)
        nodes = self._get_all_nodes(simulation_id)
        matrix_size = 30 if len(nodes) > 30 else len(nodes)
        expected_batch_count = len(self._split_nodes_by_matrix(nodes, matrix_size))
        submitted_batch_count = len(self.matrix_repository.get_batches_by_simulation_id(simulation_id))

        has_pending_batches = False
        
        for batch in batches:
            logger.info(f"Batch value: {batch.__dict__}")
            
            status_response = self.tomtom_service.get_matrix_status(batch.tomtom_job_id)
            state = status_response.get("state")
            
            logger.info(f"Received status response for batch {batch.id} with TomTom job ID {batch.tomtom_job_id}: {status_response}")
            
            if state == STATE_ENUM.Completed.value:
                # Update batch status to completed in the database
                self.matrix_repository.update_matrix_batch_status(
                    batch_id=batch.id,
                    data=UpdateMatrixBatchStatusData(
                        status=MatrixBatchStatusEnum.completed,
                        completed_at=datetime.now(timezone.utc)
                    )
                )
                
                await self._get_matrix_results(batch, simulation_id)
                
            elif state == STATE_ENUM.Failed.value:
                # Update batch status to failed in the database
                self.matrix_repository.update_matrix_batch_status(
                    batch_id=batch.id,
                    data=UpdateMatrixBatchStatusData(
                        status=MatrixBatchStatusEnum.failed,
                        completed_at=datetime.now(timezone.utc)
                    )
                )
                await self.simulation_repository.update_simulation_status(
                    simulation_id, SimulationStatusEnum.failed
                )
                logger.warning(f"Batch {batch.id} failed for simulation {simulation_id}, simulation status set to failed")
            else:
                logger.info(f"Batch {batch.id} with TomTom job ID {batch.tomtom_job_id} is still processing with state {state}")
                has_pending_batches = True

        if has_pending_batches:
            from app.workers import matrix_worker_get_matrix_results

            logger.info(f"Matrix batches for simulation {simulation_id} are still being processed")
            enqueue_job(
                    function_path=matrix_worker_get_matrix_results,
                    delay=timedelta(seconds=15),
                    job_prefix=JOB_PREFIXES_ENUM.MATRIX_RESULT_PROCESSING,
                    job_type=JobType.HEAVY,
                    simulation_id=simulation_id,
                )
        elif submitted_batch_count >= expected_batch_count:
            from app.workers import optimization_worker_optimize

            logger.info(f"Matrix batches for simulation {simulation_id} are fully processed, continuing optimization")
            enqueue_job(
                function_path=optimization_worker_optimize,
                job_prefix=JOB_PREFIXES_ENUM.OPTIMIZATION,
                job_type=JobType.HEAVY,
                simulation_id=simulation_id,
            )
        else:
            from app.workers import matrix_worker_get_matrix_results

            logger.info(
                f"Matrix batches for simulation {simulation_id} are still being submitted "
                f"({submitted_batch_count}/{expected_batch_count}), checking again later"
            )
            enqueue_job(
                function_path=matrix_worker_get_matrix_results,
                delay=timedelta(seconds=15),
                job_prefix=JOB_PREFIXES_ENUM.MATRIX_RESULT_PROCESSING,
                job_type=JobType.HEAVY,
                simulation_id=simulation_id,
            )
    
    def has_batches(self, simulation_id: str) -> bool:
        return self.matrix_repository.has_batches_by_simulation_id(simulation_id)

    def has_failed_batches(self, simulation_id: str) -> bool:
        return self.matrix_repository.has_failed_batches(simulation_id)

    async def has_pending_batches(self, simulation_id: str):
        remaining_batches = self.matrix_repository.get_batches_by_simulation_id(
            simulation_id, 
            status=MatrixBatchStatusEnum.submitted
        )

        return len(remaining_batches) > 0
    
    async def build_time_matrix(self, simulation_id: str) -> list[list[int]]:
        results = self.matrix_repository.get_matrix_results_by_simulation_id(simulation_id)

        nodes = self._get_all_nodes(simulation_id)
        num_nodes = len(nodes)

        time_matrix = [[0] * num_nodes for _ in range(num_nodes)]

        for result in results:
            origin = result.origin_index
            destination = result.destination_index
            if origin < num_nodes and destination < num_nodes:
                time_matrix[origin][destination] = result.travel_time_in_seconds

        logger.info(f"Built {num_nodes}x{num_nodes} time matrix for simulation {simulation_id} from {len(results)} results")

        return time_matrix

    
    async def _get_matrix_results(self, batch: MatrixBatch, simulation_id: str) -> list[CreateMatrixResultData]:
        matrix_result = self.tomtom_service.get_matrix_result(batch.tomtom_job_id)

        mapped_results = self._mapped_matrix_result_to_db_format(
            matrix_result.get("data"),
            batch.id,
            simulation_id,
            batch.origin_start_index,
            batch.destination_start_index,
        )

        self.matrix_repository.bulk_insert_matrix_results(mapped_results)

        return mapped_results

    def _mapped_matrix_result_to_db_format(
        self,
        matrix_result: list[MatrixResponse],
        batch_id: int,
        simulation_id: str,
        origin_offset: int = 0,
        destination_offset: int = 0,
    ) -> list[CreateMatrixResultData]:
        mapped_results: list[CreateMatrixResultData] = []
        
        for result in matrix_result:
            summary: RouteSummary = result.get("routeSummary", {})
            
            mapped_result = CreateMatrixResultData(
                origin_index=result.get("originIndex") + origin_offset,
                destination_index=result.get("destinationIndex") + destination_offset,
                travel_time_in_seconds=summary.get("travelTimeInSeconds"),
                length_in_meters=summary.get("lengthInMeters"),
                traffic_delay_in_seconds=summary.get("trafficDelayInSeconds"),
                simulation_id=simulation_id,
                matrix_batch_id=batch_id
            )
            mapped_results.append(mapped_result)
            
        return mapped_results

    def _get_all_nodes(self, simulation_id: str):
        return self.node_repository.get_nodes_by_simulation_id(simulation_id)
    
    def _split_nodes_by_matrix(self, nodes: list[Node], matrix_size: int = 50) -> list[tuple[list[Node], list[Node]]]:
        chunks = [nodes[i:i + matrix_size] for i in range(0, len(nodes), matrix_size)]

        pairs: list[tuple[list[Node], list[Node]]] = []

        for origin_chunk in chunks:
            for destination_chunk in chunks:
                pairs.append((origin_chunk, destination_chunk))

        return pairs
    
    def _node_to_location_payload(self, node: Node) -> LocationPayload:
        return LocationPayload(
            point=Point(
                latitude=node.latitude,
                longitude=node.longitude
            )
        )
