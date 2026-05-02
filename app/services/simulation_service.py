import time as time_module
from datetime import datetime, timezone 
from fastapi.exceptions import ValidationException

# from app.models.node import GroupedNodeData, Node, NodeDetailCreate
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.services.file_service import FileService
from app.services.minio_service import MinioService
from app.repositories.node_repository import NodeRepository
from app.lib.logging.logging import get_logger
from app.models.error_report import ValidationError, CSVValidationResult
from app.models.simulation_job import SimulationJobStatusEnum, SimulationJobFileValidationStatusEnum
from app.schemas.simulation_job_schema import SimulationJobUpdateData
from app.schemas.simulation_job_uploaded_file_error_schema import SimulationJobUploadedFileErrorCreate
from app.repositories.simulation_job_uploaded_file_error_repository import SimulationJobUploadedFileErrorRepository

logger = get_logger(__name__)

class SimulationService:
    def __init__(
        self,
        minio_service: MinioService,
        simulation_job_repository: SimulationJobRepository,
        simulation_job_uploaded_file_error_repository: SimulationJobUploadedFileErrorRepository,
        node_repository: NodeRepository
    ):
        self.minio_service = minio_service
        self.node_repository = node_repository
        self.simulation_job_repository = simulation_job_repository
        self.simulation_job_uploaded_file_error_repository = simulation_job_uploaded_file_error_repository

    async def process_files(self, simulation_job_id: str):
        try:
            dataset = await self._get_dataset(simulation_job_id=simulation_job_id)
            fieldnames, rows = FileService.parse_csv_bytes(bytes(dataset))
            
            await self._validate_dataset(simulation_job_id=simulation_job_id, field_names=fieldnames, rows=rows)
            # await self._create_nodes_from_dataset(simulation_job_id=simulation_job_id, rows=rows)
            
        except Exception as e:
            raise e

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
            
            wide_event["total_rows"] = errors["row_count"]
            wide_event["error_count"] = len(errors["errors"])
            
            error_report_path = f"error-reports/simulation-{simulation_job_id}-errors.csv"
            
            if errors["errors"]:
                error_reports: list[SimulationJobUploadedFileErrorCreate] = [
                    SimulationJobUploadedFileErrorCreate(
                        simulation_job_id=simulation_job_id,
                        row_number=err.row_number,
                        error_message=err.error_message,
                        created_at=datetime.now(timezone.utc),
                        field_name=err.field_name,
                        invalid_value=err.invalid_value,
                    )
                    for err in errors["errors"]
                ]
                
                await self.simulation_job_uploaded_file_error_repository.insert_uploaded_file_errors(
                    errors=error_reports
                )
                
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)
            
            return {
                "simulation_job_id": simulation_job_id,
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
            
            final_status = (
                SimulationJobStatusEnum.failed
                if invalid_row_count > 0
                else SimulationJobStatusEnum.processing
            )
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    progress_percentage=100,
                    processed_rows=total_rows,
                    invalid_rows=invalid_row_count,
                    valid_rows=row_count - invalid_row_count,
                    status=final_status,
                    file_validation_status=SimulationJobFileValidationStatusEnum.validated if invalid_row_count == 0 else SimulationJobFileValidationStatusEnum.failed,
                    updated_at=datetime.now(timezone.utc),
                    validation_completed_at=datetime.now(timezone.utc)
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
                    status=SimulationJobStatusEnum.failed,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            raise ValueError(f"Failed to validate CSV: {str(e)}")
    
    def _get_missing_required_fields(self, fieldnames: list[str]) -> set[str]:
        required_fields = {
            "Nosi",
            "Courier",
            "Customer_Name",
            "Address",
            "City",
            "Weight",
            "Start_Datetime",
            "End_Datetime",
        }

        return required_fields - set(fieldnames or [])

    def _validate_row(
        self,
        row: dict[str, str],
        row_number: int,
        simulation_job_id: str,
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []

        # Nosi
        if not row.get("Nosi", "").strip():
            logger.info({
                "event_type": "validation_error",
                "simulation_job_id": simulation_job_id,
                "row_number": row_number,
                "field_name": "Nosi",
                "invalid_value": "[empty]",
                "error_message": "Nosi is required and cannot be empty",
            })
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Nosi",
                    invalid_value="[empty]",
                    error_message="Nosi is required and cannot be empty",
                )
            )

        # Courier
        if not row.get("Courier", "").strip():
            logger.info({
                "event_type": "validation_error",
                "simulation_job_id": simulation_job_id,
                "row_number": row_number,
                "field_name": "Courier",
                "invalid_value": "[empty]",
                "error_message": "Courier is required and cannot be empty",
            })
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Courier",
                    invalid_value="[empty]",
                    error_message="Courier is required and cannot be empty",
                )
            )
            
        # Customer_Name
        if not row.get("Customer_Name", "").strip():
            logger.info({
                "event_type": "validation_error",
                "simulation_job_id": simulation_job_id,
                "row_number": row_number,
                "field_name": "Customer_Name",
                "invalid_value": "[empty]",
                "error_message": "Customer_Name is required and cannot be empty",
            })
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Customer_Name",
                    invalid_value="[empty]",
                    error_message="Customer_Name is required and cannot be empty",
                )
            )
            
        # Address
        if not row.get("Address", "").strip():
            logger.info({
                "event_type": "validation_error",
                "simulation_job_id": simulation_job_id,
                "row_number": row_number,
                "field_name": "Address",
                "invalid_value": "[empty]",
                "error_message": "Address is required and cannot be empty",
            })
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Address",
                    invalid_value="[empty]",
                    error_message="Address is required and cannot be empty",
                )
            )
            
        # City
        if not row.get("City", "").strip():
            logger.info({
                "event_type": "validation_error",
                "simulation_job_id": simulation_job_id,
                "row_number": row_number,
                "field_name": "City",
                "invalid_value": "[empty]",
                "error_message": "City is required and cannot be empty",
            })
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="City",
                    invalid_value="[empty]",
                    error_message="City is required and cannot be empty",
                )
            )
            
        # Weight
        weight_str = row.get("Weight", "").strip()
        if not weight_str:
            logger.info({
                "event_type": "validation_error",
                "simulation_job_id": simulation_job_id,
                "row_number": row_number,
                "field_name": "Weight",
                "invalid_value": "[empty]",
                "error_message": "Weight is required and cannot be empty",
            })
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Weight",
                    invalid_value="[empty]",
                    error_message="Weight is required and cannot be empty",
                )
            )
        else:
            try:
                weight = float(weight_str)
                if weight < 0:
                    logger.info({
                        "event_type": "validation_error",
                        "simulation_job_id": simulation_job_id,
                        "row_number": row_number,
                        "field_name": "Weight",
                        "invalid_value": weight_str,
                        "error_message": "Weight cannot be negative",
                    })
                    errors.append(
                        ValidationError(
                            row_number=row_number,
                            field_name="Weight",
                            invalid_value=weight_str,
                            error_message="Weight cannot be negative",
                        )
                    )
            except ValueError:
                logger.info({
                    "event_type": "validation_error",
                    "simulation_job_id": simulation_job_id,
                    "row_number": row_number,
                    "field_name": "Weight",                    "invalid_value": weight_str,
                    "error_message": "Weight must be a valid number",
                })
                errors.append(
                    ValidationError(
                        row_number=row_number,
                        field_name="Weight",
                        invalid_value=weight_str,
                        error_message="Weight must be a valid number",
                    )
                )
                
        # Start_Datetime
        start_datetime_str = row.get("Start_Datetime", "").strip()
        if not start_datetime_str:  
            logger.info({
                    "event_type": "validation_error",
                    "simulation_job_id": simulation_job_id,
                    "row_number": row_number,
                    "field_name": "Start_Datetime",
                    "invalid_value": "[empty]",
                    "error_message": "Start_Datetime is required and cannot be empty",
                })
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="Start_Datetime",
                    invalid_value="[empty]",
                    error_message="Start_Datetime is required and cannot be empty",
                )
            )
        else:
            if not self._is_valid_datetime(start_datetime_str):
                logger.info({
                    "event_type": "validation_error",
                    "simulation_job_id": simulation_job_id,
                    "row_number": row_number,
                    "field_name": "Start_Datetime",
                    "invalid_value": start_datetime_str,
                    "error_message": "Start_Datetime must be in valid format (ISO 8601 or DD/MM/YYYY HH:MM:SS)",
                })
                errors.append(
                    ValidationError(
                        row_number=row_number,
                        field_name="Start_Datetime",
                        invalid_value=start_datetime_str,
                        error_message="Start_Datetime must be in valid format (ISO 8601 or DD/MM/YYYY HH:MM:SS)",
                    )
                )
                
        # End_Datetime
        end_datetime_str = row.get("End_Datetime", "").strip()
        if not end_datetime_str:
            logger.info({
                "event_type": "validation_error",
                "simulation_job_id": simulation_job_id,
                "row_number": row_number,
                "field_name": "End_Datetime",
                "invalid_value": "[empty]",
                "error_message": "End_Datetime is required and cannot be empty",
            })
            errors.append(
                ValidationError(
                    row_number=row_number,
                    field_name="End_Datetime",
                    invalid_value="[empty]",
                    error_message="End_Datetime is required and cannot be empty",
                )
            )
        else:
            if not self._is_valid_datetime(end_datetime_str):
                logger.info({
                    "event_type": "validation_error",
                    "simulation_job_id": simulation_job_id,
                    "row_number": row_number,
                    "field_name": "End_Datetime",
                    "invalid_value": end_datetime_str,
                    "error_message": "End_Datetime must be in valid format (ISO 8601 or DD/MM/YYYY HH:MM:SS)",
                })
                errors.append(
                    ValidationError(
                        row_number=row_number,
                        field_name="End_Datetime",
                        invalid_value=end_datetime_str,
                        error_message="End_Datetime must be in valid format (ISO 8601 or DD/MM/YYYY HH:MM:SS)",
                    )
                )
        

        return errors

    def _is_valid_datetime(self, datetime_value: str) -> bool:
        try:
            datetime.fromisoformat(datetime_value)
            return True
        except ValueError:
            pass

        accepted_formats = [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
        ]

        for datetime_format in accepted_formats:
            try:
                datetime.strptime(datetime_value, datetime_format)
                return True
            except ValueError:
                continue

        return False