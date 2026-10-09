"""Funding windows and source-level holding limits. IP of Webby-Soft SRL."""

from datetime import date, datetime, timedelta

from backend.apps.platform_core.domain.time import business_date

MAX_FUNDING_PERIOD_DAYS = 50
DEFAULT_FUNDING_PERIOD_DAYS = 30
BALANCE_HOLDING_LIMIT_DAYS = 60


def latest_funding_deadline(opening_date: date) -> date:
    # The deadline is the last inclusive subscription date; close runs next day.
    return opening_date + timedelta(days=MAX_FUNDING_PERIOD_DAYS - 1)


def balance_covers_funding(
    *, withdrawal_deadline_at: datetime, funding_deadline: date, as_of: datetime
) -> bool:
    return (
        business_date(as_of) < business_date(withdrawal_deadline_at)
        and funding_deadline < business_date(withdrawal_deadline_at)
    )


def balance_deadline_date(withdrawal_deadline_at: datetime) -> date:
    """Europe/Zurich withdrawal deadline date of a balance source (holding day 60).

    It is the last day the money may stay on the account: the investor can withdraw it
    until the end of that day. Forced return, penalty mode and penalties start the day after.
    """
    return business_date(withdrawal_deadline_at)


def balance_is_overdue(*, withdrawal_deadline_at: datetime, as_of: datetime) -> bool:
    return business_date(as_of) > balance_deadline_date(withdrawal_deadline_at)


def balance_holding_day(*, withdrawal_deadline_at: datetime, as_of: datetime) -> int:
    """Holding day counted back from the deadline, so FX proceeds keep the source's age."""
    days_left = (balance_deadline_date(withdrawal_deadline_at) - business_date(as_of)).days
    return BALANCE_HOLDING_LIMIT_DAYS - days_left
