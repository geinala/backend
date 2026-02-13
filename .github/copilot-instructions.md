# Copilot Instructions - Simulation App Solver

## 📚 Before Starting - Read Agent Skills First

**IMPORTANT**: Before working on any task, always review the installed agent skills in the `.agents/` directory:

```bash
.agents/skills/fastapi-templates/SKILL.md               # FastAPI patterns (if applicable)
.agents/skills/kiss-dry-yagni/SKILL.md  # Design principles
.agents/skills/python-background-jobs/SKILL.md         # RQ patterns & task queues
.agents/skills/python-design-patterns/SKILL.md         # KISS, SRP, Composition
.agents/skills/python-type-safety/SKILL.md             # Type hints & validation
.agents/skills/python-performance-optimization/SKILL.md # Profiling & optimization
```

Read the relevant skill documentation first to understand:

- Background job patterns and RQ best practices
- Design principles (KISS, Single Responsibility, Composition)
- Type safety with Pydantic
- Performance optimization techniques

This ensures your implementation aligns with established best practices.

## Project Overview

**Simulation App Solver** is a backend **worker service** with optional **REST API** for job management.

- **Stack**: RQ (task queue), Redis (message broker), Pydantic, FastAPI (optional), RQ-Scheduler
- **Language**: Python >=3.10
- **Package Manager**: `uv` (not pip/venv)
- **Architecture**: Message broker-driven worker service with layered API

**Core**: Pure background job processor
**Optional**: REST API for job enqueueing and status checks

## Architecture Layers

```
┌─────────────────────────────────────────┐
│         API Routes (HTTP)                │ ← FastAPI endpoints (optional)
├─────────────────────────────────────────┤
│  Controllers (Orchestration - optional)  │ ← Complex workflows
├─────────────────────────────────────────┤
│   Services (Shared Business Logic)      │ ← Reusable code between API & workers
├─────────────────────────────────────────┤
│     Workers (Job Execution - RQ)        │ ← Background task handlers
├─────────────────────────────────────────┤
│  Models, DTOs, Repositories (Data)      │ ← DB models, validation, data access
├─────────────────────────────────────────┤
│  Configs (Settings & Redis - singleton) │ ← Environment & infrastructure
└─────────────────────────────────────────┘
```

**Data Flow:**

1. API receives request → validates with **DTOs**
2. Route optionally uses **Controller** for orchestration
3. Logic handled by **Services** (shared between API & workers)
4. Job enqueued to Redis → **Worker** executes logic
5. Data persisted with **Models** & **Repositories**
6. Configuration managed by **Configs** (singleton pattern)

## Project Structure

```
app/
├── api/                     # FastAPI routes (optional HTTP layer)
│   ├── routes.py           # REST endpoints
│   └── README.md
├── configs/                # Configuration & Redis setup
│   ├── environment_configuration.py  # Settings (Pydantic)
│   ├── redis_configuration.py       # Redis singleton
│   └── README.md
├── workers/                # RQ job handlers (core execution)
│   ├── hello_world.py     # Example job handler
│   └── README.md
├── services/               # Shared business logic (optional)
│   ├── __init__.py        # Reusable services
│   └── README.md
├── controllers/            # API orchestration (optional)
│   └── README.md
├── dtos/                   # Request/Response validation
│   ├── __init__.py        # Pydantic models (SimulationConfig, JobResult)
│   └── README.md
├── models/                 # Database models (optional)
│   └── README.md
├── repositories/           # Data access layer (optional)
│   └── README.md
├── main.py                 # FastAPI app entrypoint (optional)
└── __init__.py
```

**Worker Pattern**: Job handlers are functions in `app/workers/`:

```python
# app/workers/simulation.py
from rq import current_job

def process_simulation(config: dict) -> dict:
    """Simulation job handler—enqueued via Redis."""
    job = current_job()
    job.meta['progress'] = 0
    job.save_meta()
    # ... simulation logic ...
    return {"result": "..."}
```

### Key Technical Decisions

