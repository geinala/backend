import time
import functools
from contextlib import contextmanager
from typing import Any, Callable, TypeVar, cast, Generator
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


@contextmanager
def wide_event(event_type: str, **initial_context: Any) -> Generator[dict[str, object], None, None]:
    start_time = time.time()
    event_dict: dict[str, object] = {
        "event_type": event_type,
        "status": "processing",
        **initial_context
    }
    
    try:
        yield event_dict
        event_dict["status"] = "success"
        
    except Exception as e:
        event_dict["status"] = "failed"
        event_dict["error"] = str(e)
        event_dict["error_type"] = type(e).__name__
        logger.error(event_dict)
        raise e
        
    finally:
        event_dict["duration_ms"] = (time.time() - start_time) * 1000
        if event_dict["status"] == "success":
            logger.info(event_dict)


def wide_event_logger(event_type: str, **initial_context: Any) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with wide_event(event_type, **initial_context) as event:
                return await func(*args, event=event, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with wide_event(event_type, **initial_context) as event:
                return func(*args, event=event, **kwargs)
        
        if functools.iscoroutinefunction(func): # type: ignore [reportUnknownMemberType]
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)
    
    return decorator

