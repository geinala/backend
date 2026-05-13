import asyncio
import json
import time as time_module
import traceback
from datetime import datetime, timezone, timedelta
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.services.tomtom_service import TomTomService
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.schemas.simulation_job_schema import SimulationJobUpdateData
from app.models.simulation_uploaded_row import SimulationUploadedRow
from app.models.simulation_job import SimulationGeocodingStatusEnum

from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

class GeocodeService:
    MAX_CONCURRENT_REQUESTS = 5
    GEOCODE_STEP = 3

    def __init__(
        self, 
        tomtom_service: TomTomService,
        simulation_uploaded_row_repository: SimulationUploadedRowRepository,
        simulation_job_repository: SimulationJobRepository
        ):
        self.tomtom_service = tomtom_service
        self.simulation_uploaded_row_repository = simulation_uploaded_row_repository
        self.simulation_job_repository = simulation_job_repository

    async def _geocode_single_row(self, row: SimulationUploadedRow, semaphore: asyncio.Semaphore) -> dict[str, object]:
        async with semaphore:
            if not row.final_address:
                return {
                    "id": row.id,
                    "status": "skipped",
                }
            
            geocode_result = await self.tomtom_service.fuzzy_search(row.final_address)
            api_results = geocode_result.get("results")
            
            if api_results:
                best_result = api_results[0]
                if best_result and best_result.get("position"):
                    city_name = row.city.split(",")[0].replace("KOTA ", "").strip() if row.city else ""
                    municipality = best_result.get("address", {}).get("municipality", "").strip()
                    
                    if city_name.upper() == municipality.upper():
                        return {
                            "id": row.id,
                            "latitude": best_result["position"]["lat"],
                            "longitude": best_result["position"]["lon"],
                            "geocode_provider": "TomTom API",
                            "geocode_score": best_result.get("score"),
                            "geocode_response": json.dumps(geocode_result),
                        }
            
            return {
                "id": row.id,
                "resolution_status": "needed_review",
                "geocode_response": json.dumps(geocode_result),
            }

    async def run(self, simulation_job_id: str) -> list[dict[str, object]]:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "geocode_process",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }
        
        try:
            simulation_job = await self.simulation_job_repository.get_simulation_job_by_id(simulation_job_id)
            total_rows_from_excel: int = simulation_job.total_rows if simulation_job is not None and simulation_job.total_rows is not None else 0
            
            # Set geocoding as started
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    geocoding_status=SimulationGeocodingStatusEnum.in_progress,
                    geocoding_started_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            
            uploaded_rows = await self.simulation_uploaded_row_repository.get_uploaded_rows_by_simulation_job_id_and_resolution_status(
                simulation_job_id=simulation_job_id,
                resolution_status="auto_solved"
            )
            batch_size = len(uploaded_rows)

            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
            
            # Process all rows concurrently
            updated_rows = await asyncio.gather(
                *[self._geocode_single_row(row, semaphore) for row in uploaded_rows]
            )
            
            skipped_rows_count = sum(1 for row in updated_rows if row.get("status") == "skipped")
            processed_rows = [row for row in updated_rows if row.get("status") != "skipped"]
            
            await self.simulation_uploaded_row_repository.update_geocoded_rows(updated_rows=processed_rows)
            
            # Calculate progress percentage based on total rows from Excel
            progress_percentage: int = int((len(processed_rows) / total_rows_from_excel * 100)) if total_rows_from_excel > 0 else 0
            
            # Estimate completion time based on processing rate
            elapsed_time = time_module.time() - start_time
            estimated_total_time: float = (elapsed_time / len(processed_rows)) * total_rows_from_excel if len(processed_rows) > 0 else 0.0
            remaining_time: float = max(0.0, estimated_total_time - elapsed_time)
            estimated_completion = datetime.now(timezone.utc) + timedelta(seconds=remaining_time)
            
            # Determine geocoding status: completed if all rows in batch are processed (successfully or skipped)
            is_batch_complete = (len(processed_rows) + skipped_rows_count) == batch_size
            geocoding_status = SimulationGeocodingStatusEnum.completed if is_batch_complete else SimulationGeocodingStatusEnum.in_progress
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    geocoded_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    current_step=self.GEOCODE_STEP,
                    progress_geocoding_percentage=progress_percentage,
                    estimated_completion_time=estimated_completion,
                    geocoding_status=geocoding_status,
                )
            )
            
            wide_event["status"] = "success"
            wide_event["processed_rows"] = len(processed_rows)
            wide_event["skipped_rows"] = skipped_rows_count
            wide_event["progress_percentage"] = progress_percentage
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000

            logger.info(wide_event)
            
            return processed_rows

        except ValueError as e:
            wide_event["status"] = "failed"
            wide_event["error_type"] = "ValueError"
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise
        except KeyError as e:
            wide_event["status"] = "failed"
            wide_event["error_type"] = "KeyError"
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error_type"] = type(e).__name__
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise