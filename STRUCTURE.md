# Simulation App Solver - Project Structure

Complete project directory tree with guides for each module.

## Full Directory Structure

```
.
├── README.md                      # This file
├── pyproject.toml                 # Project dependencies (uv)
├── .env.example                   # Example environment variables
│
├── app/                           # Main application package
│   ├── __init__.py
│   │
│   ├── core/                      # Configuration & setup
│   │   ├── __init__.py            # Redis & Queue helpers
│   │   ├── config.py              # Environment settings
│   │   └── README.md              # Core module guide
│   │
│   ├── workers/                   # RQ job handlers
│   │   ├── __init__.py
│   │   ├── simulation.py          # Example: simulation handler
│   │   └── README.md              # Workers guide & patterns
│   │
│   ├── schemas/                   # Pydantic validation models
│   │   ├── __init__.py            # SimulationConfig, JobResult
│   │   └── README.md              # Schemas guide
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── README.md                  # Testing guide
│   ├── unit/                      # Unit tests
│   │   └── test_workers/
│   │       └── test_simulation.py
│   └── integration/               # Integration tests
│       └── test_job_processing.py
│
├── .github/
│   └── copilot-instructions.md    # AI agent guidelines
│
└── .agents/
    └── skills/                    # Installed agent skills
        └── fastapi-templates/     # FastAPI skill
```

## Quick Reference

| Directory     | Purpose                  | Key Files                              |
| ------------- | ------------------------ | -------------------------------------- |
| `app/core`    | Config & Redis setup     | `config.py`, `__init__.py`             |
| `app/workers` | Job handlers             | `simulation.py` (example pattern)      |
| `app/schemas` | Data validation          | `__init__.py` (Pydantic models)        |
| `tests`       | Unit & integration tests | `conftest.py`, `unit/`, `integration/` |

## Getting Started

### 1. Setup Environment

```bash
# Install dependencies
uv sync

# Create .env file
cp .env.example .env
# Edit .env with your Redis connection
```

### 2. Run Worker

```bash
# Start worker (listens to Redis queue)
rq worker

# In another terminal, enqueue jobs or monitor
redis-cli
```

### 3. Enqueue Jobs (from external service)

```python
from rq import Queue
from redis import Redis

redis = Redis()
q = Queue(connection=redis)

# This enqueues a job
job = q.enqueue(
    'app.workers.simulation.process_simulation',
    {
        "name": "my_sim",
        "parameters": {"iterations": 1000},
        "timeout": 600
    }
)

print(f"Job ID: {job.id}")
```

## Key Patterns

### Add New Job Handler

1. Create `app/workers/feature_name.py`
2. Define `async def handle_feature(params_dict: dict)` function
3. Use `current_job()` for metadata tracking
4. Return result dictionary

See [app/workers/README.md](app/workers/README.md) for examples.

### Add New Validation Schema

1. Create model in `app/schemas/__init__.py` using Pydantic
2. Use `Field(...)` for documentation
3. Import and use in job handlers for validation

See [app/schemas/README.md](app/schemas/README.md) for examples.

### Environment Configuration

Set variables in `.env`:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
RQ_QUEUE=default
ENVIRONMENT=development
```

See [app/core/README.md](app/core/README.md) for all options.

## Development Commands

```bash
# Install dependencies
uv sync

# Start RQ worker (listens to Redis queue)
rq worker

# Start FastAPI health check server
uv run fastapi dev app/main.py

# Run tests
pytest

# Test with coverage
pytest --cov=app

# Run specific test
pytest tests/unit/test_workers/test_simulation.py -v
```

## Documentation

- **Overall Architecture**: `.github/copilot-instructions.md`
- **Workers Guide**: `app/workers/README.md`
- **Configuration**: `app/core/README.md`
- **Schemas**: `app/schemas/README.md`
- **Testing**: `tests/README.md`

## Technology Stack

- **Python**: 3.10+
- **Package Manager**: `uv` (unified Python packaging)
- **Job Queue**: RQ (Redis Queue)
- **Message Broker**: Redis
- **Validation**: Pydantic V2
- **Scheduler**: RQ-Scheduler
- **Events**: CloudEvents Python

## Project Type

🔧 **Backend Worker Service**

- ❌ Not a REST API (no HTTP endpoints)
- ✅ Message broker-driven (Redis + RQ)
- ✅ Async job processing
- ✅ Pure background process
- ✅ Designed for horizontal scaling

## Next Steps

1. Read `.github/copilot-instructions.md` (AI agent guidelines)
2. Review `app/workers/simulation.py` (example pattern)
3. Check `tests/README.md` for testing approach
4. Create your first job handler following the pattern
5. Write tests using fixtures in `tests/conftest.py`
