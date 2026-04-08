from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Return current UTC time with millisecond precision (truncate microseconds for iOS compatibility)."""
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def local_now(timezone_name: str) -> datetime:
    return utc_now().astimezone(ZoneInfo(timezone_name))


def local_date(timezone_name: str) -> date:
    return local_now(timezone_name).date()
