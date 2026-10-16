from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.apps.platform_core.domain.funding import (
    BALANCE_AUTO_RETURN_AFTER_DAYS,
    DEFAULT_BALANCE_REMINDER_DAYS,
    balance_covers_funding,
    balance_deadline_date,
    balance_holding_day,
    balance_is_overdue,
    balance_last_day,
    balance_return_date,
    balance_return_is_due,
    latest_funding_deadline,
    normalized_auto_return_after_days,
    normalized_balance_reminder_days,
)

ZURICH = ZoneInfo("Europe/Zurich")


def _at(value: date, hour: int = 12) -> datetime:
    return datetime.combine(value, time(hour), tzinfo=ZURICH)


@pytest.mark.parametrize("month,day", [(1, 1), (3, 20), (10, 20)])
@pytest.mark.parametrize("remaining_days", [1, 5, 10, 30, 50])
def test_source_covers_exact_remaining_window_before_its_last_day(
    month: int, day: int, remaining_days: int
) -> None:
    opening = datetime(2026, month, day, tzinfo=ZURICH)
    # The source's last day (day 58) is `remaining_days` away; the legal deadline 2 days later.
    last_day = opening.date() + timedelta(days=remaining_days)
    holding_deadline = opening + timedelta(days=remaining_days + 2)
    last_subscription_date = last_day - timedelta(days=1)

    def covers(funding_deadline: date, as_of: datetime) -> bool:
        return balance_covers_funding(
            withdrawal_deadline_at=holding_deadline,
            funding_deadline=funding_deadline,
            as_of=as_of,
            return_after_days=58,
        )

    assert balance_last_day(withdrawal_deadline_at=holding_deadline, return_after_days=58) == (
        last_day
    )
    assert covers(last_subscription_date, opening + timedelta(hours=12))
    assert not covers(last_subscription_date + timedelta(days=1), opening)
    # On its last day the source can no longer fund anything, not even a same-day window.
    assert not covers(last_subscription_date, _at(last_day, 0))
    assert (latest_funding_deadline(opening.date()) - opening.date()).days + 1 == 50


def test_day_58_is_the_last_day_and_the_money_goes_back_on_day_59() -> None:
    # Received 2026-01-01 (day 0): legal deadline 2026-03-02 (day 60).
    deadline_at = datetime(2026, 3, 2, tzinfo=ZURICH)
    last_day = balance_last_day(withdrawal_deadline_at=deadline_at, return_after_days=58)
    return_date = balance_return_date(withdrawal_deadline_at=deadline_at, return_after_days=58)

    assert BALANCE_AUTO_RETURN_AFTER_DAYS == 58
    assert balance_deadline_date(deadline_at) == date(2026, 3, 2)
    assert (last_day, return_date) == (date(2026, 2, 28), date(2026, 3, 1))
    assert balance_holding_day(withdrawal_deadline_at=deadline_at, as_of=_at(last_day)) == 58
    assert balance_holding_day(withdrawal_deadline_at=deadline_at, as_of=_at(return_date)) == 59

    def due(value: date, hour: int = 12) -> bool:
        return balance_return_is_due(
            withdrawal_deadline_at=deadline_at, as_of=_at(value, hour), return_after_days=58
        )

    def overdue(value: date) -> bool:
        return balance_is_overdue(withdrawal_deadline_at=deadline_at, as_of=_at(value))

    # Day 58, even late in the evening: still the investor's day. Day 59: due back.
    assert not due(date(2026, 2, 28), 23)
    assert due(date(2026, 3, 1), 0)
    # Penalties follow the legal limit only: day 61 and later.
    assert not overdue(date(2026, 3, 1))
    assert not overdue(date(2026, 3, 2))
    assert overdue(date(2026, 3, 3))


def test_return_day_is_configurable_but_never_after_the_legal_limit() -> None:
    deadline_at = datetime(2026, 3, 2, tzinfo=ZURICH)
    # 60 is the old rule: the last day is the legal deadline date itself.
    assert balance_last_day(withdrawal_deadline_at=deadline_at, return_after_days=60) == date(
        2026, 3, 2
    )
    assert balance_last_day(withdrawal_deadline_at=deadline_at, return_after_days=55) == date(
        2026, 2, 25
    )
    assert normalized_auto_return_after_days(55) == 55
    assert normalized_auto_return_after_days(60) == 60
    for invalid in (None, 0, 61, "58", 58.0, True):
        assert normalized_auto_return_after_days(invalid) == 58


def test_reminder_days_end_on_the_last_day() -> None:
    assert DEFAULT_BALANCE_REMINDER_DAYS == (25, 46, 53, 56, 57, 58)
    assert normalized_balance_reminder_days(None, return_after_days=58) == (
        25,
        46,
        53,
        56,
        57,
        58,
    )
    # The old schedule keeps only the days up to the last day.
    assert normalized_balance_reminder_days([25, 46, 53, 58, 59, 60], return_after_days=58) == (
        25,
        46,
        53,
        58,
    )
    assert normalized_balance_reminder_days([58, 10, 10], return_after_days=58) == (10, 58)
    for invalid in ([], [0, 25], [25, 61], ["25"], {"days": [25]}):
        assert normalized_balance_reminder_days(invalid, return_after_days=58) == (
            DEFAULT_BALANCE_REMINDER_DAYS
        )
