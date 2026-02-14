# Repositories Module

Data access layer for database operations that you need for persistent storage.

This module provides:

- **Data abstraction** - Decouple business logic from database queries
- **CRUD operations** - Create, Read, Update, Delete patterns
- **Query methods** - Reusable database queries
- **Testability** - Easy to mock data layer in tests
- **Logging** - Track data access operations

## Architecture Position

```
FastAPI Route (HTTP)
        ↓
Controller (orchestration)
        ↓
Service (business logic) ← Uses Repository for data access
        ↓
Repository (data access) ← You are here (Uses Database Models)
        ↓
Database (SQLAlchemy/ORM)
        ↓
PostgreSQL/MySQL/Similar
```

Repositories isolate database access so services can focus on business logic.

## When to Use

Use repositories when:

- You're working with a SQL database
- You need to isolate data access logic from business logic
- Multiple services query the same entities
- You want to mock data in tests

You don't need repositories for:

- Pure Redis-based operations (use RQ directly)
- Simple key-value access (access Redis directly)
- Job metadata (RQ handles this automatically)

##Current Status

Repositories are optional for the Simulation App Solver.

The core application uses Redis for all state. You can add repositories when you need persistent database storage for:

- Simulation history and results
- User configuration
- Audit logs
- Analytics data

## Example Repository

Create repository patterns for your data access needs.

### Basic Repository Pattern

Use this pattern for simple CRUD operations:

`app/repositories/simulation_repository.py`

```python

from app.lib import get_logger
from app.models import Simulation
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List

logger = get_logger(__name__)

class SimulationRepository:
"""Repository for Simulation database operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create(self, job_id: str, name: str, status: str = "queued") -> Simulation:
        """Create new simulation record."""
        try:
            logger.info(f"Repository: Creating simulation - job {job_id}, name {name}")

            sim = Simulation(job_id=job_id, name=name, status=status)
            self.db.add(sim)
            self.db.commit()
            self.db.refresh(sim)

            logger.info(f"Repository: Simulation created - ID {sim.id}")
            return sim

        except SQLAlchemyError as e:
            logger.error(f"Repository: Create failed - {str(e)}")
            self.db.rollback()
            raise

    def get_by_id(self, id: int) -> Optional[Simulation]:
        """Get simulation by database ID."""
        try:
            logger.info(f"Repository: Fetching simulation ID {id}")

            sim = self.db.query(Simulation).filter_by(id=id).first()

            if sim:
                logger.info(f"Repository: Simulation found - {sim.job_id}")
            else:
                logger.warning(f"Repository: Simulation not found - {id}")

            return sim

        except SQLAlchemyError as e:
            logger.error(f"Repository: Fetch failed - {str(e)}")
            raise

    def get_by_job_id(self, job_id: str) -> Optional[Simulation]:
        """Get simulation by RQ job ID."""
        try:
            logger.info(f"Repository: Fetching by job ID {job_id}")

            sim = self.db.query(Simulation).filter_by(job_id=job_id).first()

            if sim:
                logger.info(f"Repository: Found simulation {sim.id}")
            else:
                logger.warning(f"Repository: Simulation not found for job {job_id}")

            return sim

        except SQLAlchemyError as e:
            logger.error(f"Repository: Fetch failed - {str(e)}")
            raise

    def list_all(self) -> List[Simulation]:
        """List all simulations."""
        try:
            logger.info("Repository: Listing all simulations")

            sims = self.db.query(Simulation).all()

            logger.info(f"Repository: Found {len(sims)} simulations")
            return sims

        except SQLAlchemyError as e:
            logger.error(f"Repository: List failed - {str(e)}")
            raise

    def list_by_status(self, status: str) -> List[Simulation]:
        """List simulations by status."""
        try:
            logger.info(f"Repository: Fetching simulations with status {status}")

            sims = self.db.query(Simulation).filter_by(status=status).all()

            logger.info(f"Repository: Found {len(sims)} simulations with status {status}")
            return sims

        except SQLAlchemyError as e:
            logger.error(f"Repository: List by status failed - {str(e)}")
            raise

    def update_status(self, id: int, status: str) -> Optional[Simulation]:
        """Update simulation status."""
        try:
            logger.info(f"Repository: Updating simulation {id} status to {status}")

            sim = self.get_by_id(id)
            if sim:
                sim.status = status
                self.db.commit()
                self.db.refresh(sim)

                logger.info(f"Repository: Simulation {id} updated")
            else:
                logger.warning(f"Repository: Simulation {id} not found for update")

            return sim

        except SQLAlchemyError as e:
            logger.error(f"Repository: Update failed - {str(e)}")
            self.db.rollback()
            raise

    def update_result(self, id: int, result: dict) -> Optional[Simulation]:
        """Update simulation result."""
        try:
            logger.info(f"Repository: Updating simulation {id} result")

            sim = self.get_by_id(id)
            if sim:
                sim.result = result
                sim.status = "completed"
                self.db.commit()
                self.db.refresh(sim)

                logger.info(f"Repository: Simulation {id} result updated")
            else:
                logger.warning(f"Repository: Simulation {id} not found")

            return sim

        except SQLAlchemyError as e:
            logger.error(f"Repository: Result update failed - {str(e)}")
            self.db.rollback()
            raise

    def delete(self, id: int) -> bool:
        """Delete simulation record."""
        try:
            logger.info(f"Repository: Deleting simulation {id}")

            sim = self.get_by_id(id)
            if sim:
                self.db.delete(sim)
                self.db.commit()

                logger.info(f"Repository: Simulation {id} deleted")
                return True
            else:
                logger.warning(f"Repository: Simulation {id} not found")
                return False

        except SQLAlchemyError as e:
            logger.error(f"Repository: Delete failed - {str(e)}")
            self.db.rollback()
            raise

```

