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
app/
├── workers/           # Job handlers (RQ functions)
│   ├── simulation.py  # Example: simulation job
│   └── __init__.py
├── core/              # Configuration & Redis setup
│   ├── config.py
│   └── __init__.py
└── schemas/           # Pydantic validation models
    └── __init__.py

make/                  # Helper scripts
├── docker/            # Docker files
└── scripts/           # Development utilities
```

## Available Commands

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
- **Project Structure**: [STRUCTURE.md](STRUCTURE.md)
- **Workers**: [app/workers/README.md](app/workers/README.md)
- **Configuration**: [app/core/README.md](app/core/README.md)
- **Testing**: [tests/README.md](tests/README.md)
