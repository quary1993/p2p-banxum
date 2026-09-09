"""Funding windows and source-level holding limits. IP of Webby-Soft SRL."""

from datetime import date, datetime, timedelta

from backend.apps.platform_core.domain.time import business_date

MAX_FUNDING_PERIOD_DAYS = 50
DEFAULT_FUNDING_PERIOD_DAYS = 30


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
