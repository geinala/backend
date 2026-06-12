from collections import OrderedDict

from app.lib.logging.logging import get_logger
from app.schemas.node_schema import NodeBase, NodeDetailCreate
from app.models.simulation_job import SimulationJob
from app.models.simulation_uploaded_row import ResolutionStatusEnum, SimulationUploadedRow
from app.schemas.courier_schema import CreateCourier
from app.repositories.node_repository import NodeRepository
from app.repositories.simulation_job_repository import SimulationJobRepository
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.repositories.courier_repository import CourierRepository

logger = get_logger(__name__)


class PreOptimizationService:
    def __init__(
        self,
        simulation_job_repository: SimulationJobRepository,
        simulation_uploaded_row_repository: SimulationUploadedRowRepository,
        courier_repository: CourierRepository,
        node_repository: NodeRepository,
    ):
        self.simulation_job_repository = simulation_job_repository
        self.simulation_uploaded_row_repository = simulation_uploaded_row_repository
        self.courier_repository = courier_repository
        self.node_repository = node_repository

    async def map_couriers_to_vehicles(self, simulation_id: str) -> dict[str, object]:
        simulation_job = await self._get_simulation_job(simulation_id)
        rows = await self._get_resolved_rows(simulation_id)

        if self.courier_repository.get_couriers_by_simulation_id(simulation_id):
            logger.info(f"Couriers already mapped for simulation {simulation_id}, skipping courier mapping")
            return {"simulation_id": simulation_id, "mapped_couriers": 0, "skipped": True}

        courier_totals: OrderedDict[str, float] = OrderedDict()
        for row in rows:
            courier_name = self._normalize_courier_name(row.courier)
            courier_totals[courier_name] = courier_totals.get(courier_name, 0.0) + float(row.weight or 0.0)

        courier_records = [
            CreateCourier(
                simulation_id=simulation_job.id,
                name=courier_name,
                is_active=True,
            )
            for courier_name in courier_totals.keys()
        ]

        self.courier_repository.bulk_insert_couriers(couriers=courier_records)

        logger.info(
            {
                "event_type": "pre_optimization_map_couriers",
                "simulation_id": simulation_id,
                "mapped_couriers": len(courier_records),
                "status": "success",
            }
        )

        return {
            "simulation_id": simulation_id,
            "mapped_couriers": len(courier_records),
            "couriers": list(courier_totals.keys()),
            "simulation_job_id": str(simulation_job.id),
        }

    async def map_nodes_and_details(self, simulation_id: str) -> dict[str, object]:
        simulation_job = await self._get_simulation_job(simulation_id)
        rows = await self._get_resolved_rows(simulation_id)

        existing_nodes = self.node_repository.get_nodes_by_simulation_id(simulation_id)
        if existing_nodes:
            logger.info(f"Nodes already mapped for simulation {simulation_id}, skipping node mapping")
            return {"simulation_id": simulation_id, "mapped_nodes": 0, "skipped": True}
        
        couriers = self.courier_repository.get_couriers_by_simulation_id(simulation_id)
        courier_id_map = {courier.name: courier.id for courier in couriers}

        rows_by_courier: dict[str, list[SimulationUploadedRow]] = {}
        for row in rows:
            courier_name = self._normalize_courier_name(row.courier)
            if courier_name not in rows_by_courier:
                rows_by_courier[courier_name] = []
            rows_by_courier[courier_name].append(row)

        total_mapped_nodes = 0
        total_mapped_details = 0

        for courier_name, courier_rows in rows_by_courier.items():
            nodes: list[NodeBase] = []
            
            depot_node = NodeBase(
                simulation_id=simulation_job.id,
                matrix_index=0,
                latitude=simulation_job.depot_location_latitude,
                longitude=simulation_job.depot_location_longitude,
                demand=0.0,
                courier_id=None
            )
            nodes.append(depot_node)
            
            total_mapped_nodes += 1

            grouped_nodes: dict[tuple[float, float], tuple[NodeBase, list[NodeDetailCreate]]] = {}
            next_matrix_index = 1

            for row in courier_rows:
                if row.latitude is None or row.longitude is None:
                    continue

                node_key = (float(row.latitude), float(row.longitude))
                grouped_node = grouped_nodes.get(node_key)

                if grouped_node is None:
                    details: list[NodeDetailCreate] = []
                    grouped_node = (
                        NodeBase(
                            simulation_id=simulation_job.id,
                            matrix_index=next_matrix_index,
                            latitude=float(row.latitude),
                            longitude=float(row.longitude),
                            demand=0,
                            courier_id=courier_id_map.get(courier_name),
                        ),
                        details,
                    )
                    grouped_nodes[node_key] = grouped_node
                    next_matrix_index += 1

                node, details = grouped_node
                node.demand += float(row.weight or 0.0)
                details.append(self._build_node_detail(row))

            grouped_data: list[tuple[NodeBase, list[NodeDetailCreate]]] = list(grouped_nodes.values())
            
            if grouped_data:
                self.node_repository.create_nodes_with_grouped_details(grouped_data=grouped_data)
                total_mapped_nodes += len(grouped_data)
                total_mapped_details += sum(len(details) for _, details in grouped_data)

        logger.info(
            {
                "event_type": "pre_optimization_map_nodes",
                "simulation_id": simulation_id,
                "mapped_nodes": total_mapped_nodes,
                "status": "success",
            }
        )

        return {
            "simulation_id": simulation_id,
            "mapped_nodes": total_mapped_nodes,
            "mapped_details": total_mapped_details,
            "simulation_job_id": str(simulation_job.id),
        }

    async def _get_simulation_job(self, simulation_id: str) -> SimulationJob:
        simulation_job = await self.simulation_job_repository.get_simulation_job_by_id(simulation_id)
        if not simulation_job:
            raise ValueError(f"Simulation job with ID {simulation_id} not found.")
        return simulation_job

    async def _get_resolved_rows(self, simulation_id: str) -> list[SimulationUploadedRow]:
        uploaded_rows = await self.simulation_uploaded_row_repository.get_uploaded_rows_by_simulation_job_id(simulation_id)
        return [
            row
            for row in uploaded_rows
            if not row.is_ignored
            and row.final_address
            and row.latitude is not None
            and row.longitude is not None
            and row.resolution_status in {ResolutionStatusEnum.auto_solved, ResolutionStatusEnum.manual_override}
        ]

    def _normalize_courier_name(self, courier_name: str | None) -> str:
        if courier_name and courier_name.strip():
            return courier_name.strip()
        return "UNASSIGNED"

    def _build_node_detail(self, row: SimulationUploadedRow) -> NodeDetailCreate:
        address = row.final_address or row.address or ""
        city = row.city or ""

        return NodeDetailCreate(
            name=row.customer_name or row.nosi or "Customer",
            address=address,
            city=city,
            weight=float(row.weight or 0.0),
        )