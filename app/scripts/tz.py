"""Timezone helpers without external tzdata (Windows has no zoneinfo database).

Moscow is UTC+3 all year. London follows the EU rule: BST from the last Sunday
of March 01:00 UTC to the last Sunday of October 01:00 UTC.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone


def _last_sunday(year: int, month: int) -> date:
    day = calendar.monthrange(year, month)[1]
    value = date(year, month, day)
    while value.weekday() != 6:
        value -= timedelta(days=1)
    return value


def london_offset(utc: datetime) -> timedelta:
    if utc.tzinfo is None:
        utc = utc.replace(tzinfo=timezone.utc)
    utc = utc.astimezone(timezone.utc)
    start = datetime.combine(
        _last_sunday(utc.year, 3), datetime.min.time(), timezone.utc
    ) + timedelta(hours=1)
    end = datetime.combine(
        _last_sunday(utc.year, 10), datetime.min.time(), timezone.utc
    ) + timedelta(hours=1)
    return timedelta(hours=1) if start <= utc < end else timedelta(0)


def to_london(utc: datetime) -> datetime:
    utc = utc.astimezone(timezone.utc)
    offset = london_offset(utc)
    return utc.astimezone(timezone(offset))


def to_moscow(utc: datetime) -> datetime:
    return utc.astimezone(timezone.utc).astimezone(MOSCOW)


MOSCOW = timezone(timedelta(hours=3))
