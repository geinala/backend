from sqlalchemy.orm import Session

from app.models.tabu_search_configuration import TabuSearchConfiguration
from app.schemas.tabu_search_configuration_schema import (
    TabuSearchConfigurationCreate,
)

class TabuSearchConfigurationRepository:
    def __init__(self, db: Session):
        self.db = db

    async def create_tabu_search_configuration(
        self,
        data: TabuSearchConfigurationCreate,
    ) -> TabuSearchConfiguration:
        config = TabuSearchConfiguration(
            **data.model_dump()
        )

        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        return config

    async def get_active_tabu_search_configuration(self) -> TabuSearchConfiguration | None:
        return self.db.query(TabuSearchConfiguration).filter_by(is_active=True).first()