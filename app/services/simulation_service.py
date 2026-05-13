import json
import re
import time as time_module
from datetime import datetime, timezone
from fastapi.exceptions import ValidationException

# from app.models.node import GroupedNodeData, Node, NodeDetailCreate
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.services.file_service import FileService
from app.services.minio_service import MinioService
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.lib.logging.logging import get_logger
from app.models.error_report import ValidationError, CSVValidationResult
from app.models.simulation_job import (
    SimulationJobStatusEnum,
    SimulationJobFileCleaningStatusEnum,
    SimulationJobFileValidationStatusEnum,
)
from app.schemas.simulation_job_schema import SimulationJobUpdateData
from app.schemas.simulation_job_uploaded_row_schema import CreateSimulationUploadedRowSchema

logger = get_logger(__name__)

ALIAS_MAP = {
    "jl": "jalan",
    "jln": "jalan",
    "perum": "perumahan",
    "gg": "gang",
    "resindence": "residence",
    "resindent": "residence",
    "resd": "residence",
    "la": "laksda",
    "lasucipto": "laksda adi sucipto",
    "pbi": "pondok blimbing indah",
    "r": "raden",
    "rp": "raden panji",
    "a": "ahmad",
    "jend": "jenderal",
    "per": "perumahan",
}

NOISE_WORDS = {
    "no", "nomor",
    "rt", "rw",
    "kel", "kelurahan",
    "kec", "kecamatan",
    "kota", "provinsi",
    "pagar", "kuning",
    "gang", "blok", "block",
    "rmh", "rumah",
    "blkg", "belakang",
    "toko", "ruko",
}

RESIDENTIAL_KEYWORDS = {
    "perumahan",
    "cluster",
    "residence",
    "estate",
    "graha",
}

STOP_AFTER_STREET = {
    "perumahan",
    "cluster",
    "residence",
    "estate",
    "graha",
}

BLOCK_PATTERN = re.compile(r"^[a-z]{1,2}\d+$", re.IGNORECASE)
HOUSE_TOKEN_PATTERN = re.compile(r"^(?:\d+[a-z]{0,2}|[a-z]{1,2}\d+[a-z]{0,2})$", re.IGNORECASE)
ROMAN_NUMERAL_PATTERN = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)

