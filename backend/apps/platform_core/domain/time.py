from __future__ import annotations

from datetime import date, datetime
from typing import cast
from zoneinfo import ZoneInfo

from django.apps import apps
from django.conf import settings
from django.core.exceptions import AppRegistryNotReady
from django.db import DatabaseError, ProgrammingError
from django.utils import timezone


def now_utc() -> datetime:
    override = _qa_dev_mode_time_override()
    return override or timezone.now()


def _qa_dev_mode_time_override() -> datetime | None:
    if not bool(getattr(settings, "QA_DEV_MODE_ALLOWED", False)):
        return None
    if bool(getattr(settings, "IS_PRODUCTION", False)):
        return None
    try:
        services = __import__(
            "backend.apps.platform_core.services.qa_dev_mode",
            fromlist=["qa_time_override_from_db"],
        )
        if not apps.ready:
            return None
        return cast(datetime | None, services.qa_time_override_from_db())
    except (AppRegistryNotReady, DatabaseError, ProgrammingError, RuntimeError):
        return None


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
