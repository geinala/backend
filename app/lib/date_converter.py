from datetime import datetime
from zoneinfo import ZoneInfo

def format_departure_time(
    departure_time: datetime | None,
    timezone: str = "Asia/Jakarta",
) -> str | None:
    if departure_time is None:
        return None

    return departure_time.astimezone(
        ZoneInfo(timezone)
    ).isoformat(timespec="seconds")