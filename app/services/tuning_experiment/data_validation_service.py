import time as time_module
from datetime import datetime, timezone

from app.models.tuning_experiment_dataset import TuningExperimentDatasetStatusEnum
from app.repositories.tuning_experiment_dataset_repository import TuningExperimentDatasetRepository
from app.repositories.tuning_experiment_repository import TuningExperimentRepository
from app.schemas.tuning_experiment_uploaded_row_schema import CreateTuningExperimentUploadedRowSchema
from app.services.file_service import FileService
from app.services.minio_service import MinioService
from app.repositories.tuning_experiment_uploaded_row_repository import TuningExperimentUploadedRowRepository
from app.lib.logging.logging import get_logger
from app.models.error_report import ValidationError

logger = get_logger(__name__)

class TuningExperimentDataValidationService:
    def __init__(
        self,
        minio_service: MinioService,
        tuning_experiment_repository: TuningExperimentRepository,
        tuning_experiment_uploaded_row_repository: TuningExperimentUploadedRowRepository,
        tuning_experiment_dataset_repository: TuningExperimentDatasetRepository,
    ):
        self.minio_service = minio_service
        self.tuning_experiment_repository = tuning_experiment_repository
        self.tuning_experiment_uploaded_row_repository = tuning_experiment_uploaded_row_repository
        self.tuning_experiment_dataset_repository = tuning_experiment_dataset_repository

    async def run(self, tuning_experiment_dataset_id: str) -> dict[str, object] | None:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "tuning_validate_dataset",
            "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
            "status": "processing",
        }
        
        try:
            dataset = await self._get_dataset(tuning_experiment_dataset_id=tuning_experiment_dataset_id)
            
            if not dataset:
                wide_event["status"] = "failed"
                wide_event["error"] = "Dataset is empty or could not be retrieved"
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                return None
            
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.validating
            )
            
            field_names, rows = FileService.parse_csv_bytes(bytes(dataset))
            rows = self._deduplicate_rows_by_nosi(rows)
            
            valid_rows = await self._validate_csv_content(field_names=field_names, rows=rows, tuning_experiment_dataset_id=tuning_experiment_dataset_id)
            
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.validated
            ) 
            
            await self._store_uploaded_rows(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                rows=valid_rows,
            )
            
            wide_event["stored_rows"] = len(valid_rows)
            
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)
            
            return {
                "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
                "stored_rows": len(valid_rows),
            }
            
        except Exception as e:
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.failed
            )
            logger.error("Error occurred while processing files", extra={"tuning_experiment_dataset_id": tuning_experiment_dataset_id, "error": str(e)})
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            raise e
        
    async def _get_dataset(self, tuning_experiment_dataset_id: str) -> bytes | None:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "tuning_get_dataset",
            "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
            "status": "processing",
        }
        
        try:
            dataset = await self.tuning_experiment_dataset_repository.get_tuning_experiment_dataset_by_id_and_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                status=TuningExperimentDatasetStatusEnum.uploaded
            )
            
            if not dataset:
                wide_event["status"] = "failed"
                wide_event["error"] = "Dataset not found for the given ID"
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                return None
            
            file_data = await self.minio_service.download_file(
                object_name=str(dataset.dataset_file_path)
            )
            
            if not file_data:
                wide_event["status"] = "failed"
                wide_event["error"] = "Downloaded file is empty"
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                return None
            
            wide_event["status"] = "success"
            wide_event["file_size"] = len(file_data)
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

    async def _validate_csv_content(self, field_names: list[str], rows: list[dict[str, str]], tuning_experiment_dataset_id: str) -> list[dict[str, str]]:
        try:
            missing_fields = self._get_missing_required_fields(field_names)
            
            if missing_fields:
                raise ValueError(f"Missing required fields in header: {', '.join(missing_fields)}")
            
            valid_rows: list[dict[str, str]] = []
            
            for index, row in enumerate(rows):
                row_number = index + 2
                
                errors = self._validate_row(
                    row=row,
                    row_number=row_number,
                    tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                )
                
                if not errors:
                    valid_rows.append(row)
            
            return valid_rows
            
        except Exception as e:
            logger.error({
                "event_type": "csv_validation_error",
                "error": str(e),
                "error_type": type(e).__name__,
            })
            raise ValueError(f"Failed to validate CSV: {str(e)}")
        
    async def _store_uploaded_rows(
        self,
        tuning_experiment_dataset_id: str,
        rows: list[dict[str, str]],
    ) -> None:
        uploaded_rows: list[CreateTuningExperimentUploadedRowSchema] = []

        for _, row in enumerate(rows):
            nosi = self._get_row_value(row, "Nosi")
            courier = self._get_row_value(row, "Courier")
            customer_name = self._get_row_value(row, "Customer_Name")
            address = self._get_row_value(row, "Address")
            city = self._get_row_value(row, "City")
            weight_value = self._get_row_value(row, "Weight")
            start_datetime_value = self._get_row_value(row, "Start_Datetime")
            end_datetime_value = self._get_row_value(row, "End_Datetime")

            uploaded_rows.append(
                CreateTuningExperimentUploadedRowSchema(
                    tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                    nosi=nosi,
                    courier=courier,
                    customer_name=customer_name,
                    address=address,
                    city=city,
                    weight=self._parse_float(weight_value),
                    start_datetime=self._parse_datetime(start_datetime_value),
                    end_datetime=self._parse_datetime(end_datetime_value),
                    created_at=datetime.now(timezone.utc),
                )
            )

        await self.tuning_experiment_uploaded_row_repository.insert_uploaded_rows(rows=uploaded_rows)

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
        tuning_experiment_dataset_id: str,
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []

        # Required fields
        self._validate_required(row, "Nosi", row_number, tuning_experiment_dataset_id, errors)
        self._validate_required(row, "Courier", row_number, tuning_experiment_dataset_id, errors)
        self._validate_required(row, "Customer_Name", row_number, tuning_experiment_dataset_id, errors)
        self._validate_required(row, "Address", row_number, tuning_experiment_dataset_id, errors)
        self._validate_required(row, "City", row_number, tuning_experiment_dataset_id, errors)
        weight_str = self._validate_required(row, "Weight", row_number, tuning_experiment_dataset_id, errors)
        start_str = self._validate_required(row, "Start_Datetime", row_number, tuning_experiment_dataset_id, errors)
        end_str = self._validate_required(row, "End_Datetime", row_number, tuning_experiment_dataset_id, errors)

        # Weight validation
        weight = None
        if weight_str:
            weight = self._parse_float(weight_str)
            if weight is None:
                self._add_error(errors, row_number, "Weight", weight_str, "Weight must be a valid number", tuning_experiment_dataset_id)
            elif weight < 0:
                self._add_error(errors, row_number, "Weight", weight_str, "Weight cannot be negative", tuning_experiment_dataset_id)

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
                    tuning_experiment_dataset_id,
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
                    tuning_experiment_dataset_id,
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
                    tuning_experiment_dataset_id,
                )

        return errors

    def _add_error(
        self,
        errors: list[ValidationError],
        row_number: int,
        field: str,
        value: str | None,
        message: str,
        tuning_experiment_dataset_id: str,
    ) -> None:
        logger.error("Validation error occurred", extra={
            "event_type": "validation_error",
            "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
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
        tuning_experiment_id: str,
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
                tuning_experiment_id,
            )
            return None
        return value
    