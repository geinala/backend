import asyncio
import json
import time as time_module
import traceback
from typing import Literal, TypedDict
from typing_extensions import NotRequired
from app.models.tuning_experiment_dataset import TuningExperimentDatasetStatusEnum
from app.models.tuning_experiment_uploaded_row import TuningExperimentUploadedRow
from app.repositories.tuning_experiment_dataset_repository import TuningExperimentDatasetRepository
from app.repositories.tuning_experiment_uploaded_row_repository import TuningExperimentUploadedRowRepository
from app.schemas.tuning_experiment_uploaded_row_schema import UpdateGeocodedTuningExperimentUploadedRowSchema
from app.services.tomtom_service import TomTomService

from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

class GeocodeRowResult(TypedDict):
    id: int
    status: Literal["success", "failed"]
    latitude: NotRequired[float]
    longitude: NotRequired[float]
    geocode_score: NotRequired[float]
    geocode_provider: NotRequired[str]
    geocode_response: NotRequired[str]

class TuningExperimentGeocodeService:
    MAX_CONCURRENT_REQUESTS = 5
    BATCH_SIZE = 25
    GEOCODE_STEP = 3

    def __init__(
        self, 
        tomtom_service: TomTomService,
        tuning_experiment_uploaded_row_repository: TuningExperimentUploadedRowRepository,
        tuning_experiment_dataset_repository: TuningExperimentDatasetRepository
        ):
        self.tomtom_service = tomtom_service
        self.tuning_experiment_uploaded_row_repository = tuning_experiment_uploaded_row_repository
        self.tuning_experiment_dataset_repository = tuning_experiment_dataset_repository

    async def run(
        self,
        tuning_experiment_dataset_id: str,
    ):
        logger.info(f"Starting geocoding process for tuning experiment dataset {tuning_experiment_dataset_id}")
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "geocode_process",
            "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
            "status": "processing",
        }
        
        try:
            dataset = await self.tuning_experiment_dataset_repository.get_tuning_experiment_dataset_by_id_and_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                status=TuningExperimentDatasetStatusEnum.cleaned
            )

            if not dataset:
                raise ValueError(f"Tuning experiment dataset with ID {tuning_experiment_dataset_id} not found.")

            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.geocoding
            )

            uploaded_rows = await self.tuning_experiment_uploaded_row_repository.get_uploaded_rows_by_tuning_experiment_dataset_id(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
            )

            total_rows = len(uploaded_rows)

            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            for batch_index, batch_start in enumerate(range(0, len(uploaded_rows), self.BATCH_SIZE), start=1):
                batch_rows = uploaded_rows[batch_start:batch_start + self.BATCH_SIZE]
                batch_results = await asyncio.gather(
                    *[self._geocode_single_row(row, semaphore) for row in batch_rows]
                )

                batch_success_rows: list[UpdateGeocodedTuningExperimentUploadedRowSchema] = [
                    UpdateGeocodedTuningExperimentUploadedRowSchema(
                        id=row["id"],
                        latitude=row.get("latitude"),
                        longitude=row.get("longitude"),
                        geocode_score=row.get("geocode_score"),
                        geocode_provider=row.get("geocode_provider"),
                        geocode_response=row.get("geocode_response")
                    ) 
                    for row in batch_results 
                    if row.get("status") == "success"
                ]
                
                if batch_success_rows:
                    await self.tuning_experiment_uploaded_row_repository.update_geocoded_rows(updated_rows=batch_success_rows)

                wide_event["batch_number"] = batch_index
                wide_event["batch_size"] = len(batch_rows)
                wide_event["total_rows"] = total_rows
                logger.info(wide_event)

            wide_event["status"] = "success"
            wide_event["total_rows"] = total_rows
            wide_event["progress_percentage"] = 100
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000

            logger.info(wide_event)
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.geocoded
            )
        except ValueError as e:
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.failed
            )
            wide_event["status"] = "failed"
            wide_event["error_type"] = "ValueError"
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise e
        except KeyError as e:
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.failed
            )
            wide_event["status"] = "failed"
            wide_event["error_type"] = "KeyError"
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise e
        except Exception as e:
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.failed
            )
            wide_event["status"] = "failed"
            wide_event["error_type"] = type(e).__name__
            wide_event["error_message"] = str(e)
            wide_event["traceback"] = traceback.format_exc()
            logger.error(wide_event)
            raise e
        
    async def _geocode_single_row(self, row: TuningExperimentUploadedRow, semaphore: asyncio.Semaphore) -> GeocodeRowResult:
        async with semaphore:
            if not row.final_address:
                return {
                    "id": row.id,
                    "status": "failed",
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
                            "status": "success",
                            "latitude": best_result["position"]["lat"],
                            "longitude": best_result["position"]["lon"],
                            "geocode_provider": "TomTom API",
                            "geocode_score": best_result.get("score"),
                            "geocode_response": json.dumps(geocode_result),
                        }
            
            return {
                "id": row.id,
                "status": "failed",
                "geocode_response": json.dumps(geocode_result),
            }