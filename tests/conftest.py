
import pytest
from unittest.mock import MagicMock
from redis import Redis
from rq import Queue, Job


@pytest.fixture
def mock_redis(mocker):
    return MagicMock(spec=Redis)


@pytest.fixture
def mock_job():
    job = MagicMock(spec=Job)
    job.id = "test-job-id-123"
    job.meta = {}
    job.save_meta = MagicMock()
    job.set_status = MagicMock()
    job.exc_info = None
    return job


@pytest.fixture
def mock_queue(mock_redis):
    queue = MagicMock(spec=Queue)
    queue.enqueue = MagicMock()
    queue.connection = mock_redis
    return queue


@pytest.fixture
def sample_simulation_config():
    return {
        "name": "test_simulation_001",
        "parameters": {
            "iterations": 100,
            "precision": 0.01,
            "seed": 42
        },
        "timeout": 600
    }
