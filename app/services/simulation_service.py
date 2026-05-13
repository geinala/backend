# from app.models.node import GroupedNodeData, Node, NodeDetailCreate
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.services.minio_service import MinioService
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

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
    
    
    