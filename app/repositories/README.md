# Repositories Module

Data access layer for database operations.

## Purpose

This module provides:

- **Data abstraction** - Decouple business logic from database queries
- **CRUD operations** - Create, Read, Update, Delete patterns
- **Query methods** - Reusable database queries
- **Testability** - Easy to mock database in tests

## Architecture Pattern

```
Route/Controller
    ↓
Repository (data access)
    ↓
Database (SQLAlchemy/ORM)
```

## When to Use

Use repositories when:

- Working with a SQL database
- You need to isolate data access logic
- Multiple parts of code query the same entities
- You want to mock data in tests

## Example Repository (With SQLAlchemy)

```python
# app/repositories/__init__.py

from typing import Optional, List
from app.models import Simulation
from sqlalchemy.orm import Session

class SimulationRepository:
    """Repository for Simulation database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str, job_id: str) -> Simulation:
        """Create new simulation record."""
        sim = Simulation(name=name, job_id=job_id, status='queued')
        self.db.add(sim)
        self.db.commit()
        return sim

    def get_by_id(self, id: int) -> Optional[Simulation]:
        """Get simulation by ID."""
        return self.db.query(Simulation).filter_by(id=id).first()

    def get_by_job_id(self, job_id: str) -> Optional[Simulation]:
        """Get simulation by RQ job ID."""
        return self.db.query(Simulation).filter_by(job_id=job_id).first()

    def list_all(self) -> List[Simulation]:
        """List all simulations."""
        return self.db.query(Simulation).all()

    def update_status(self, id: int, status: str) -> Simulation:
        """Update simulation status."""
        sim = self.get_by_id(id)
        if sim:
            sim.status = status
            self.db.commit()
        return sim
```

## Using Repositories in Controllers

```python
# app/controllers/__init__.py

from app.repositories import SimulationRepository
from app.configs import get_db

class SimulationController:
    @staticmethod
    def enqueue_simulation(config: dict) -> dict:
        db = get_db()
        repo = SimulationRepository(db)

        # Enqueue job
        q = get_queue()
        job = q.enqueue('app.workers.simulation.process_simulation', config)

        # Record in database
        sim = repo.create(
            name=config.get('name'),
            job_id=job.id
        )

        return {'job_id': job.id, 'db_id': sim.id}
```

## Testing Repositories

```python
from unittest.mock import MagicMock
from app.repositories import SimulationRepository

def test_create_simulation():
    mock_db = MagicMock()
    repo = SimulationRepository(mock_db)

    sim = repo.create('test_sim', 'job123')

    assert sim.name == 'test_sim'
    assert sim.job_id == 'job123'
    mock_db.add.assert_called_once()
```

## Design Principles

- **Single responsibility** - One repository per entity
- **Dependency injection** - Pass DB session to constructor
- **No business logic** - Keep only data access logic
- **Testable** - Easy to mock for unit tests

For now, this directory is a placeholder for database integration.
