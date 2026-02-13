# Models Module

Database and domain models (if using a database).

## Purpose

This module contains:

- **SQLAlchemy models** - Database table definitions (if using SQL)
- **Domain models** - Core data structures and business entities
- **Relationships** - Foreign keys and relationships between entities

## When to Use

Use models if the app requires:

- Persistent data storage (database)
- Database migrations
- Complex relationships between entities
- Audit trails or data versioning

## Note: This is a Background Job Service

The **Simulation App Solver** is primarily a message-driven worker service. Most data persists in **Redis** (job state, results).

Database models are optional unless you need:

- Historical data storage
- Complex queries beyond job metadata
- User/configuration management
- Audit logs

## Example Model (SQLAlchemy)

If databases are needed later:

```python
# app/models/__init__.py

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Simulation(Base):
    """Simulation record model."""

    __tablename__ = "simulations"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    job_id = Column(String(255), nullable=False, unique=True)
    status = Column(String(50), nullable=False)
    result = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
