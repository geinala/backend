"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import MagicMock
from redis import Redis
from rq import Queue, Job


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis connection for testing."""
    return MagicMock(spec=Redis)


@pytest.fixture
def mock_job():
    """Mock RQ job for testing job handlers."""
    job = MagicMock(spec=Job)
    job.id = "test-job-id-123"
    job.meta = {}
    job.save_meta = MagicMock()
    job.set_status = MagicMock()
    job.exc_info = None
    return job


@pytest.fixture
def mock_queue(mock_redis):
    """Mock RQ Queue for testing."""
    queue = MagicMock(spec=Queue)
    queue.enqueue = MagicMock()
    queue.connection = mock_redis
    return queue


@pytest.fixture
def sample_simulation_config():
    """Sample simulation configuration for testing."""
    return {
        "name": "test_simulation_001",
        "parameters": {
            "iterations": 100,
            "precision": 0.01,
            "seed": 42
        },
        "timeout": 600
    }
