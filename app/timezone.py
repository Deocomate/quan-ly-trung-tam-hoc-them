from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except ZoneInfoNotFoundError:
    VIETNAM_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def now_vietnam() -> datetime:
    return datetime.now(VIETNAM_TZ)


def today_vietnam() -> date:
    return now_vietnam().date()


def parse_local_date(value: str) -> date:
    return date.fromisoformat(value)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end
