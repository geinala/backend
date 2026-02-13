"""Test configuration and fixtures."""

import pytest
from unittest.mock import MagicMock, patch
from redis import Redis
from rq import Queue


@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing."""
    return MagicMock(spec=Redis)


@pytest.fixture
def mock_job():
    """Mock RQ job for testing job handlers."""
    job = MagicMock()
    job.id = "test-job-id"
    job.meta = {}
    job.save_meta = MagicMock()
    job.set_status = MagicMock()
    return job


@pytest.fixture
def mock_queue():
    """Mock RQ Queue for testing."""
    return MagicMock(spec=Queue)
