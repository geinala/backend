from sqlalchemy.orm import Session

from app.models.courier import Courier
from app.schemas.courier_schema import CreateCourier

class CourierRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def get_couriers_by_simulation_id(self, simulation_id: str) -> list[Courier]:
        return self.db.query(Courier).filter_by(simulation_id=simulation_id).all()

    def get_all_active_couriers_by_simulation_id(self, simulation_id: str) -> list[Courier]:
        return self.db.query(Courier).filter_by(simulation_id=simulation_id, is_active=True).all()

    def bulk_insert_couriers(self, couriers: list[CreateCourier]):
        courier_objects = [Courier(**courier.model_dump()) for courier in couriers]

        self.db.add_all(courier_objects)

        try:
            self.db.commit()

            for courier in courier_objects:
                self.db.refresh(courier)

            return courier_objects
        except Exception:
            self.db.rollback()
            raise