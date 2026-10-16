"""Funding windows and source-level holding limits. IP of Webby-Soft SRL."""

from datetime import date, datetime, timedelta

from backend.apps.platform_core.domain.time import business_date

MAX_FUNDING_PERIOD_DAYS = 50
DEFAULT_FUNDING_PERIOD_DAYS = 30
# Legal limit: money may not stay on a balance longer than 60 Europe/Zurich days.
BALANCE_HOLDING_LIMIT_DAYS = 60
# Operating rule (owner decision 2026-10-16): money still not invested goes back to the
# investor's bank automatically after 58 days, before the legal limit. Setting
# `balance.auto_return_after_days`; this is its default.
BALANCE_AUTO_RETURN_AFTER_DAYS = 58
# Reminder holding days (setting `balance.reminder_days`). The last ones come before the
# return; the 2026-05-20 default was 25, 46, 53, 58, 59, 60.
DEFAULT_BALANCE_REMINDER_DAYS = (25, 46, 53, 56, 57, 58)
PREVIOUS_DEFAULT_BALANCE_REMINDER_DAYS = (25, 46, 53, 58, 59, 60)


def latest_funding_deadline(opening_date: date) -> date:
    # The deadline is the last inclusive subscription date; close runs next day.
    return opening_date + timedelta(days=MAX_FUNDING_PERIOD_DAYS - 1)


def normalized_auto_return_after_days(value: object) -> int:
    """The configured return day, or the default when the value is not a usable day count.

    The return can come earlier than the legal limit, never later.
    """
    if type(value) is not int or not 1 <= value <= BALANCE_HOLDING_LIMIT_DAYS:
        return BALANCE_AUTO_RETURN_AFTER_DAYS
    return value


def normalized_balance_reminder_days(value: object, *, return_after_days: int) -> tuple[int, ...]:
    """Configured reminder days up to the last day; the default when the value is unusable.

    Days after the last day are dropped: the money is returned (or, without a usable IBAN,
    gets its own notices) from the next day.
    """
    days: tuple[int, ...] = DEFAULT_BALANCE_REMINDER_DAYS
    if (
        isinstance(value, list)
        and value
        and all(type(day) is int and 1 <= day <= BALANCE_HOLDING_LIMIT_DAYS for day in value)
    ):
        days = tuple(value)
    return tuple(sorted({day for day in days if day <= return_after_days}))


def balance_deadline_date(withdrawal_deadline_at: datetime) -> date:
    """Europe/Zurich legal deadline date of a balance source (holding day 60).

    Penalty mode and penalties start the day after it.
    """
    return business_date(withdrawal_deadline_at)


def balance_last_day(*, withdrawal_deadline_at: datetime, return_after_days: int) -> date:
    """Last Europe/Zurich day the money may stay (holding day `return_after_days`, e.g. 58).

    On that day it can only be withdrawn (no investing or exchange). Counted back from the
    legal deadline, so FX proceeds keep the dates of the money they came from.
    """
    days_before_legal_deadline = BALANCE_HOLDING_LIMIT_DAYS - return_after_days
    return balance_deadline_date(withdrawal_deadline_at) - timedelta(
        days=days_before_legal_deadline
    )


def balance_return_date(*, withdrawal_deadline_at: datetime, return_after_days: int) -> date:
    """Day the platform returns money still not invested to the investor's bank (day 59)."""
    return balance_last_day(
        withdrawal_deadline_at=withdrawal_deadline_at, return_after_days=return_after_days
    ) + timedelta(days=1)


def balance_return_is_due(
    *, withdrawal_deadline_at: datetime, as_of: datetime, return_after_days: int
) -> bool:
    """True from the return date: the money must go back to the investor's bank."""
    return business_date(as_of) > balance_last_day(
        withdrawal_deadline_at=withdrawal_deadline_at, return_after_days=return_after_days
    )


def balance_is_overdue(*, withdrawal_deadline_at: datetime, as_of: datetime) -> bool:
    """True after the legal 60-day limit: penalty mode applies when no return was possible."""
    return business_date(as_of) > balance_deadline_date(withdrawal_deadline_at)


def balance_covers_funding(
    *,
    withdrawal_deadline_at: datetime,
    funding_deadline: date,
    as_of: datetime,
    return_after_days: int,
) -> bool:
    """A source can fund a loan only if the whole remaining window ends before its last day.

    The last subscription date must be earlier than the source's last day, so the funding
    close (the next day) happens at the latest on the last day.
    """
    last_day = balance_last_day(
        withdrawal_deadline_at=withdrawal_deadline_at, return_after_days=return_after_days
    )
    return business_date(as_of) < last_day and funding_deadline < last_day


def balance_holding_day(*, withdrawal_deadline_at: datetime, as_of: datetime) -> int:
    """Holding day counted back from the deadline, so FX proceeds keep the source's age."""
    days_left = (balance_deadline_date(withdrawal_deadline_at) - business_date(as_of)).days
    return BALANCE_HOLDING_LIMIT_DAYS - days_left
