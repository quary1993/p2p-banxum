from __future__ import annotations

from datetime import UTC, datetime

from backend.apps.platform_core.domain.time import business_date, calendar_day_difference


def test_business_date_uses_europe_zurich_boundary(settings) -> None:  # type: ignore[no-untyped-def]
    settings.TIME_ZONE = "Europe/Zurich"

    utc_time = datetime(2026, 6, 1, 22, 30, tzinfo=UTC)

    assert business_date(utc_time).isoformat() == "2026-06-02"


def test_calendar_day_difference_uses_business_dates(settings) -> None:  # type: ignore[no-untyped-def]
    settings.TIME_ZONE = "Europe/Zurich"

    start = datetime(2026, 6, 1, 22, 30, tzinfo=UTC)
    end = datetime(2026, 6, 6, 7, 0, tzinfo=UTC)

    assert calendar_day_difference(start, end) == 4
