from datetime import datetime

from sqlalchemy.orm import Session, joinedload
from app.models.node import Node, NodeDetail
from app.schemas.node_detail_schema import NodeDetailCreate

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
        grouped_data: list[tuple[Node, list[NodeDetailCreate]]]
    ):
        try:
            nodes = [node for node, _ in grouped_data]
            
            self.db.add_all(nodes)
            self.db.flush()
            
            for node, details_dicts in grouped_data:
                for detail_dict in details_dicts:
                    node_detail = NodeDetail(
                        node_id=node.id,
                        **detail_dict.model_dump()
                    )
                    self.db.add(node_detail)
            
            self.db.commit()
            
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