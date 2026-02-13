# Schemas Module

Pydantic models for data validation (job inputs, outputs, messages).

## Purpose

This module contains **Pydantic V2 schemas** for:
- Validating job input parameters before processing
- Ensuring type safety and error handling
- Documenting expected data structures
- Supporting CloudEvents message validation

## Structure

```
schemas/
├── __init__.py         # Core schemas
├── simulation.py       # Simulation-specific schemas
├── events.py           # CloudEvents schemas (optional)
└── README.md
```

## Core Schemas

### SimulationConfig

Input schema for simulation jobs:

```python
from app.schemas import SimulationConfig

config = SimulationConfig(
    name = "experiment_001",
    parameters = {"iterations": 1000},
    timeout = 600
)
# Access: config.name, config.parameters, config.timeout
```

### JobResult

Standard output schema:

```python
from app.schemas import JobResult

result = JobResult(
    status="success",
    result={"data": [1, 2, 3]},
    job_id="job_123",
    timestamp="2026-02-13T10:30:00"
)
```

## Creating New Schemas

### Pattern

```python
from pydantic import BaseModel, Field
from typing import Optional

class MyJobConfig(BaseModel):
    """Schema for MyJob input."""
    
    param1: str = Field(..., description="Required parameter")
    param2: Optional[int] = Field(default=10, description="Optional with default")
    
    class Config:
        json_schema_extra = {
            "example": {
                "param1": "value",
                "param2": 42
            }
        }
```

## Using in Job Handlers

```python
from rq import current_job
from app.schemas import SimulationConfig, JobResult

def process_simulation(config_data: dict) -> dict:
    """Process simulation with validated input."""
    
    # Validate input
    config = SimulationConfig(**config_data)  # Raises ValidationError if invalid
    
    # Process
    result = run_simulation(config)
    
    # Return validated output
    job = current_job()
    output = JobResult(
        status="success",
        result=result,
        job_id=job.id,
        timestamp=datetime.now().isoformat()
    )
    
    return output.model_dump()  # Convert to dict for Redis storage
```

## Validation Errors

Pydantic automatically raises `ValidationError`:

```python
try:
    config = SimulationConfig(**invalid_data)
except ValidationError as e:
    print(e.errors())  # List of validation errors
```

In job handlers, validation errors automatically fail the job in RQ.

## CloudEvents (Optional)

For event-driven communication with external services:

```python
# In schemas/events.py
from pydantic import BaseModel

class CloudEventInput(BaseModel):
    """Standard CloudEvents format."""
    specversion: str = "1.0"
    type: str
    source: str
    id: str
    data: dict
```

Then use in handlers to publish events after job completion.

## Testing Schemas

```python
from app.schemas import SimulationConfig

def test_valid_config():
    config = SimulationConfig(
        name="test",
        parameters={"key": "value"}
    )
    assert config.name == "test"

def test_invalid_config():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SimulationConfig(name=123)  # name must be str
```

## Best Practices

1. **Always document** fields with `Field(..., description="...")`
2. **Use Optional** for nullable fields with defaults
3. **Provide examples** in `Config.json_schema_extra`
4. **Reuse schemas** - don't duplicate validation logic
5. **Keep schemas simple** - complex logic goes in handlers, not schemas
