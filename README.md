# Simulation App Solver

Backend **worker service** for processing simulation jobs via Redis message broker (RQ).

- **Pure background processor** - No HTTP API, message-driven only
- **Async job handlers** using RQ (Redis Queue)
- **Pydantic V2** for input validation
- **Python 3.10+** with `uv` package manager

## Prerequisites

1. **Python 3.10+**
2. **uv** (Python Package Manager)

   _Mac/Linux:_

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   _Windows:_

   ```powershell
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. **Redis** (for job queue and message broker)
   - Local: `redis-server`
   - Or use Docker: `docker run -d -p 6379:6379 redis:7`

## Quick Start

### 1. Local Development

```bash
# Install dependencies
uv sync

# Create .env from template
cp .env.example .env

# Terminal 1: Start Redis (if not running)
redis-server

# Terminal 2: Start worker (listens to Redis queue)
make worker

# Terminal 3: Monitor jobs with Redis CLI
redis-cli
```

### 2. Docker Development

```bash
# Start everything (Redis + Worker)
make docker-up

# View logs
make docker-logs

# Stop everything
make docker-down
```

### 3. Production

```bash
# Build and run with production settings
make docker-build
make docker-prod

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=3
```

## Enqueueing Jobs

Jobs are enqueued from **upstream services** (API gateway, scheduler, CLI):

```python
from rq import Queue
from redis import Redis

redis = Redis(host='localhost', port=6379)
q = Queue(connection=redis)

# Enqueue simulation job
job = q.enqueue(
    'app.workers.simulation.process_simulation',
    {'name': 'test_sim', 'parameters': {'iterations': 1000}},
    job_timeout='10m'
)

print(f"Job ID: {job.id}")
```

## Project Structure

```
.
├── README.md                      # Project documentation
├── pyproject.toml                 # Project dependencies (uv)
├── .env.example                   # Example environment variables
│
├── app/                           # Main application package
│   ├── __init__.py
│   │
│   ├── configs/                   # Configuration & Redis setup
│   │   ├── __init__.py            # Exports all config utilities
│   │   ├── environment_configuration.py  # Environment settings
│   │   └── redis_configuration.py # Redis & Queue singleton
│   │
│   ├── workers/                   # RQ job handlers
│   │   ├── __init__.py
│   │   ├── hello_world.py         # Example: simple job handler
│   │   └── README.md              # Workers guide & patterns
│   │
│   ├── api/                       # FastAPI routes
│   │   ├── __init__.py
│   │   ├── routes.py              # API endpoints
│   │   └── README.md              # API documentation
│   │
│   ├── dtos/                      # Request/Response models
│   │   ├── __init__.py            # SimulationConfig, JobResult
│   │   └── README.md              # DTOs guide
│   │
│   ├── services/                  # Reusable business logic
│   │   ├── __init__.py            # Shared services (optional)
│   │   └── README.md              # Services guide
│   │
│   ├── controllers/               # Business logic layer (optional)
│   │   ├── __init__.py
│   │   └── README.md              # Controllers guide
│   │
│   ├── models/                    # Database models (optional)
│   │   ├── __init__.py
│   │   └── README.md              # Models guide
│   │
│   ├── repositories/              # Data access layer (optional)
│   │   ├── __init__.py
│   │   └── README.md              # Repositories guide
│   │
│   └── main.py                    # FastAPI app (health check only)
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   └── README.md                  # Testing guide
│
├── .github/
│   └── copilot-instructions.md    # AI agent guidelines
│
├── Docker files/                  # Docker configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
│
└── Makefile                       # Development commands
```

### Directory Reference

| Directory          | Purpose                         | Key Files                                                |
| ------------------ | ------------------------------- | -------------------------------------------------------- |
| `app/configs`      | Configuration & Redis setup     | `environment_configuration.py`, `redis_configuration.py` |
| `app/workers`      | Job handlers (RQ functions)     | `hello_world.py` (example pattern)                       |
| `app/api`          | FastAPI HTTP endpoints          | `routes.py`                                              |
| `app/dtos`         | Request/Response validation     | `__init__.py` (Pydantic models)                          |
| `app/services`     | Reusable business logic         | Shared services between API & workers                    |
| `app/controllers`  | Business logic layer (optional) | Controllers for complex workflows                        |
| `app/models`       | Database models (optional)      | SQLAlchemy models if using DB                            |
| `app/repositories` | Data access layer (optional)    | CRUD operations if using DB                              |
| `tests`            | Unit & integration tests        | `conftest.py` (pytest fixtures)                          |

## Architecture Layers

```
┌─────────────────────────────────────────┐
│         API Routes (HTTP)                │ ← External requests
├─────────────────────────────────────────┤
│  Controllers (Orchestration - optional)  │ ← Complex workflows
├─────────────────────────────────────────┤
│   Services (Shared Business Logic)      │ ← Reusable logic
├─────────────────────────────────────────┤
│     Workers (Job Execution - RQ)        │ ← Background tasks
├─────────────────────────────────────────┤
│  Models, DTOs, Repositories (Data)      │ ← Data & validation
├─────────────────────────────────────────┤
│  Configs (Settings & Redis - singleton) │ ← Infrastructure
└─────────────────────────────────────────┘
```

**Data Flow:**
1. API receives request → validates with **DTOs**
2. Route optionally uses **Controller** for orchestration
3. Logic handled by **Services** (shared between API & workers)
4. Job enqueued to Redis → **Worker** executes logic
5. Data persisted with **Models** & **Repositories**
6. Configuration managed by **Configs** (singleton pattern)

```bash
make help              # Show all commands
make worker            # Run worker locally
make worker-verbose    # Run with verbose logging
make redis-cli         # Connect to Redis CLI
make test              # Run tests
make docker-up         # Start Docker containers
make docker-down       # Stop Docker containers
make docker-logs       # View Docker logs
```

See [Makefile](Makefile) for all available commands.

## Documentation

- **Architecture**: [.github/copilot-instructions.md](.github/copilot-instructions.md)
- **Workers**: [app/workers/README.md](app/workers/README.md)
- **API**: [app/api/README.md](app/api/README.md)
- **DTOs**: [app/dtos/README.md](app/dtos/README.md)
- **Services**: [app/services/README.md](app/services/README.md)
- **Testing**: [tests/README.md](tests/README.md)
