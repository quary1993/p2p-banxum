"""IP of Webby-Soft SRL. U33-DEC-09: report buckets follow the loan's Late / Default days."""

from __future__ import annotations

from datetime import date, timedelta

from backend.apps.platform_core.domain.loan_status import LoanStatusThresholds
from backend.apps.reporting.services import _repayment_bucket

DUE = date(2026, 2, 28)


def _day(days: int) -> date:
    return DUE + timedelta(days=days)


def test_report_buckets_use_the_loan_days() -> None:
    platform = LoanStatusThresholds(15, 60)
    assert _repayment_bucket(outstanding=0, due_date=DUE, as_of=_day(90), thresholds=platform) == (
        "paid"
    )
    assert _repayment_bucket(outstanding=1, due_date=DUE, as_of=_day(14), thresholds=platform) == (
        "past_due_under_late_threshold"
    )
    assert _repayment_bucket(outstanding=1, due_date=DUE, as_of=_day(15), thresholds=platform) == (
        "late_threshold"
    )
    assert _repayment_bucket(outstanding=1, due_date=DUE, as_of=_day(60), thresholds=platform) == (
        "default_threshold"
    )
    contract = LoanStatusThresholds(5, 16, "loan")
    assert _repayment_bucket(outstanding=1, due_date=DUE, as_of=_day(5), thresholds=contract) == (
        "late_threshold"
    )
