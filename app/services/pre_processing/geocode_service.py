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
from app.models.simulation_job import SimulationGeocodingStatusEnum, SimulationJobStatusEnum

from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

class GeocodeService:
    MAX_CONCURRENT_REQUESTS = 5
    BATCH_SIZE = 25
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

    async def run(self, simulation_job_id: str) -> list[dict[str, object]]:
        logger.info(f"Starting geocoding process for simulation job {simulation_job_id}")
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "geocode_process",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }
        
        try:
            # Set geocoding as started
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    geocoding_status=SimulationGeocodingStatusEnum.in_progress,
                    geocoding_started_at=datetime.now(timezone.utc),
                    geocoding_total_rows=0,
                    geocoding_processed_rows=0,
                    geocoding_progress_percentage=0,
                    geocoding_estimated_completion_time=None,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            
            uploaded_rows = await self.simulation_uploaded_row_repository.get_uploaded_rows_by_simulation_job_id_and_resolution_status(
                simulation_job_id=simulation_job_id,
                resolution_status="auto_solved"
            )

            total_rows = len(uploaded_rows)

            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    geocoding_total_rows=total_rows,
                    geocoding_processed_rows=0,
                    geocoding_progress_percentage=0,
                    geocoding_estimated_completion_time=None,
                    updated_at=datetime.now(timezone.utc),
                )
            )

            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            processed_rows: list[dict[str, object]] = []
            processed_rows_count = 0
            skipped_rows_count = 0
            has_needed_review_rows = False
            estimated_completion: datetime | None = None

            for batch_index, batch_start in enumerate(range(0, len(uploaded_rows), self.BATCH_SIZE), start=1):
                batch_rows = uploaded_rows[batch_start:batch_start + self.BATCH_SIZE]
                batch_results = await asyncio.gather(
                    *[self._geocode_single_row(row, semaphore) for row in batch_rows]
                )

                batch_processed_rows = [row for row in batch_results if row.get("status") != "skipped"]
                batch_skipped_rows_count = len(batch_results) - len(batch_processed_rows)
                skipped_rows_count += batch_skipped_rows_count
                has_needed_review_rows = has_needed_review_rows or any(
                    row.get("resolution_status") == "needed_review" for row in batch_processed_rows
                )

                processed_rows.extend(batch_processed_rows)
                await self.simulation_uploaded_row_repository.update_geocoded_rows(updated_rows=batch_processed_rows)

                processed_rows_count += len(batch_rows)
                progress_percentage: int = int((processed_rows_count / total_rows) * 100) if total_rows > 0 else 0

                elapsed_time = time_module.time() - start_time
                estimated_total_time: float = (elapsed_time / processed_rows_count) * total_rows if processed_rows_count > 0 else 0.0
                remaining_time: float = max(0.0, estimated_total_time - elapsed_time)
                estimated_completion = datetime.now(timezone.utc) + timedelta(seconds=remaining_time) if processed_rows_count > 0 else None

                await self.simulation_job_repository.update_simulation_job(
                    simulation_job_id=simulation_job_id,
                    update_data=SimulationJobUpdateData(
                        geocoding_total_rows=total_rows,
                        geocoding_processed_rows=processed_rows_count,
                        geocoding_progress_percentage=progress_percentage,
                        geocoding_estimated_completion_time=estimated_completion,
                        updated_at=datetime.now(timezone.utc),
                    )
                )

                wide_event["batch_number"] = batch_index
                wide_event["batch_size"] = len(batch_rows)
                wide_event["batch_skipped_rows"] = batch_skipped_rows_count
                wide_event["processed_rows"] = processed_rows_count
                wide_event["total_rows"] = total_rows
                wide_event["progress_percentage"] = progress_percentage
                logger.info(wide_event)

            geocoding_status = SimulationGeocodingStatusEnum.needed_review if has_needed_review_rows else SimulationGeocodingStatusEnum.completed

            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    geocoded_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    current_step=self.GEOCODE_STEP,
                    geocoding_total_rows=total_rows,
                    geocoding_processed_rows=processed_rows_count,
                    geocoding_progress_percentage=100,
                    geocoding_estimated_completion_time=estimated_completion,
                    geocoding_status=geocoding_status,
                )
            )
            
            wide_event["status"] = "success"
            wide_event["processed_rows"] = processed_rows_count
            wide_event["skipped_rows"] = skipped_rows_count
            wide_event["total_rows"] = total_rows
            wide_event["progress_percentage"] = 100
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000

            logger.info(wide_event)
            
            return processed_rows

        except ValueError as e:
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    geocoding_status=SimulationGeocodingStatusEnum.failed,
                    updated_at=datetime.now(timezone.utc),
                    status=SimulationJobStatusEnum.failed,
                )
            )
            wide_event["status"] = "failed"
            wide_event["error_type"] = "ValueError"
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise e
        except KeyError as e:
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    geocoding_status=SimulationGeocodingStatusEnum.failed,
                    updated_at=datetime.now(timezone.utc),
                    status=SimulationJobStatusEnum.failed,
                )
            )
            wide_event["status"] = "failed"
            wide_event["error_type"] = "KeyError"
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise e
        except Exception as e:
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    geocoding_status=SimulationGeocodingStatusEnum.failed,
                    updated_at=datetime.now(timezone.utc),
                    status=SimulationJobStatusEnum.failed,
                )
            )
            wide_event["status"] = "failed"
            wide_event["error_type"] = type(e).__name__
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise e
        
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