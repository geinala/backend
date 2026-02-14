# Models Module

Database models and domain entities for when you add database support.

This module contains:

- **SQLAlchemy models** - Database table definitions
- **Domain models** - Core business entities and data structures
- **Relationships** - Foreign keys and relationships between entities

## When to Use

Use models when your application needs:

- Persistent data storage using a SQL database
- Complex queries and relationships
- Data migrations and versioning
- Audit trails and historical data
- User and configuration management

You don't need models for:

- Pure message-driven worker services with data stored in Redis
- Simple key-value storage (access Redis directly)
- Job metadata (RQ handles this automatically in Redis)

## Current Status

The Simulation App Solver is primarily a message-driven worker service.

Jobs and metadata are stored in Redis via RQ. You don't need a database for core functionality, but models are optional for future expansion.

## Setting Up Database Support (if Needed)

### Option 1: Simple Models

Use this approach when you don't need complex relationships:

`app/models/__init__.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.orm import declarative_base, Session
from datetime import datetime

Base = declarative_base()

class Simulation(Base):
"""Simulation job record."""

    __tablename__ = "simulations"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)
    name = Column(String)
    status = Column(String, default="queued")  # queued, running, completed, failed
    result = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class JobLog(Base):
"""Job execution log."""

    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, index=True)
    message = Column(String)
    level = Column(String)  # debug, info, warning, error
    created_at = Column(DateTime, default=datetime.utcnow)

```

### Option 2: With SQLAlchemy ORM

Use this approach when you have relationships between models:

`app/models/__init__.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
"""User model."""
**tablename** = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True)
    jobs = relationship("Simulation", back_populates="user")

class Simulation(Base):
"""Simulation model with user relationship."""
**tablename** = "simulations"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="jobs")

```

## Using Models with Repositories

Models work with repositories for data access:

```

Route/Controller
↓
Service (uses Repository for data)
↓
Repository (uses Model for queries)
↓
Database (SQLAlchemy ORM)

```

Example with repository:

```python
# app/repositories/simulation_repository.py

from app.models import Simulation
from sqlalchemy.orm import Session

class SimulationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, job_id: str, name: str) -> Simulation:
        """Create new simulation record."""
        sim = Simulation(job_id=job_id, name=name)
        self.db.add(sim)
        self.db.commit()
        return sim

    def get_by_job_id(self, job_id: str) -> Simulation | None:
        """Get simulation by RQ job ID."""
        return self.db.query(Simulation).filter_by(job_id=job_id).first()

    def update_status(self, job_id: str, status: str) -> Simulation:
        """Update simulation status."""
        sim = self.get_by_job_id(job_id)
        if sim:
            sim.status = status
            self.db.commit()
        return sim
```

Then use in service:

```python
# app/services/simulation_service.py

from app.lib import get_logger
from app.repositories import SimulationRepository
from sqlalchemy.orm import Session

logger = get_logger(__name__)

class SimulationService:
    @staticmethod
    def create_simulation_record(db: Session, job_id: str, name: str) -> Simulation:
        """Create simulation record in database."""
        logger.info(f"Service: Creating simulation record for job {job_id}")

        repo = SimulationRepository(db)
        sim = repo.create(job_id, name)

        logger.info(f"Service: Simulation record created - ID {sim.id}")
        return sim

    @staticmethod
    def get_simulation(db: Session, job_id: str) -> Simulation | None:
        """Fetch simulation from database."""
        logger.info(f"Service: Fetching simulation {job_id}")

        repo = SimulationRepository(db)
        return repo.get_by_job_id(job_id)
```

## Database Configuration

When using a database, configure in `app/configs/environment_configuration.py`:

```python
# Already configured:
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", 5432))
DB_USERNAME: str = os.getenv("DB_USERNAME", "user")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
DB_NAME: str = os.getenv("DB_NAME", "simulation_db")

@property
def database_url(self) -> str:
    return f"postgresql://{self.DB_USERNAME}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
```

And access via:

```python
# app/configs/database_configuration.py

from app.configs import get_environment_configuration

db_config = DatabaseConfiguration()
database_url = db_config.database_url
```

## File Organization

```
models/
├── __init__.py              # All models exported
├── simulation.py            # Simulation model (optional)
├── user.py                  # User model (optional)
└── README.md
```

`app/models/__init__.py`:

```python
"""Database models and entities."""

# Import models here to make them available at package level
# from app.models.simulation import Simulation
# from app.models.user import User

# __all__ = ["Simulation", "User"]
```

## Testing Models

```python
from app.models import Simulation
from datetime import datetime

def test_simulation_model():
    """Test model creation."""
    sim = Simulation(
        job_id="test-123",
        name="test_simulation",
        status="queued"
    )

    assert sim.job_id == "test-123"
    assert sim.status == "queued"
    assert isinstance(sim.created_at, datetime)
```

## Common Patterns

### Timestamp Tracking

```python
from datetime import datetime

class BaseModel(Base):
    """Base model with audit timestamps."""
    __abstract__ = True

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Simulation(BaseModel):
    __tablename__ = "simulations"
    id = Column(Integer, primary_key=True)
    # ... other fields ...
```

### Status Enum

```python
from enum import Enum
from sqlalchemy import Enum as SQLEnum

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Simulation(Base):
    __tablename__ = "simulations"
    status = Column(SQLEnum(JobStatus), default=JobStatus.QUEUED)
```

### JSON Field for Flexible Data

```python
from sqlalchemy import JSON

class Simulation(Base):
    __tablename__ = "simulations"
    # ... fields ...
    metadata = Column(JSON, default={})  # Flexible data storage
    result = Column(JSON, nullable=True)
```

## Redis vs Database Trade-off

**Use Redis (Current):**

- ✅ Job state and temporary results
- ✅ Fast, message-driven architecture
- ✅ No schema migrations needed
- ✅ TTL automatic cleanup

**Add Database when:**

- 📊 Need to query historical simulations
- 🔍 Complex analytics on past data
- 👤 Multiple users with permissions
- 📋 Compliance/audit requirements

For now, this directory is a placeholder for future database integration.

## See Also

- [Repositories Module](../repositories/README.md) - Data access layer using models
- [Services Module](../services/README.md) - Business logic using repositories
- [Configs Module](../configs/README.md) - Database configuration
- [Lib Module](../lib/README.md) - Database utilities
