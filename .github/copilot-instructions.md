# Copilot Instructions - Simulation App Solver

## 📚 Before Starting - Read Agent Skills First

**IMPORTANT**: Before working on any task, always review the installed agent skills in the `.agents/` directory:

```bash
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

**Simulation App Solver** is a backend **worker service** that processes simulation jobs from a message broker (Redis). It is a pure background job processor with NO HTTP endpoints.

- **Stack**: RQ (task queue), Redis (message broker), Pydantic, RQ-Scheduler
- **Language**: Python >=3.10
- **Package Manager**: `uv` (not pip/venv)
- **Architecture**: Message broker-driven worker, pure background process

## Architecture Essentials

### Directory Structure & Patterns

```
app/
├── workers/             # RQ job handler modules
│   ├── simulation.py    # Example: simulation job handler
│   └── __init__.py
├── core/
│   ├── config.py        # Configuration & environment
│   └── __init__.py      # Redis & Queue setup
└── schemas/
    └── __init__.py      # Pydantic models for validation
```

**Worker Pattern**: Job handlers are async functions in `app/workers/`:

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
- **No HTTP Layer**: Pure background worker—no FastAPI or web framework
- **CloudEvents Support**: Structured event publishing for inter-service communication
- **Pydantic V2**: For job argument validation and message schemas
- **No Monitoring HTTP**: Health monitoring done via Redis connection checks, not endpoints

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

- [app/workers/simulation.py](app/workers/simulation.py) - Example job handler
- [app/core/config.py](app/core/config.py) - Configuration & Redis setup
- [app/schemas/**init**.py](app/schemas/__init__.py) - Pydantic validation models
- [pyproject.toml](pyproject.toml) - RQ, Redis dependencies

## Guiding Principles

1. **Message-Driven**: All business logic is job handler functions, not HTTP endpoints
2. **State via Redis**: Job state/progress stored in Redis, not in-memory
3. **Async-First**: Workers handle I/O-bound simulation tasks with `async/await`
4. **No HTTP Layer**: Pure background process; no web framework overhead
5. **Type Safety**: Validate job inputs with Pydantic before processing

## Documentation Index

- **README**: [../../README.md](../../README.md) - Setup, quick start, Docker & Makefile
- **Project Structure**: See [STRUCTURE.md](../../STRUCTURE.md) for complete directory layout
- **Worker Guide**: [app/workers/README.md](../../app/workers/README.md) - Patterns for job handlers
- **Configuration**: [app/core/README.md](../../app/core/README.md) - Environment & Redis setup
- **Schemas**: [app/schemas/README.md](../../app/schemas/README.md) - Pydantic validation models
- **Testing**: [tests/README.md](../../tests/README.md) - Test setup & fixtures
- **Infrastructure**: [Dockerfile](../../Dockerfile), [docker-compose.yml](../../docker-compose.yml), [Makefile](../../Makefile)
- **Agent Skills**:
  - [.agents/skills/python-background-jobs/SKILL.md](.agents/skills/python-background-jobs/SKILL.md) - RQ & task queue patterns
  - [.agents/skills/python-design-patterns/SKILL.md](.agents/skills/python-design-patterns/SKILL.md) - KISS, SRP, composition
