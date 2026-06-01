from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def now_utc() -> datetime:
    return timezone.now()


def business_timezone() -> ZoneInfo:
    return ZoneInfo(settings.TIME_ZONE)


def to_business_time(value: datetime) -> datetime:
    if timezone.is_naive(value):
        raise ValueError("Datetime must be timezone-aware.")
    return value.astimezone(business_timezone())


def business_date(value: datetime) -> date:
    return to_business_time(value).date()


def calendar_day_difference(start: datetime, end: datetime) -> int:
    return (business_date(end) - business_date(start)).days
