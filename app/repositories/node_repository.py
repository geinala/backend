from datetime import datetime

from sqlalchemy.orm import Session, joinedload
from app.models.node import Node, NodeDetail
from app.schemas.node_schema import NodeBase, NodeDetailCreate

class NodeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_node(self, node: Node):
        try:
            self.db.add(node)
            self.db.commit()
            self.db.refresh(node)
            return node
        except Exception:
            self.db.rollback()
            raise

    def mark_node_as_completed(
        self,
        node_id: int,
        courier_id: int,
        completed_at: datetime,
    ) -> bool:
        updated_rows = (
            self.db.query(Node)
            .filter(Node.id == node_id)
            .update(
                {
                    Node.is_completed: True,
                    Node.completed_at: completed_at,
                    Node.completed_by: courier_id,
                },
                synchronize_session=False,
            )
        )

        return updated_rows > 0

    def create_nodes_with_grouped_details(
        self,
        grouped_data: list[tuple[NodeBase, list[NodeDetailCreate]]],
    ) -> list[Node]:
        try:
            created_nodes: list[Node] = []

            for node_data, detail_data_list in grouped_data:
                node = Node(
                    simulation_id=node_data.simulation_id,
                    courier_id=node_data.courier_id,
                    matrix_index=node_data.matrix_index,
                    latitude=node_data.latitude,
                    longitude=node_data.longitude,
                    demand=node_data.demand,
                )

                self.db.add(node)
                self.db.flush()

                for detail_data in detail_data_list:
                    self.db.add(
                        NodeDetail(
                            node_id=node.id,
                            **detail_data.model_dump(),
                        )
                    )

                created_nodes.append(node)

            self.db.commit()

            for node in created_nodes:
                self.db.refresh(node)

            return created_nodes

        except Exception:
            self.db.rollback()
            raise

    def get_nodes_by_simulation_id(self, simulation_id: str) -> list[Node]:
        return self.db.query(Node).filter(Node.simulation_id == simulation_id).all()

    def get_nodes_by_simulation_id_and_courier_id(self, simulation_id: str, courier_id: int) -> list[Node]:
        return self.db.query(Node).filter(
            Node.simulation_id == simulation_id,
            Node.courier_id == courier_id,
        ).all()

    def get_nodes_with_details_by_simulation_id(self, simulation_id: str) -> list[Node]:
        return self.db.query(Node).options(
            joinedload(Node.details)
        ).filter(
            Node.simulation_id == simulation_id
        ).order_by(Node.matrix_index.asc()).all()
        
    def get_remaining_nodes_by_simulation_id_and_courier_id(self, simulation_id: str, courier_id: int) -> list[Node]:
        return self.db.query(Node).filter(
            Node.simulation_id == simulation_id,
            Node.courier_id == courier_id,
            Node.is_completed == False
        ).all()