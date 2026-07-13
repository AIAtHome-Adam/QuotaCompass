from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = {
    name: index for index, name in enumerate(("mon", "tue", "wed", "thu", "fri", "sat", "sun"))
}


def next_reset(cadence: str, timezone: str, *, now: datetime | None = None) -> datetime:
    """Return the next daily/weekly wall-clock reset as an offset-aware UTC datetime."""
    current = (now or datetime.now(UTC)).astimezone(ZoneInfo(timezone))
    weekly = re.fullmatch(r"weekly:(mon|tue|wed|thu|fri|sat|sun)\s+(\d{1,2}):(\d{2})", cadence)
    daily = re.fullmatch(r"daily:\s*(\d{1,2}):(\d{2})", cadence)
    if weekly:
        day, hour_text, minute_text = weekly.groups()
        days = (WEEKDAYS[day] - current.weekday()) % 7
    elif daily:
        hour_text, minute_text = daily.groups()
        days = 0
    else:
        raise ValueError("cadence must be `daily: HH:MM` or `weekly:day HH:MM`")
    hour, minute = int(hour_text), int(minute_text)
    if hour > 23 or minute > 59:
        raise ValueError("cadence time is outside the 24-hour clock")
    date = current.date() + timedelta(days=days)
    candidate = datetime(date.year, date.month, date.day, hour, minute, tzinfo=current.tzinfo)
    if candidate <= current:
        candidate += timedelta(days=7 if weekly else 1)
    return candidate.astimezone(UTC)
