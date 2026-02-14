# Simulation App Solver Backend

Production-ready **message-driven worker service** for processing simulation jobs via Redis message broker (RQ).

- **Pure background processor** - Async job execution via RQ & Redis
- **Optional FastAPI** - REST API for job enqueueing (optional)
- **Type-safe** - Pydantic V2 DTOs and full type hints
- **Production-ready** - Logging, error handling, configuration management
- **Python 3.10+** with `uv` package manager

## Quick Start

### Prerequisites

1. **Python 3.10+**
2. **uv** package manager ([install](https://docs.astral.sh/uv/)).
3. **Redis** server running
4. **Make** (for Makefile commands)

### Setup

```bash
# Clone and setup
git clone <repo>
cd backend
uv sync

# Copy environment template
cp .env.example .env

# Start development services
make docker-up

# In separate terminal: Start worker
make worker

# Monitor via Redis CLI
redis-cli

# View logs
tail -f logs/app.log
```

## Architecture Overview

### Complete Request Flow

```
Upstream Service (API Gateway, Scheduler)
    ↓
Call Controller
    ↓
Controller validates + orchestrates
    ↓
Controller calls Service(s)
    ↓
Service contains business logic
    ↓
Service enqueues job to Redis Queue
    ↓
Redis Queue (message broker)
    ↓
RQ Worker picks up job
    ↓
Worker calls same Services for shared logic
    ↓
Worker calls Repository (if database needed)
    ↓
Worker processes and returns result
```

### Layers & Responsibilities

| Layer          | Purpose                       | Uses            | Called By              |
| -------------- | ----------------------------- | --------------- | ---------------------- |
| **Route**      | HTTP input/output             | DTOs            | Client                 |
| **Controller** | Orchestration + error mapping | Services, DTOs  | Route                  |
| **Service**    | Reusable business logic       | Configs, Models | Controller, Worker     |
| **Repository** | Database access               | Models          | Service                |
| **Worker**     | Job execution                 | Services, DTOs  | Queue                  |
| **Model**      | Database schema               | -               | Repository             |
| **DTO**        | Validation + serialization    | -               | Route, Service, Worker |
| **Config**     | Settings + singletons         | -               | All layers             |
| **Lib**        | Utilities (logging, etc.)     | -               | All layers             |

### Data Flow Diagram

```
┌─────────────────┐
│  HTTP Request   │
└────────┬─────── ┘
         ↓
┌─────────────────────────────────────────┐
│  API Route  (FastAPI)                   │
│  - Receives HTTP request                │
│  - Validates with DTO                   │
│  - Logs: "Route: Received..."           │
└────────┬────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Controller (Orchestration)             │
│  - Calls Services                       │
│  - Maps errors to API exceptions        │
│  - Logs: "Controller: Processing..."    │
└────────┬────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Service (Business Logic)               │
│  - Validates data                       │
│  - Transforms data                      │
│  - Enqueues job to Redis                │
│  - Logs: "Service: Enqueueing..."       │
└────────┬────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Redis Queue (Message Broker)           │
│  - Stores job in Redis                  │
│  - Worker picks up job                  │
└────────┬────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  RQ Worker (Background Execution)       │
│  - Receives job parameters              │
│  - Calls Services for business logic    │
│  - Accesses Database via Repository     │
│  - Logs: "Worker: Job X - Processing..."│
│  - Returns result                       │
└─────────────────────────────────────────┘
```

## Module Guide

### Core Modules

**[`app/api/`](./app/api/README.md)** - HTTP API routes

- Receives HTTP requests
- Validates request data with DTOs
- Calls controllers
- Returns JSON responses
- Handles HTTP exceptions

**[`app/controllers/`](./app/controllers/README.md)** - Request orchestration

- Coordinates multiple services
- Validates business logic
- Maps exceptions to API errors
- Implements per-domain orchestration

**[`app/services/`](./app/services/README.md)** - Reusable business logic

- Shared between controllers and workers
- Pure functions with no HTTP concerns
- Database operations via repositories
- External integrations

**[`app/workers/`](./app/workers/README.md)** - Background job handlers

- RQ job functions
- Called asynchronously by Redis queue
- Uses services for logic
- Tracks progress and results

### Data & Configuration

**[`app/dtos/`](./app/dtos/README.md)** - Request/Response DTOs

- Pydantic models for validation
- Type-safe data contracts
- Self-documenting API schema
- Auto-serialization to JSON

**[`app/models/`](./app/models/README.md)** - Database models (optional)

- SQLAlchemy ORM models
- Database schema definition
- Relationships and constraints
- Only needed if using database

**[`app/repositories/`](./app/repositories/README.md)** - Database access (optional)

- CRUD operations
- Query abstractions
- Isolation of data layer
- Easy testing with mocks

**[`app/configs/`](./app/configs/README.md)** - Configuration management

- Environment variables
- Redis & database connections
- Singleton pattern for safe access
- Settings from `.env` file

**[`app/lib/`](./app/lib/README.md)** - Utilities

- Logging setup and configuration
- Response formatting helpers
- Database utilities
- Shared infrastructure code

## Environment Configuration

Configure application via `.env` file:

```env
# Database (optional)
DB_HOST=localhost
DB_PORT=5432
DB_USERNAME=user
DB_PASSWORD=password
DB_NAME=simulation_db

# Redis (required)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# RQ Queue
RQ_QUEUE=default
RQ_JOB_TIMEOUT=10m
RQ_RESULT_TTL=300

# API
API_HOST=0.0.0.0
API_PORT=8000
API_TITLE=Simulation App Solver
API_VERSION=1.0.0

# CORS
CORS_ALLOW_ORIGINS=*
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS

# Documentation
ENABLE_DOCS=true
ENABLE_REDOC=true
ENABLE_OPENAPI=true

# Environment

ENVIRONMENT=development

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_FILE=app.log
LOG_BACKUP_COUNT=5
LOG_MAX_BYTES=10485760
ENABLE_FILE_LOGGING=false  # Console-only by default (development friendly)
```

## Project Structure

```
.
├── README.md                           # This file
├── Makefile                            # Build & run commands
├── pyproject.toml                      # Dependencies
├── .env.example                        # Environment template
├── .gitignore
│
├── app/                                # Application
│   ├── __init__.py
│   ├── main.py                         # FastAPI app
│   │
│   ├── api/                            # HTTP routes
│   │   ├── __init__.py
│   │   ├── jobs.py                     # /jobs endpoints
│   │   ├── exceptions/                 # Error handling
│   │   │   ├── __init__.py
│   │   │   └── base.py
│   │   └── README.md
│   │
│   ├── controllers/                    # Orchestration (optional)
│   │   ├── __init__.py
│   │   └── README.md
│   │
│   ├── services/                       # Business logic
│   │   ├── __init__.py
│   │   └── README.md
│   │
│   ├── workers/                        # Job handlers
│   │   ├── __init__.py
│   │   ├── hello_world.py              # Example
│   │   └── README.md
│   │
│   ├── dtos/                           # Request/Response models
│   │   ├── __init__.py
│   │   ├── api_response_dto.py
│   │   └── README.md
│   │
│   ├── models/                         # Database models (optional)
│   │   ├── __init__.py
│   │   └── README.md
│   │
│   ├── repositories/                   # Data access (optional)
│   │   ├── __init__.py
│   │   └── README.md
│   │
│   ├── configs/                        # Configuration
│   │   ├── __init__.py
│   │   ├── environment_configuration.py
│   │   ├── redis_configuration.py
│   │   ├── database_configuration.py
│   │   └── README.md
│   │
│   └── lib/                            # Utilities
│       ├── __init__.py
│       ├── logging.py
│       ├── response_formatter.py
│       ├── db.py
│       └── README.md
│
├── tests/                              # Test suite
│   ├── __init__.py
│   ├── conftest.py
│   └── README.md
│
├── logs/                               # Application logs
│   └── app.log
│
└── docker/                             # Docker files
    ├── Dockerfile
    ├── docker-compose.yml
    └── docker-compose.prod.yml
```

## Development Workflow

### Local Development

```bash
# Install + setup
uv sync
cp .env.example .env

# Terminal 1: Redis
redis-server

# Terminal 2: Worker
rq worker

# Terminal 3: API (optional)
python -m uvicorn app.main:app --reload

# Terminal 4: Monitor
redis-cli
```

### Using Docker

```bash
# Start all services
make docker-up

# View logs
make docker-logs

# Scale workers
docker-compose up -d --scale worker=3

# Stop
make docker-down
```

### Commands (Makefile)

```bash
make install        # Install dependencies
make worker         # Start RQ worker
make api            # Start FastAPI server
make docker-up      # Start Docker services
make docker-down    # Stop Docker services
make docker-logs    # View Docker logs
make test           # Run tests
make lint           # Run linters
make format         # Format code
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/workers/test_simulation.py

# With coverage
pytest --cov=app tests/
```

## Production Deployment

### Docker

```bash
# Build image
docker build -t sim-app .

# Run with production settings
docker-compose -f docker-compose.prod.yml up

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=5
```

### Environment Setup

For production, configure:

```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING

# Redis
REDIS_HOST=redis.example.com
REDIS_PASSWORD=<strong-password>

# Database
DB_HOST=db.example.com
DB_USERNAME=<username>
DB_PASSWORD=<strong-password>

# CORS
CORS_ALLOW_ORIGINS=https://app.example.com

# Documentation (disable in production)
ENABLE_DOCS=false
ENABLE_REDOC=false
```

## Module Documentation

Each module has comprehensive documentation:

- **[API Module](./app/api/README.md)** - Creating HTTP endpoints
- **[Controllers Module](./app/controllers/README.md)** - Orchestrating requests
- **[Services Module](./app/services/README.md)** - Business logic patterns
- **[Workers Module](./app/workers/README.md)** - Job handler patterns
- **[DTOs Module](./app/dtos/README.md)** - Request/response validation
- **[Models Module](./app/models/README.md)** - Database models
- **[Repositories Module](./app/repositories/README.md)** - Data access
- **[Configs Module](./app/configs/README.md)** - Configuration management
- **[Lib Module](./app/lib/README.md)** - Utilities and helpers

## Logging

Logs are automatically captured in console output. File logging is optional and controlled via environment variable.

**View logs:**

```bash
# View all logs (console output in real-time)
# No file needed if ENABLE_FILE_LOGGING=false

# If ENABLE_FILE_LOGGING=true, view file logs:
tail -f logs/app.log

# Filter by level
tail -f logs/app.log | grep ERROR

# By layer
tail -f logs/app.log | grep "Route:"     # API routes
tail -f logs/app.log | grep "Controller:" # Controllers
tail -f logs/app.log | grep "Service:"   # Services
tail -f logs/app.log | grep "Worker:"    # Workers
```

**Configure logging:**

```env
LOG_LEVEL=DEBUG                 # More verbose
LOG_LEVEL=WARNING               # Less verbose (production)
LOG_DIR=logs                    # Directory for log files (if enabled)
LOG_FILE=app.log                # Log filename
LOG_BACKUP_COUNT=5              # Number of backup files
LOG_MAX_BYTES=10485760          # Max file size (10 MB)
ENABLE_FILE_LOGGING=false       # Console-only (development)
ENABLE_FILE_LOGGING=true        # Write to file (production)
```

**Development vs Production:**

- **Development** (ENABLE_FILE_LOGGING=false): All logs to console, no files created
- **Production** (ENABLE_FILE_LOGGING=true): Logs to console AND rotating file with automatic cleanup

## Dependencies

- **rq** - Job queue
- **redis** - Message broker
- **fastapi** - HTTP API (optional)
- **pydantic** - Data validation
- **sqlalchemy** - Database ORM (optional)
- **python-json-logger** - JSON logging (optional)

## Troubleshooting

### Worker Not Processing Jobs

```bash
# Check Redis connection
redis-cli ping

# Check queue
redis-cli llen rq:queue:default

# Check worker logs
tail -f logs/app.log | grep "Worker:"
```

### Job Timeout

Jobs timeout if they take longer than configured:

```env
RQ_JOB_TIMEOUT=10m  # 10 minutes

# Increase for long-running jobs
RQ_JOB_TIMEOUT=30m  # 30 minutes
```

### Database Connection Issues

```bash
# Check connection string
python -c "from app.configs import get_environment_configuration; print(get_environment_configuration().database_url)"

# Test connection
psql $(python -c "from app.configs import get_environment_configuration; print(get_environment_configuration().database_url)")
```
