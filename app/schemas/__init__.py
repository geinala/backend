"""Pydantic schemas for job input/output validation."""

from pydantic import BaseModel, Field
from typing import Optional, Any


class SimulationConfig(BaseModel):
    """Configuration schema for simulation jobs."""
    
    name: str = Field(..., description="Simulation name/identifier")
    parameters: dict = Field(default_factory=dict, description="Simulation parameters")
    timeout: Optional[int] = Field(default=300, description="Job timeout in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "test_sim_001",
                "parameters": {"iterations": 1000, "precision": 0.01},
                "timeout": 600
            }
        }


class JobResult(BaseModel):
    """Standard job result schema."""
    
    status: str = Field(..., description="Job status: success, failed, timeout")
    result: Optional[Any] = Field(default=None, description="Job result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    job_id: Optional[str] = Field(default=None, description="RQ job ID")
    timestamp: str = Field(..., description="ISO format timestamp")
