import time

from app.lib.db import get_db
from app.lib.logging.logging import get_logger
from app.repositories.simulation_repository import SimulationRepository
from app.repositories.route_repository import RouteRepository
from app.services.simulation_engine_service import SimulationEngineService
from app.configs.environment_configuration import get_environment_configuration

logger = get_logger(__name__)


def run_simulation_engine(tick_interval_seconds: float | None = None) -> None:
    settings = get_environment_configuration()
    resolved_tick_interval = tick_interval_seconds
    if resolved_tick_interval is None:
        resolved_tick_interval = settings.SIMULATION_ENGINE_TICK_INTERVAL_SECONDS

    db_session = get_db()
    db = next(db_session)

    service = SimulationEngineService(
        simulation_repository=SimulationRepository(db),
        route_repository=RouteRepository(db),
        tick_interval_seconds=resolved_tick_interval,
    )

    logger.info(
        {
            "event_type": "simulation_engine_started",
            "tick_interval_seconds": resolved_tick_interval,
        }
    )

    try:
        while True:
            service.tick_once()
            time.sleep(resolved_tick_interval)
    finally:
        db.close()


def main() -> None:
    run_simulation_engine(5.0)


if __name__ == "__main__":
    main()