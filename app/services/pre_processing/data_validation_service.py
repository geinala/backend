import json
import time as time_module
from datetime import datetime, timezone

from app.repositories.simulation_job_repository import SimulationJobRepository
from app.services.file_service import FileService
from app.services.minio_service import MinioService
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.lib.logging.logging import get_logger
from app.models.error_report import ValidationError
from app.schemas.error_report_schema import CSVValidationResult
from app.models.simulation_job import (
    SimulationJobStatusEnum,
    SimulationJobFileValidationStatusEnum,
)
from app.schemas.simulation_job_schema import SimulationJobUpdateData
from app.schemas.simulation_job_uploaded_row_schema import CreateSimulationUploadedRowSchema

logger = get_logger(__name__)

class DataValidationService:
    def __init__(
        self,
        minio_service: MinioService,
        simulation_job_repository: SimulationJobRepository,
        simulation_uploaded_row_repository: SimulationUploadedRowRepository
    ):
        self.minio_service = minio_service
        self.simulation_job_repository = simulation_job_repository
        self.simulation_uploaded_row_repository = simulation_uploaded_row_repository
        
    async def run(self, simulation_job_id: str) -> dict[str, object] | None:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "simulation_validate_dataset",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }
        
        try:
            dataset = await self._get_dataset(simulation_job_id=simulation_job_id)
            
            if not dataset:
                wide_event["status"] = "failed"
                wide_event["error"] = "Dataset is empty or could not be retrieved"
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                return
            
            field_names, rows = FileService.parse_csv_bytes(bytes(dataset))
            rows = self._deduplicate_rows_by_nosi(rows)
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    status=SimulationJobStatusEnum.processing,
                    file_validation_status=SimulationJobFileValidationStatusEnum.validating,
                    file_validation_started_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
            )
            
            errors = await self._validate_csv_content(field_names=field_names, rows=rows, simulation_job_id=simulation_job_id)
            await self._store_uploaded_rows(
                simulation_job_id=simulation_job_id,
                rows=rows,
                errors=errors["errors"],
            )
            
            wide_event["total_rows"] = errors["row_count"]
            wide_event["error_count"] = len(errors["errors"])
            wide_event["stored_rows"] = len(rows)
            
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)
            
            return {
                "simulation_job_id": simulation_job_id,
                "total_rows": errors["row_count"],
                "error_count": len(errors["errors"]),
                "is_valid": len(errors["errors"]) == 0,
                "stored_rows": len(rows),
            }
            
        except Exception as e:
            logger.error("Error occurred while processing files", extra={"simulation_job_id": simulation_job_id, "error": str(e)})
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    status=SimulationJobStatusEnum.failed,
                    updated_at=datetime.now(timezone.utc),
                    file_validation_status=SimulationJobFileValidationStatusEnum.failed,
                )
            )
            raise e
        
    async def _get_dataset(self, simulation_job_id: str) -> bytes | None:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "simulation_get_dataset",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }
        
        try:
            simulation_job = await self.simulation_job_repository.get_simulation_job_by_id(simulation_job_id)
            
            if not simulation_job:
                wide_event["status"] = "failed"
                wide_event["error"] = f"Simulation job not found"
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                return
            
            file_data = await self.minio_service.download_file(
                object_name=str(simulation_job.file_path)
            )
            
            if not file_data:
                wide_event["status"] = "failed"
                wide_event["error"] = "Downloaded file is empty"
                wide_event["file_path"] = simulation_job.file_path
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                return
            
            wide_event["status"] = "success"
            wide_event["file_size"] = len(file_data)
            wide_event["file_path"] = simulation_job.file_path
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)
            
            return file_data
            
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.error(wide_event)
            raise e

    async def _validate_csv_content(self, field_names: list[str], rows: list[dict[str, str]], simulation_job_id: str) -> CSVValidationResult:
        errors: list[ValidationError] = []
        row_count = 0

        try:
            missing_fields = self._get_missing_required_fields(field_names)
            
            total_rows = len(rows)
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    file_processed_rows=0,
                    file_progress_percentage=0,
                )
            )
            
            if missing_fields:
                for index, row in enumerate(rows):
                    row_number = index + 2 
                    for field in missing_fields:
                        errors.append(
                            ValidationError(
                                row_number=row_number,
                                field_name=field,
                                invalid_value="[field not found in CSV]",
                                error_message=f"{field} is a required field but not found in CSV header",
                            )
                        )
            
            for index, row in enumerate(rows):
                row_number = index + 2
                row_count += 1
                
                if not missing_fields:
                    row_errors = self._validate_row(
                        row=row,
                        row_number=row_number,
                        simulation_job_id=simulation_job_id,
                    )
                    errors.extend(row_errors)

                if total_rows > 0 and index % 50 == 0:
                    progress = int((index / total_rows) * 100)
                    
                    await self.simulation_job_repository.update_simulation_job(
                        simulation_job_id=simulation_job_id,
                        update_data=SimulationJobUpdateData(
                            file_processed_rows=index,
                            file_progress_percentage=progress,
                            updated_at=datetime.now(timezone.utc)
                        )
                    )
                    
            invalid_row_count = len(set(e.row_number for e in errors))
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    file_progress_percentage=100,
                    file_invalid_rows=invalid_row_count,
                    file_valid_rows=row_count - invalid_row_count,
                    file_validation_completed_at=datetime.now(timezone.utc),
                    file_validation_status=(
                        SimulationJobFileValidationStatusEnum.completed
                        if invalid_row_count == 0
                        else SimulationJobFileValidationStatusEnum.needed_review
                    ),
                    updated_at=datetime.now(timezone.utc),
                    current_step=1 if invalid_row_count > 0 else 2,
                )
            )
            
            return {
                "errors": errors,
                "row_count": row_count,
                "invalid_row_count": invalid_row_count,
            }
            
        except Exception as e:
            logger.error({
                "event_type": "csv_validation_error",
                "error": str(e),
                "error_type": type(e).__name__,
            })
            raise ValueError(f"Failed to validate CSV: {str(e)}")
        
    async def _store_uploaded_rows(
        self,
        simulation_job_id: str,
        rows: list[dict[str, str]],
        errors: list[ValidationError],
    ) -> None:
        errors_by_row: dict[int, list[ValidationError]] = {}
        for error in errors:
            errors_by_row.setdefault(error.row_number, []).append(error)

        uploaded_rows: list[CreateSimulationUploadedRowSchema] = []

        for index, row in enumerate(rows):
            row_number = index + 2
            row_errors = errors_by_row.get(row_number, [])
            nosi = self._get_row_value(row, "Nosi")
            courier = self._get_row_value(row, "Courier")
            customer_name = self._get_row_value(row, "Customer_Name")
            address = self._get_row_value(row, "Address")
            city = self._get_row_value(row, "City")
            weight_value = self._get_row_value(row, "Weight")
            start_datetime_value = self._get_row_value(row, "Start_Datetime")
            end_datetime_value = self._get_row_value(row, "End_Datetime")

            uploaded_rows.append(
                CreateSimulationUploadedRowSchema(
                    simulation_job_id=simulation_job_id,
                    nosi=nosi,
                    courier=courier,
                    customer_name=customer_name,
                    address=address,
                    city=city,
                    weight=self._parse_float(weight_value),
                    start_datetime=self._parse_datetime(start_datetime_value),
                    end_datetime=self._parse_datetime(end_datetime_value),
                    error_details=(
                        json.dumps(
                            [error.to_dict() for error in row_errors],
                            ensure_ascii=False,
                        )
                        if row_errors
                        else None
                    ),
                    created_at=datetime.now(timezone.utc),
                )
            )

        await self.simulation_uploaded_row_repository.insert_uploaded_rows(rows=uploaded_rows)

    def _get_row_value(self, row: dict[str, str], field: str) -> str | None:
        value = (row.get(field) or "").strip()
        return value or None

    def _parse_float(self, value: str | None) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except ValueError:
            return None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if value is None:
            return None

        # ISO 8601
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        formats = [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    def _validate_row(
        self,
        row: dict[str, str],
        row_number: int,
        simulation_job_id: str,
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []

        # Required fields
        self._validate_required(row, "Nosi", row_number, simulation_job_id, errors)
        self._validate_required(row, "Courier", row_number, simulation_job_id, errors)
        self._validate_required(row, "Customer_Name", row_number, simulation_job_id, errors)
        self._validate_required(row, "Address", row_number, simulation_job_id, errors)
        self._validate_required(row, "City", row_number, simulation_job_id, errors)
        weight_str = self._validate_required(row, "Weight", row_number, simulation_job_id, errors)
        start_str = self._validate_required(row, "Start_Datetime", row_number, simulation_job_id, errors)
        end_str = self._validate_required(row, "End_Datetime", row_number, simulation_job_id, errors)

        # Weight validation
        weight = None
        if weight_str:
            weight = self._parse_float(weight_str)
            if weight is None:
                self._add_error(errors, row_number, "Weight", weight_str, "Weight must be a valid number", simulation_job_id)
            elif weight < 0:
                self._add_error(errors, row_number, "Weight", weight_str, "Weight cannot be negative", simulation_job_id)

        # Datetime validation
        start_dt = None
        end_dt = None

        if start_str:
            start_dt = self._parse_datetime(start_str)
            if not start_dt:
                self._add_error(
                    errors,
                    row_number,
                    "Start_Datetime",
                    start_str,
                    "Invalid format (ISO 8601 or DD/MM/YYYY HH:MM[:SS])",
                    simulation_job_id,
                )

        if end_str:
            end_dt = self._parse_datetime(end_str)
            if not end_dt:
                self._add_error(
                    errors,
                    row_number,
                    "End_Datetime",
                    end_str,
                    "Invalid format (ISO 8601 or DD/MM/YYYY HH:MM[:SS])",
                    simulation_job_id,
                )

        # Cross-field validation
        if start_dt and end_dt:
            if start_dt > end_dt:
                self._add_error(
                    errors,
                    row_number,
                    "Start_Datetime",
                    start_str or "",
                    "Start_Datetime must be earlier than End_Datetime",
                    simulation_job_id,
                )

        return errors

    def _add_error(
        self,
        errors: list[ValidationError],
        row_number: int,
        field: str,
        value: str | None,
        message: str,
        simulation_job_id: str,
    ) -> None:
        logger.error("Validation error occurred", extra={
            "event_type": "validation_error",
            "simulation_job_id": simulation_job_id,
            "row_number": row_number,
            "field_name": field,
            "invalid_value": value or "",
            "error_message": message,
        })

        errors.append(
            ValidationError(
                row_number=row_number,
                field_name=field,
                invalid_value=value or "",
                error_message=message,
            )
        )

    def _get_missing_required_fields(self, fieldnames: list[str]) -> set[str]:
        REQUIRED_FIELDS = {
            "Nosi",
            "Courier",
            "Customer_Name",
            "Address",
            "City",
            "Weight",
            "Start_Datetime",
            "End_Datetime",
        }

        return REQUIRED_FIELDS - set(fieldnames or [])

    @staticmethod
    def _deduplicate_rows_by_nosi(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        unique_rows: list[dict[str, str]] = []
        seen_nosi: set[str] = set()

        for row in rows:
            nosi = (row.get("Nosi") or "").strip()

            if not nosi:
                unique_rows.append(row)
                continue

            if nosi in seen_nosi:
                continue

            seen_nosi.add(nosi)
            unique_rows.append(row)

        return unique_rows

    def _validate_required(
        self,
        row: dict[str, str],
        field: str,
        row_number: int,
        simulation_job_id: str,
        errors: list[ValidationError],
    ) -> str | None:
        value = (row.get(field) or "").strip()
        if not value:
            self._add_error(
                errors,
                row_number,
                field,
                "[empty]",
                f"{field} is required and cannot be empty",
                simulation_job_id,
            )
            return None
        return value
    