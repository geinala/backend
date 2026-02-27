from sqlalchemy.orm import Session, joinedload
from app.models.node import Node, NodeDetail, NodeDetailCreate

class NodeRepository:
    def __init__(self, db: Session):
        self.db = db

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
        return self.db.query(Node).options(
            joinedload(Node.details)
        ).filter(
            Node.simulation_id == simulation_id
        ).all()