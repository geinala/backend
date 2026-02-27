
import time
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.configs.worker_configuration import JobType
from app.constants.job_prefixes import JOB_PREFIXES_ENUM
from app.lib.logging.logging import get_logger
from app.lib.response_formatter import ResponseFormatter
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.node_repository import NodeRepository
from app.services.job_service import enqueue_job
from app.services.minio_service import MinioService
from app.services.simulation_service import SimulationService
from app.lib.minio import minioClient

logger = get_logger(__name__)

class SimulationController:
    def __init__(self, db: Session):
        self.db = db
        self.simulation_service = SimulationService(
            minio_service=MinioService(minio_client=minioClient),
            simulation_repository=SimulationRepository(db),
            node_repository=NodeRepository(db)
        )
        
    async def process_files(self, simulation_id: str) -> JSONResponse:
        start_time = time.time()
        wide_event: dict[str, object] = {
            "event_type": "process_files_request",
            "simulation_id": simulation_id,
            "status": "processing",
        }
        
        try:
            job = enqueue_job(
                'app.workers.simulation_worker.process_files',
                job_type=JobType.HEAVY,
                job_prefix=JOB_PREFIXES_ENUM.SIMULATION_PROCESSING_DATA,
                simulation_id=simulation_id
            )
            
            wide_event["status"] = "success"
            wide_event["job_id"] = job.id
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return ResponseFormatter.success_with_data(
                data={"job_id": str(job.id)},
                message="File processing has been enqueued for processing",
                status_code=200
            )
        
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e