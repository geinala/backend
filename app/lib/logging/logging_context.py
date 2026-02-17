
import time
from contextvars import ContextVar
from typing import Any, Optional
from uuid import uuid4

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
job_id_var: ContextVar[str] = ContextVar("job_id", default="")
request_context_var: ContextVar[dict[str, Any]] = ContextVar("request_context", default={})


def generate_request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def get_request_id() -> str:
    return request_id_var.get("")


def set_job_id(job_id: str) -> None:
    job_id_var.set(job_id)


def get_job_id() -> str:
    return job_id_var.get("")


def set_request_context(context: dict[str, Any]) -> None:
    request_context_var.set(context)


def get_request_context() -> dict[str, Any]:
    return request_context_var.get({})


def create_wide_event(
    event_type: str,
    request_id: Optional[str] = None,
    job_id: Optional[str] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    event = {
        "event_type": event_type,
    }
    
    request_id = request_id or get_request_id()
    if request_id:
        event["request_id"] = request_id
    
    job_id = job_id or get_job_id()
    if job_id:
        event["job_id"] = job_id
    
    context = get_request_context()
    if context:
        event.update(context)
    
    event.update(kwargs)
    
    return event


class WideEventTimer:
    
    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.end_time: float = 0.0
    
    def __enter__(self) -> "WideEventTimer":
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.end_time = time.time()
    
    @property
    def elapsed_ms(self) -> float:
        duration = (self.end_time - self.start_time) * 1000
        return round(duration, 2)
