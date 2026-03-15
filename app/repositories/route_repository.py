from sqlalchemy.orm import Session

from app.models.route import CreateRouteLeg, RouteLeg

class RouteRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def bulk_insert_route_legs(self, route_legs: list[CreateRouteLeg]):
        objects = [RouteLeg(**leg.model_dump()) for leg in route_legs]

        self.db.bulk_save_objects(objects)