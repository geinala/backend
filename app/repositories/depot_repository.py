from sqlalchemy.orm import Session

from app.models.depot import Depot

class DepotRepository:
    def __init__(self, db: Session):
        self.db = db

    async def get_depot_by_id(self, depot_id: int) -> Depot | None:
        return self.db.query(Depot).filter(Depot.id == depot_id).first()