- **Redis + RQ Only**: Message broker-based job processing; Redis is the **single source of truth** for tasks
- **CloudEvents Support**: Structured event publishing for inter-service communication
- **Pydantic V2**: For job argument validation and message schemas
- **Layered Architecture**: Clean separation between API, services, workers, and data layers
- **Optional HTTP Layer**: Can work as pure background worker or with optional FastAPI API

## Development Workflow

### Setup

```bash
# Install dependencies
uv sync

# Run worker (listens to Redis job queue)
rq worker

# View logs: use Redis CLI for job status
redis-cli
```

### Adding Job Handlers

1. Create handler in `app/workers/[module].py`:

   ```python
   from rq import current_job

   async def handle_my_job(param1: str, param2: int) -> dict:
       """Job handler runs in worker process."""
       job = current_job()
       job.meta['status'] = 'processing'
       job.save_meta()
       # ... async work ...
       return {"result": param1}
   ```

2. Register job handler for RQ:
   - Job enqueuing happens upstream (via API gateway or scheduler)
   - Worker process auto-discovers and executes queued jobs

### Code Conventions

- **Async Job Handlers**: Use `async def` with RQ's job context (`current_job()`)
- **Job Metadata**: Track progress/status via `job.meta` and `job.save_meta()`
- **Pydantic Models**: For input validation on enqueued job arguments
- **Error Handling**: Exceptions in handlers trigger RQ's built-in failure tracking

## Integration Points

### Redis & Job Queue

Worker processes listen to Redis:

```python
# Upstream service enqueues jobs
from rq import Queue
from redis import Redis

redis = Redis()
q = Queue(connection=redis)
job = q.enqueue('app.workers.simulation.process_simulation',
                 config={'param': 'value'})

# Worker process auto-executes handlers
# No HTTP endpoint needed
```

### CloudEvents

For publishing events after job completion:

```python
from cloudevents.http import CloudEvent
# Publish to external systems
publish_event(CloudEvent(...))
```

## Key Files to Reference

- [app/workers/hello_world.py](app/workers/hello_world.py) - Example job handler
- [app/configs/redis_configuration.py](app/configs/redis_configuration.py) - Redis singleton setup
- [app/dtos/**init**.py](app/dtos/__init__.py) - Pydantic validation models
- [app/services/README.md](app/services/README.md) - Shared business logic patterns
- [pyproject.toml](pyproject.toml) - RQ, Redis dependencies

## Guiding Principles

1. **Message-Driven**: Primary execution via job queue, optional HTTP API
2. **State via Redis**: Job state/progress stored in Redis, not in-memory
3. **Layered Architecture**: Clean separation of concerns (API → Services → Workers)
4. **Async-First**: Workers handle I/O-bound tasks with `async/await`
5. **Type Safety**: Validate job inputs with Pydantic before processing
6. **Shared Services**: Reuse business logic between API and workers

## Documentation Index

- **README**: [../../README.md](../../README.md) - Setup, quick start, Docker & Makefile
- **Architecture**: [#architecture-layers](#architecture-layers) - Layered architecture overview
- **API Guide**: [app/api/README.md](../../app/api/README.md) - HTTP endpoints & job management
- **Worker Guide**: [app/workers/README.md](../../app/workers/README.md) - Patterns for job handlers
- **Services Guide**: [app/services/README.md](../../app/services/README.md) - Shared business logic
- **DTOs Guide**: [app/dtos/README.md](../../app/dtos/README.md) - Request/Response validation
- **Configuration**: [app/configs/README.md](../../app/configs/README.md) - Environment & Redis setup
- **Testing**: [tests/README.md](../../tests/README.md) - Test setup & fixtures
- **Infrastructure**: [Dockerfile](../../Dockerfile), [docker-compose.yml](../../docker-compose.yml), [Makefile](../../Makefile)
- **Agent Skills**:
  - [.agents/skills/python-background-jobs/SKILL.md](.agents/skills/python-background-jobs/SKILL.md) - RQ & task queue patterns
  - [.agents/skills/python-design-patterns/SKILL.md](.agents/skills/python-design-patterns/SKILL.md) - KISS, SRP, composition
