
import pytest
from unittest.mock import MagicMock, patch
from redis import Redis
from rq import Queue


@pytest.fixture
def mock_redis():
    return MagicMock(spec=Redis)


@pytest.fixture
def mock_job():
    job = MagicMock()
    job.id = "test-job-id"
    job.meta = {}
    job.save_meta = MagicMock()
    job.set_status = MagicMock()
    return job


@pytest.fixture
def mock_queue():
    return MagicMock(spec=Queue)
