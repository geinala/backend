from datetime import datetime, timezone
import time as time_module
from fastapi.exceptions import ValidationException

from app.models.node import GroupedNodeData, Node, NodeDetailCreate
from app.models.simulation import SimulationUploadedFileUpdateData, SimulationUploadedFileStatusEnum
from app.services.file_service import FileService
from app.services.minio_service import MinioService
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.node_repository import NodeRepository
from app.lib.logging.logging import get_logger
from app.models.error_report import ValidationError, CSVValidationResult

logger = get_logger(__name__)


class SimulationService:
    def __init__(
        self,
        minio_service: MinioService,
        simulation_repository: SimulationRepository,
        node_repository: NodeRepository
    ):
        self.minio_service = minio_service
        self.simulation_repository = simulation_repository
        self.node_repository = node_repository

    async def process_files(self, simulation_id: str):
        try:
            dataset = await self._get_dataset(simulation_id)
            fieldnames, rows = FileService.parse_csv_bytes(bytes(dataset["file_data"]))
            uploaded_file_id: int = int(dataset["uploaded_file_id"])
            
            await self._validate_dataset(simulation_id=simulation_id, uploaded_file_id=uploaded_file_id, fieldnames=fieldnames, rows=rows)
            await self._create_nodes_from_dataset(simulation_id=simulation_id, uploaded_file_id=uploaded_file_id, rows=rows)
            
            await self.simulation_repository.update_simulation_uploaded_file(
                id=uploaded_file_id,
                uploaded_file=SimulationUploadedFileUpdateData(
                    status=SimulationUploadedFileStatusEnum.ready,
                )
            )
            
        except Exception as e:
            raise e

    async def _validate_dataset(self, simulation_id: str, uploaded_file_id: int, fieldnames: list[str], rows: list[dict[str, str]]) -> dict[str, object]:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "simulation_validate_dataset",
            "simulation_id": simulation_id,
            "status": "processing",
        }
        
        try:
            await self.simulation_repository.update_simulation_uploaded_file(
                id=uploaded_file_id,
                uploaded_file=SimulationUploadedFileUpdateData(
                    status=SimulationUploadedFileStatusEnum.validating,
                    validated_at=datetime.now(timezone.utc)
                )
            )
            
            errors = await self._validate_csv_content(fieldnames=fieldnames, rows=rows, uploaded_file_id=uploaded_file_id)
            
            wide_event["total_rows"] = errors["row_count"]
            wide_event["error_count"] = len(errors["errors"])
            
            error_report_path = f"error-reports/simulation-{simulation_id}-errors.csv"
            
            if errors["errors"]:
                csv_content = FileService.create_error_report_csv(errors=errors["errors"])
                
                await self.minio_service.upload_file(
                    object_name=error_report_path,
                    file_data=csv_content,
                    content_type='text/csv',
                )
                
                wide_event["error_report_path"] = error_report_path
                
            await self.simulation_repository.update_simulation_uploaded_file(
                id=uploaded_file_id,
                uploaded_file=SimulationUploadedFileUpdateData(
                    file_error_path=error_report_path if errors["errors"] else None,
                )
            )
            
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)
            
            return {
                "simulation_id": simulation_id,
                "total_rows": errors["row_count"],
                "error_count": len(errors["errors"]),
                "is_valid": len(errors["errors"]) == 0,
                "error_report_path": error_report_path if errors["errors"] else None,
            }
            
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.error(wide_event)
            raise

    async def _create_nodes_from_dataset(self, simulation_id: str, uploaded_file_id: int, rows: list[dict[str, str]]): 
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "simulation_create_nodes",
            "simulation_id": simulation_id,
            "status": "processing",
        }
        
        try:
            grouped_nodes: dict[tuple[str, str], GroupedNodeData] = {}
            node_index_counter = 1 # start from 1 because index 0 is reserved for depot node
            
            await self.simulation_repository.update_simulation_uploaded_file(
                id=uploaded_file_id,
                uploaded_file=SimulationUploadedFileUpdateData(
                    status=SimulationUploadedFileStatusEnum.processing,
                )
            )
            
            for row in rows:
                latitude = row.get("Customer_Latitude", "").strip()
                longitude = row.get("Customer_Longitude", "").strip()
                coord_key = (latitude, longitude)
                
                if coord_key not in grouped_nodes:
                    grouped_nodes[coord_key] = {
                        "latitude": float(latitude) if latitude else 0.0,
                        "longitude": float(longitude) if longitude else 0.0,
                        "total_demand": 0,
                        "matrix_index": node_index_counter,
                        "details": []
                    }
                    node_index_counter += 1
                
                try:
                    weight = float(row.get("Weight", "0").strip())
                except (ValueError, AttributeError):
                    weight = 0
                    
                logger.info({
                    "event_type": "processing_row",
                    "simulation_id": simulation_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    "weight": weight,
                })
                
                grouped_nodes[coord_key]["total_demand"] += weight
                
                detail_dict: NodeDetailCreate = NodeDetailCreate(
                    name=row.get("Customer_Name", "").strip(),
                    address=row.get("Address", "").strip(),
                    city=row.get("City", "").strip(),
                    district=row.get("District", "").strip(),
                    weight=weight,
                )
                grouped_nodes[coord_key]["details"].append(detail_dict)
            
            grouped_data: list[tuple[Node, list[NodeDetailCreate]]] = []
            
            for grouped_node_data in grouped_nodes.values():
                details = grouped_node_data["details"]
                
                node = Node(
                    simulation_id=simulation_id,
                    latitude=grouped_node_data["latitude"],
                    longitude=grouped_node_data["longitude"],
                    demand=grouped_node_data["total_demand"],
                    is_depot=0,
                    matrix_index=grouped_node_data["matrix_index"],
                )
                
                grouped_data.append((node, details))
            
            self.node_repository.create_nodes_with_grouped_details(grouped_data=grouped_data)
            
            wide_event["status"] = "success"
            wide_event["total_unique_nodes"] = len(grouped_data)
            wide_event["total_rows_processed"] = len(rows)
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)
            
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.error(wide_event)
            
            await self.simulation_repository.update_simulation_uploaded_file(
                id=uploaded_file_id,
                uploaded_file=SimulationUploadedFileUpdateData(
                    status=SimulationUploadedFileStatusEnum.failed,
                )
            )
            
            raise

    async def _get_dataset(self, simulation_id: str) -> dict[str, bytes | int]:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "simulation_get_dataset",
            "simulation_id": simulation_id,
            "status": "processing",
        }
        
        try:
            simulation = await self.simulation_repository.get_simulation_by_id(simulation_id)
            
            if not simulation:
                wide_event["status"] = "failed"
                wide_event["error"] = f"Simulation not found"
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                raise ValidationException(errors=f"Simulation with ID {simulation_id} not found.")
            
            upload_file_id: int | None = simulation.upload_id
            if not bool(upload_file_id):
                wide_event["status"] = "failed"
                wide_event["error"] = "No upload_id associated with simulation"
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                raise ValidationException(errors=f"Simulation {simulation_id} has no associated uploaded file.")
            
            uploaded_file = await self.simulation_repository.get_simulation_uploaded_file_by_id(
                uploaded_file_id=upload_file_id
            )

            if not uploaded_file:
                wide_event["status"] = "failed"
                wide_event["error"] = f"Uploaded file not found"
                wide_event["upload_file_id"] = upload_file_id
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                raise ValidationException(errors=f"Uploaded file with ID {upload_file_id} not found for simulation {simulation_id}.")
            
            file_data = await self.minio_service.download_file(
                object_name=str(uploaded_file.file_path)
            )
            
            if not file_data:
                wide_event["status"] = "failed"
                wide_event["error"] = "Downloaded file is empty"
                wide_event["file_path"] = uploaded_file.file_path
                wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
                logger.error(wide_event)
                raise ValidationException(errors=f"File {uploaded_file.file_path} is empty for simulation {simulation_id}.")
            
            wide_event["status"] = "success"
            wide_event["file_size"] = len(file_data)
            wide_event["file_path"] = uploaded_file.file_path
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)
            
            return {
                "file_data": file_data,
                "uploaded_file_id": int(upload_file_id),
            }
            
        except Exception as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.error(wide_event)
            raise
    
    async def _validate_csv_content(self, fieldnames: list[str], rows: list[dict[str, str]], uploaded_file_id: int) -> CSVValidationResult:
        errors: list[ValidationError] = []
        row_count = 0

        try:
            # Check for missing required fields and add them as errors for each row
            missing_fields = self._get_missing_required_fields(fieldnames)
            
            total_rows = len(rows)
            
            await self.simulation_repository.update_simulation_uploaded_file(
                id=uploaded_file_id,
                uploaded_file=SimulationUploadedFileUpdateData(
                    total_rows=total_rows,
                    progress_percentage=0,
                    processed_rows=0,
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
                    row_errors = self._validate_row(row, row_number)
                    errors.extend(row_errors)

                if total_rows > 0 and index % 50 == 0:
                    progress = int((index / total_rows) * 100)
                    
                    await self.simulation_repository.update_simulation_uploaded_file(
                        id=uploaded_file_id,
                        uploaded_file=SimulationUploadedFileUpdateData(
                            progress_percentage=progress,
                            processed_rows=index,
                        )
                    )
                    
            invalid_row_count = len(set(e.row_number for e in errors))
            
            final_status = (
                SimulationUploadedFileStatusEnum.failed
                if invalid_row_count > 0
                else SimulationUploadedFileStatusEnum.validated
            )
            
            await self.simulation_repository.update_simulation_uploaded_file(
                id=uploaded_file_id,
                uploaded_file=SimulationUploadedFileUpdateData(
                    progress_percentage=100,
                    processed_rows=total_rows,
                    invalid_rows=invalid_row_count,
                    status=final_status,
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
            await self.simulation_repository.update_simulation_uploaded_file(
                id=uploaded_file_id,
                uploaded_file=SimulationUploadedFileUpdateData(
                    status=SimulationUploadedFileStatusEnum.failed,
                )
            )
            raise ValueError(f"Failed to validate CSV: {str(e)}")
    
    def _get_missing_required_fields(self, fieldnames: list[str]) -> set[str]:
        required_fields = {
            "Customer_Name",
            "Customer_Latitude",
            "Customer_Longitude",
            "Weight",
            "Address",
            "District",
            "City"
        }

        return required_fields - set(fieldnames or [])

    def _validate_row(
        self,
        row: dict[str, str],
        row_number: int,
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []

        # Customer_Name
        if not row.get("Customer_Name", "").strip():
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Customer_Name",
                    invalid_value="[empty]",
                    error_message="Customer_Name is required and cannot be empty",
                )
            )

        # Latitude
        try:
            latitude = float(row.get("Customer_Latitude", "").strip())
            if not (-90 <= latitude <= 90):
                errors.append(
                    ValidationError(
                        row_number=row_number,
                        field_name="Customer_Latitude",
                        invalid_value=str(latitude),
                        error_message="Latitude must be between -90 and 90 degrees",
                    )
                )
        except (ValueError, AttributeError):
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Customer_Latitude",
                    invalid_value=row.get("Customer_Latitude", "[empty]"),
                    error_message="Customer_Latitude must be a valid number",
                )
            )

        # Longitude
        try:
            longitude = float(row.get("Customer_Longitude", "").strip())
            if not (-180 <= longitude <= 180):
                errors.append(
                    ValidationError(
                        row_number=row_number,
                        field_name="Customer_Longitude",
                        invalid_value=str(longitude),
                        error_message="Longitude must be between -180 and 180 degrees",
                    )
                )
        except (ValueError, AttributeError):
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Customer_Longitude",
                    invalid_value=row.get("Customer_Longitude", "[empty]"),
                    error_message="Customer_Longitude must be a valid number",
                )
            )
            
        # Address
        if not row.get("Address", "").strip():
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Address",
                    invalid_value="[empty]",
                    error_message="Address is required and cannot be empty",
                )
            )
            
        # District
        if not row.get("District", "").strip():
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="District",
                    invalid_value="[empty]",
                    error_message="District is required and cannot be empty",
                )
            )
            
        # City
        if not row.get("City", "").strip():
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="City",
                    invalid_value="[empty]",
                    error_message="City is required and cannot be empty",
                )
            )

        # Weight
        try:
            weight = float(row.get("Weight", "").strip())
            if weight <= 0:
                errors.append(
                    ValidationError(
                        row_number=row_number,
                        field_name="Weight",
                        invalid_value=str(weight),
                        error_message="Weight must be a positive number",
                    )
                )
        except (ValueError, AttributeError):
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Weight",
                    invalid_value=row.get("Weight", "[empty]"),
                    error_message="Weight must be a valid positive number",
                )
            )

        return errors