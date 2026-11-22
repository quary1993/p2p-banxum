"""Late and default status thresholds of a loan (U33-DEC-09). IP of Webby-Soft SRL.

Days past due are Europe/Zurich calendar days between the due date of the first unpaid
installment and the business date of the check (the due date itself is day 0):

- day 0 to the day before the late threshold: the payment is "Due" (the loan stays
  ``active``; the real number of overdue days is still shown);
- from the late threshold (default day 15): the loan is ``late``, also beyond the default
  threshold;
- from the default threshold (default day 60) the admin **may** declare Default (18.6, Vlad
  2026-11-17): it is never automatic; the loan is ``defaulted`` only after the declaration.

The platform values are the settings ``servicing.late_threshold_days`` and
``servicing.default_threshold_days``. A loan can carry its contract's own pair. Default
does not end the contract: the termination is a separate admin event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

DEFAULT_LATE_THRESHOLD_DAYS = 15
DEFAULT_DEFAULT_THRESHOLD_DAYS = 60
MAX_THRESHOLD_DAYS = 365

SOURCE_PLATFORM = "platform"
SOURCE_LOAN = "loan"


@dataclass(frozen=True, slots=True)
class LoanStatusThresholds:
    late_days: int
    default_days: int
    source: str = SOURCE_PLATFORM


def valid_threshold_pair(late_days: object, default_days: object) -> bool:
    """1 <= late < default <= 365, whole days."""
    return (
        type(late_days) is int
        and type(default_days) is int
        and 1 <= late_days < default_days <= MAX_THRESHOLD_DAYS
    )


def platform_thresholds(late_days: object, default_days: object) -> LoanStatusThresholds:
    """The configured platform pair, or the U33-DEC-09 defaults when it is not usable."""
    if valid_threshold_pair(late_days, default_days):
        return LoanStatusThresholds(cast(int, late_days), cast(int, default_days))
    return LoanStatusThresholds(DEFAULT_LATE_THRESHOLD_DAYS, DEFAULT_DEFAULT_THRESHOLD_DAYS)


def servicing_status_for_days_past_due(days_past_due: int, thresholds: LoanStatusThresholds) -> str:
    """``active`` (on schedule, pending or due) or ``late``; never ``defaulted`` (18.6)."""
    if days_past_due >= thresholds.late_days:
        return "late"
    return "active"


def default_can_be_declared(days_past_due: int, thresholds: LoanStatusThresholds) -> bool:
    """18.6: the oldest unpaid installment is late by at least the Default days."""
    return days_past_due >= thresholds.default_days
