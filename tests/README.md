# Tests Directory

Unit and integration tests for the worker service.

## Purpose

Test coverage for:
- Job handlers validation and logic
- Pydantic schema validation
- Configuration loading
- Redis/RQ integration

## Structure

```
tests/
├── __init__.py           # Test fixtures and configuration
├── conftest.py           # Pytest configuration
├── unit/
│   ├── test_schemas.py
│   ├── test_config.py
│   └── test_workers/
│       └── test_simulation.py
├── integration/
│   └── test_job_processing.py
└── README.md
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app

# Specific file
pytest tests/unit/test_config.py

# Verbose output
pytest -v

# Watch mode (if pytest-watch installed)
ptw
```

## Writing Tests for Job Handlers

### Example: Test Simulation Handler

```python
# tests/unit/test_workers/test_simulation.py
import pytest
from unittest.mock import patch
from app.workers.simulation import process_simulation
from app.schemas import SimulationConfig

def test_process_simulation_success(mock_job):
    """Test successful simulation execution."""
    with patch('rq.current_job', return_value=mock_job):
        result = process_simulation({
            "name": "test_sim",
            "parameters": {},
            "timeout": 300
        })
        
        assert result["status"] == "success"
        assert "result" in result
        assert mock_job.save_meta.called


def test_process_simulation_invalid_config(mock_job):
    """Test validation error handling."""
    with patch('rq.current_job', return_value=mock_job):
        with pytest.raises(ValueError):
            process_simulation({
                "name": 123,  # Invalid: should be str
                "parameters": {}
            })
```

### Mock Fixtures

Use provided fixtures from `conftest.py`:

```python
def test_with_mocks(mock_job, mock_redis, mock_queue):
    """Test using mock fixtures."""
    # mock_job - RQ job mock with meta tracking
    # mock_redis - Redis client mock
    # mock_queue - RQ Queue mock
    pass
```

## Testing Schemas

```python
# tests/unit/test_schemas.py
import pytest
from pydantic import ValidationError
from app.schemas import SimulationConfig

def test_valid_config():
    config = SimulationConfig(
        name="test",
        parameters={"x": 1}
    )
    assert config.name == "test"

def test_invalid_name_type():
    with pytest.raises(ValidationError):
        SimulationConfig(
            name=123,  # Should be string
            parameters={}
        )
```

## Testing Configuration

```python
# tests/unit/test_config.py
import os
from app.core.config import Settings

def test_settings_from_env(monkeypatch):
    """Test settings loading from environment variables."""
    monkeypatch.setenv("REDIS_HOST", "test-host")
    monkeypatch.setenv("REDIS_PORT", "9999")
    
    settings = Settings()
    assert settings.REDIS_HOST == "test-host"
    assert settings.REDIS_PORT == 9999
```

## Integration Tests

For testing with real/containerized Redis:

```python
# tests/integration/test_job_processing.py
import pytest
from redis import Redis
from rq import Queue
from app.workers.simulation import process_simulation

@pytest.mark.integration
def test_job_enqueue_and_process():
    """Test enqueuing and processing a job."""
    redis = Redis(host="localhost", port=6379)
    q = Queue(connection=redis)
    
    job = q.enqueue(process_simulation, {
        "name": "integration_test",
        "parameters": {}
    })
    
    assert job.id is not None
    # Additional assertions
```

## Coverage Requirements

Aim for:
- ✅ 80%+ coverage on `app/workers/`
- ✅ 80%+ coverage on `app/schemas/`
- ✅ 100% coverage on `app/core/config.py`
- ✅ Integration tests for critical job handlers

Generate coverage report:

```bash
pytest --cov=app --cov-report=html
# Open htmlcov/index.html
```

## CI/CD Integration

In GitHub Actions or similar CI:

```yaml
- name: Run tests
  run: pytest --cov=app
  
- name: Check coverage
  if: ${{ github.event_name == 'pull_request' }}
  run: pytest --cov=app --cov-fail-under=80
```

## Troubleshooting

- **Fixtures not found**: Ensure `conftest.py` is in tests directory
- **Imports fail in tests**: Add `PYTHONPATH=.` to pytest configuration
- **Mocks not working**: Use `patch` context manager or decorator
- **Redis connection errors**: Use mocks instead of real Redis in unit tests