class SimulationService:
    def __init__(
        self,
        minio_service: MinioService,
        simulation_job_repository: SimulationJobRepository,
        simulation_uploaded_row_repository: SimulationUploadedRowRepository,
        node_repository: NodeRepository
    ):
        self.minio_service = minio_service
        self.node_repository = node_repository
        self.simulation_job_repository = simulation_job_repository
        self.simulation_uploaded_row_repository = simulation_uploaded_row_repository

    async def process_files(self, simulation_job_id: str):
        try:
            dataset = await self._get_dataset(simulation_job_id=simulation_job_id)
            fieldnames, rows = FileService.parse_csv_bytes(bytes(dataset))
            
            await self._validate_dataset(simulation_job_id=simulation_job_id, field_names=fieldnames, rows=rows)
            # await self._create_nodes_from_dataset(simulation_job_id=simulation_job_id, rows=rows)

            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    updated_at=datetime.now(timezone.utc),
                )
            )
            
        except Exception as e:
            logger.error("Error occurred while processing files", extra={"simulation_job_id": simulation_job_id, "error": str(e)})
            raise e

    async def clean_uploaded_rows(self, simulation_job_id: str) -> dict[str, object]:
        start_time = time_module.time()
        cleaning_started_at = datetime.now(timezone.utc)
        cleaning_started = False
        wide_event: dict[str, object] = {
            "event_type": "simulation_clean_uploaded_rows",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }

        try:
            simulation_job = await self.simulation_job_repository.get_simulation_job_by_id(simulation_job_id)

            if not simulation_job:
                raise ValidationException(errors=f"Simulation job with ID {simulation_job_id} not found.")

            if simulation_job.file_validation_status != SimulationJobFileValidationStatusEnum.completed:
                raise ValidationException(
                    errors=(
                        "Cleaning data can only be processed when "
                        f"file_validation_status is completed. Current status: {simulation_job.file_validation_status.value}"
                    )
                )

            uploaded_rows = await self.simulation_uploaded_row_repository.get_uploaded_rows_by_simulation_job_id(
                simulation_job_id=simulation_job_id
            )

            if not uploaded_rows:
                raise ValidationException(
                    errors=f"No uploaded rows found for simulation job {simulation_job_id}."
                )

            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    cleaning_status=SimulationJobFileCleaningStatusEnum.cleaning,
                    cleaning_started_at=cleaning_started_at,
                    cleaning_completed_at=None,
                    progress_cleaning_percentage=0,
                    updated_at=datetime.now(timezone.utc),
                ),
            )
            cleaning_started = True

            cleaned_rows: list[dict[str, object]] = []
            total_rows = len(uploaded_rows)
            progress_update_interval = max(1, total_rows // 20)  # ~5% granularity

            for index, row in enumerate(uploaded_rows, start=1):
                prepared = self._prepare_row_for_cleaning(
                    address=row.address,
                    city=row.city,
                )
                cleaned_rows.append(
                    {
                        "id": row.id,
                        "cleaned_address": prepared["cleaned"],
                        "street_candidate": prepared["street_candidate"],
                        "fallback": prepared["fallback"],
                        "final_address": prepared["query"],
                    }
                )

                if index % progress_update_interval == 0 or index == total_rows:
                    progress = int((index / total_rows) * 100)
                    await self.simulation_job_repository.update_simulation_job(
                        simulation_job_id=simulation_job_id,
                        update_data=SimulationJobUpdateData(
                            progress_cleaning_percentage=progress,
                            updated_at=datetime.now(timezone.utc),
                        ),
                    )

            await self.simulation_uploaded_row_repository.update_cleaned_rows(cleaned_rows=cleaned_rows)
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    cleaning_status=SimulationJobFileCleaningStatusEnum.completed,
                    cleaning_started_at=cleaning_started_at,
                    cleaning_completed_at=datetime.now(timezone.utc),
                    progress_cleaning_percentage=100,
                    updated_at=datetime.now(timezone.utc),
                )
            )

            wide_event["status"] = "success"
            wide_event["processed_rows"] = len(cleaned_rows)
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)

            return {
                "simulation_job_id": simulation_job_id,
                "processed_rows": len(cleaned_rows),
            }

        except Exception as e:
            if cleaning_started:
                await self.simulation_job_repository.update_simulation_job(
                    simulation_job_id=simulation_job_id,
                    update_data=SimulationJobUpdateData(
                        cleaning_status=SimulationJobFileCleaningStatusEnum.failed,
                        cleaning_completed_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    ),
                )
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.error(wide_event)
            raise

    async def _validate_dataset(self, simulation_job_id: str, field_names: list[str], rows: list[dict[str, str]]) -> dict[str, object]:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "simulation_validate_dataset",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }
        
        try:
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    status=SimulationJobStatusEnum.processing,
                    file_validation_status=SimulationJobFileValidationStatusEnum.validating,
                    validation_started_at=datetime.now(timezone.utc),
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
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.error(wide_event)
            raise

    # async def _create_nodes_from_dataset(self, simulation_job_id: str, rows: list[dict[str, str]]): 
    #     start_time = time_module.time()
    #     wide_event: dict[str, object] = {
    #         "event_type": "simulation_create_nodes",
    #         "simulation_job_id": simulation_job_id,
    #         "status": "processing",
    #     }
        
    #     try:
    #         grouped_nodes: dict[tuple[str, str], GroupedNodeData] = {}
    #         node_index_counter = 1 # start from 1 because index 0 is reserved for depot node
            
    #         await self.simulation_job_repository.update_simulation_job(
    #             simulation_job_id=simulation_job_id,
    #             update_data=SimulationJobUpdateData(
    #                 status=SimulationJobStatusEnum.processing,
    #             )
    #         )
            
    #         for row in rows:
    #             latitude = row.get("Customer_Latitude", "").strip()
    #             longitude = row.get("Customer_Longitude", "").strip()
    #             coord_key = (latitude, longitude)
                
    #             if coord_key not in grouped_nodes:
    #                 grouped_nodes[coord_key] = {
    #                     "latitude": float(latitude) if latitude else 0.0,
    #                     "longitude": float(longitude) if longitude else 0.0,
    #                     "total_demand": 0,
    #                     "matrix_index": node_index_counter,
    #                     "details": []
    #                 }
    #                 node_index_counter += 1
                
    #             try:
    #                 weight = float(row.get("Weight", "0").strip())
    #             except (ValueError, AttributeError):
    #                 weight = 0
                    
    #             logger.info({
    #                 "event_type": "processing_row",
    #                 "simulation_job_id": simulation_job_id,
    #                 "latitude": latitude,
    #                 "longitude": longitude,
    #                 "weight": weight,
    #             })
                
    #             grouped_nodes[coord_key]["total_demand"] += weight
                
    #             detail_dict: NodeDetailCreate = NodeDetailCreate(
    #                 name=row.get("Customer_Name", "").strip(),
    #                 address=row.get("Address", "").strip(),
    #                 city=row.get("City", "").strip(),
    #                 district=row.get("District", "").strip(),
    #                 weight=weight,
    #             )
    #             grouped_nodes[coord_key]["details"].append(detail_dict)
            
    #         grouped_data: list[tuple[Node, list[NodeDetailCreate]]] = []
            
    #         for grouped_node_data in grouped_nodes.values():
    #             details = grouped_node_data["details"]
                
    #             node = Node(
    #                 simulation_id=simulation_job_id,
    #                 latitude=grouped_node_data["latitude"],
    #                 longitude=grouped_node_data["longitude"],
    #                 demand=grouped_node_data["total_demand"],
    #                 is_depot=0,
    #                 matrix_index=grouped_node_data["matrix_index"],
    #             )
                
    #             grouped_data.append((node, details))
            
    #         self.node_repository.create_nodes_with_grouped_details(grouped_data=grouped_data)

    #         await self.simulation_job_repository.update_simulation_job(
    #             simulation_job_id=simulation_job_id,
    #             update_data=SimulationJobUpdateData(
    #                 total_nodes=len(grouped_data) + 1,
    #             )
    #         )
            
    #         wide_event["status"] = "success"
    #         wide_event["total_unique_nodes"] = len(grouped_data)
    #         wide_event["total_rows_processed"] = len(rows)
    #         wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
    #         logger.info(wide_event)
            
    #     except Exception as e:
    #         wide_event["status"] = "failed"
    #         wide_event["error"] = str(e)
    #         wide_event["error_type"] = type(e).__name__
    #         wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
    #         logger.error(wide_event)
            
    #         await self.simulation_job_repository.update_simulation_job(
    #             simulation_job_id=simulation_job_id,
    #             update_data=SimulationJobUpdateData(
    #                 status=SimulationJobStatusEnum.failed,
    #             )
    #         )
            
    #         raise

    async def _get_dataset(self, simulation_job_id: str) -> bytes:
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
                raise ValidationException(errors=f"Simulation job with ID {simulation_job_id} not found.")
            
            file_data = await self.minio_service.download_file(
                object_name=str(simulation_job.file_path)
            )
            
            if not file_data:
                wide_event["status"] = "failed"
                wide_event["error"] = "Downloaded file is empty"
                wide_event["file_path"] = simulation_job.file_path
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                raise ValidationException(errors=f"File {simulation_job.file_path} is empty for simulation job {simulation_job_id}.")
            
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
            raise
    
    async def _validate_csv_content(self, field_names: list[str], rows: list[dict[str, str]], simulation_job_id: str) -> CSVValidationResult:
        errors: list[ValidationError] = []
        row_count = 0

        try:
            # Check for missing required fields and add them as errors for each row
            missing_fields = self._get_missing_required_fields(field_names)
            
            total_rows = len(rows)
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    total_rows=total_rows,
                    processed_rows=0,
                    progress_percentage=0,
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
                            processed_rows=index,
                            progress_percentage=progress,
                            updated_at=datetime.now(timezone.utc)
                        )
                    )
                    
            invalid_row_count = len(set(e.row_number for e in errors))
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    progress_percentage=100,
                    processed_rows=total_rows,
                    invalid_rows=invalid_row_count,
                    valid_rows=row_count - invalid_row_count,
                    validation_completed_at=datetime.now(timezone.utc),
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
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    updated_at=datetime.now(timezone.utc),
                    file_validation_status=SimulationJobFileValidationStatusEnum.failed,
                    validation_completed_at=datetime.now(timezone.utc)
                )
            )
            raise ValueError(f"Failed to validate CSV: {str(e)}")
    
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
                    error_details=json.dumps(
                        [error.to_dict() for error in row_errors],
                        ensure_ascii=False,
                    ),
                    created_at=datetime.now(timezone.utc),
                )
            )

        await self.simulation_uploaded_row_repository.insert_uploaded_rows(rows=uploaded_rows)

    def _get_row_value(self, row: dict[str, str], field: str) -> str | None:
        value = (row.get(field) or "").strip()
        return value or None

    def _clean_text(self, text: str | None) -> str:
        if not text:
            return ""

        normalized = str(text).lower()
        normalized = re.sub(r"(\d+)/(\d+)", r"\1 \2", normalized)
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = [ALIAS_MAP.get(token, token) for token in normalized.split()]
        return " ".join(tokens)

    def _detect_address_type(self, text: str) -> str:
        tokens = text.split()

        if "jalan" in tokens:
            return "street"

        if any(token in RESIDENTIAL_KEYWORDS for token in tokens):
            return "residential"

        return "unknown"

    def _is_house_number(self, token: str) -> bool:
        return token.isdigit() or bool(HOUSE_TOKEN_PATTERN.match(token))

    def _is_block_code(self, token: str) -> bool:
        return bool(BLOCK_PATTERN.match(token))

    def _is_roman_numeral(self, token: str) -> bool:
        return bool(ROMAN_NUMERAL_PATTERN.match(token))

    def _extract_street_name(self, text: str) -> str:
        tokens = text.split()

        if "jalan" not in tokens:
            return ""

        start = tokens.index("jalan")
        result = ["jalan"]

        for token in tokens[start + 1:]:
            if token in NOISE_WORDS:
                break
            if token in STOP_AFTER_STREET:
                break
            if self._is_house_number(token):
                break
            if self._is_block_code(token):
                break
            if token == "gang":
                break

            result.append(token)

            if len(result) >= 7:
                break

        return " ".join(result)

    def _extract_city_fallback(self, city: str | None) -> str:
        if not city:
            return ""

        text = str(city).upper()
        if text.startswith("KOTA "):
            text = text[5:]

        parts = [part.strip().lower() for part in text.split(",") if part.strip()]
        parts.reverse()
        return " ".join(parts)

    def _prepare_row_for_cleaning(self, address: str | None, city: str | None, default_city: str = "malang") -> dict[str, str | None]:
        cleaned = self._clean_text(address)
        address_type = self._detect_address_type(cleaned)
        street = self._extract_street_name(cleaned)
        fallback = self._extract_city_fallback(city)

        filtered: list[str] = []
        for token in cleaned.split():
            if token in NOISE_WORDS:
                continue
            if self._is_house_number(token):
                continue
            if self._is_block_code(token):
                continue
            if self._is_roman_numeral(token):
                continue
            filtered.append(token)

        if address_type == "residential" and street:
            street_tokens = street.split()
            remainder = [token for token in filtered if token not in street_tokens]
            tokens = street_tokens + remainder
        else:
            tokens = filtered

        if fallback:
            for part in fallback.split():
                if part not in tokens:
                    tokens.append(part)

        query = " ".join(tokens).strip()
        if default_city not in query.split():
            query = f"{query} {default_city}".strip()

        street_candidate: str | None = None
        if address_type != "unknown":
            if street and fallback:
                street_candidate = f"{street} {fallback}".strip()
            elif street:
                street_candidate = street
            elif address_type == "residential" and query:
                street_candidate = query

        return {
            "cleaned": cleaned,
            "street_candidate": street_candidate,
            "fallback": fallback,
            "query": query,
        }

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
