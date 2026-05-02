"""RQ scheduler bootstrap modules."""

def register_all_schedules() -> list[str]:
	from .bootstrap import register_all_schedules as _register_all_schedules

	return _register_all_schedules()

__all__ = ["register_all_schedules"]