### Using Repository in Service

```python
# app/services/simulation_service.py

from app.lib import get_logger
from app.repositories import SimulationRepository
from sqlalchemy.orm import Session

logger = get_logger(__name__)

class SimulationService:
    """Service using repository for data access."""

    @staticmethod
    def record_simulation(db: Session, job_id: str, name: str) -> dict:
        """Record simulation in database."""
        try:
            logger.info(f"Service: Recording simulation {job_id}")

            repo = SimulationRepository(db)
            sim = repo.create(job_id, name)

            logger.info(f"Service: Simulation recorded - ID {sim.id}")
            return {
                "id": sim.id,
                "job_id": sim.job_id,
                "status": sim.status
            }

        except Exception as e:
            logger.error(f"Service: Failed to record simulation - {str(e)}")
            raise

    @staticmethod
    def update_simulation_result(db: Session, job_id: str, result: dict) -> dict:
        """Update simulation result via repository."""
        try:
            logger.info(f"Service: Updating simulation {job_id} with result")

            repo = SimulationRepository(db)
            sim = repo.get_by_job_id(job_id)

            if not sim:
                logger.error(f"Service: Simulation {job_id} not found")
                raise ValueError(f"Simulation {job_id} not found")

            sim = repo.update_result(sim.id, result)

            logger.info(f"Service: Simulation result updated")
            return {
                "id": sim.id,
                "status": sim.status,
                "result": sim.result
            }

        except Exception as e:
            logger.error(f"Service: Failed to update result - {str(e)}")
            raise
```

## File Organization

```
repositories/
├── __init__.py                      # Repository exports
├── simulation_repository.py         # Simulation data access
├── user_repository.py               # User data access (optional)
└── README.md
```

`app/repositories/__init__.py`:

```python
"""Data access layer repositories."""

from app.repositories.simulation_repository import SimulationRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "SimulationRepository",
    "UserRepository",
]
```

## Best Practices

✅ **Include logging at every operation**

```python
logger.info(f"Repository: Creating record - {data}")
logger.error(f"Repository: Failed - {error}")
```

✅ **Handle database errors gracefully**

```python
try:
    repo.create(data)
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    db.rollback()
    raise
```

✅ **Type hints for clarity**

```python
def get_by_id(self, id: int) -> Optional[Simulation]:
    ...

def list_all(self) -> List[Simulation]:
    ...
```

✅ **Use dependency injection for session**

```python
class Repository:
    def __init__(self, db: Session):
        self.db = db  # Injected, not created
```

❌ **Avoid business logic in repositories**

```python
# Bad - Business logic in repository
def process_simulation(self):
    sim = self.get_simulation()
    sim.status = "processing"
    self.save()

# Good - Repository only does data access
def update_status(self, id, status):
    sim = self.get_by_id(id)
    sim.status = status
    self.db.commit()
```

❌ **Don't create new database sessions**

```python
# Bad
class Repository:
    def get_data(self):
        db = SessionLocal()  # ❌ Creates new session

# Good
class Repository:
    def __init__(self, db: Session):
        self.db = db  # Uses injected session
```

## Testing Repositories

```python
from unittest.mock import Mock, MagicMock
from app.repositories import SimulationRepository
from app.models import Simulation

def test_create_simulation():
    """Test repository create operation."""
    mock_db = Mock()
    repo = SimulationRepository(mock_db)

    sim = Simulation(job_id="test", name="test_sim")
    mock_db.query().filter_by().first.return_value = sim

    result = repo.get_by_job_id("test")

    assert result.job_id == "test"
    assert result.name == "test_sim"
```

## Design Principles

- **Single responsibility** - One repository per entity
- **Dependency injection** - Pass DB session to constructor
- **No business logic** - Keep only data access logic
- **Testable** - Easy to mock for unit tests

For now, this directory is a placeholder for database integration.

## See Also

- [Models Module](../models/README.md) - Database models
- [Services Module](../services/README.md) - Using repositories in business logic
- [Configs Module](../configs/README.md) - Database configuration
- [Lib Module](../lib/README.md) - Database utilities
