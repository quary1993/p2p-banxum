from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.apps.platform_core.domain.funding import (
    balance_covers_funding,
    latest_funding_deadline,
)


@pytest.mark.parametrize("month,day", [(1, 1), (3, 20), (10, 20)])
@pytest.mark.parametrize("remaining_days", [1, 5, 10, 30, 50])
def test_source_covers_exact_remaining_window_in_zurich_calendar_days(
    month: int, day: int, remaining_days: int
) -> None:
    opening = datetime(2026, month, day, tzinfo=ZoneInfo("Europe/Zurich"))
    holding_deadline = opening + timedelta(days=remaining_days)
    last_subscription_date = holding_deadline.date() - timedelta(days=1)
    assert balance_covers_funding(
        withdrawal_deadline_at=holding_deadline,
        funding_deadline=last_subscription_date,
        as_of=opening + timedelta(hours=12),
    )
    assert not balance_covers_funding(
        withdrawal_deadline_at=holding_deadline,
        funding_deadline=last_subscription_date + timedelta(days=1),
        as_of=opening,
    )
    assert not balance_covers_funding(
        withdrawal_deadline_at=holding_deadline,
        funding_deadline=last_subscription_date,
        as_of=holding_deadline,
    )
    assert (latest_funding_deadline(opening.date()) - opening.date()).days + 1 == 50
