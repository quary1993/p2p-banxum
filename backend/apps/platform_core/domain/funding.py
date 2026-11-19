"""Funding windows and source-level holding limits. IP of Webby-Soft SRL."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol

from backend.apps.platform_core.domain.time import business_date, business_timezone

MAX_FUNDING_PERIOD_DAYS = 50
DEFAULT_FUNDING_PERIOD_DAYS = 30
# Legal limit: money may not stay on a balance longer than 60 Europe/Zurich days.
BALANCE_HOLDING_LIMIT_DAYS = 60
# Q01 (U33-DEC-03, 18.4): the value date of a lot is day 0; day 56 is the last day (withdraw only)
# and the return request is normally made on day 57. Setting `balance.auto_return_after_days`
# for new lots; each lot keeps the days it was created with.
BALANCE_AUTO_RETURN_AFTER_DAYS = 56
# Lots created before the switch keep the 58-day rule of 2026-10-16 and its dates (no calendar
# adjustment). A lot with more days than the current maximum is treated the same way.
LEGACY_BALANCE_RETURN_AFTER_DAYS = 58
MAX_BALANCE_RETURN_AFTER_DAYS = BALANCE_AUTO_RETURN_AFTER_DAYS
# The debit of Garanta's account is planned at the latest on day 59, one day before the legal
# limit (days 57-59 are the intended margin). Compliance is alerted when a lot reaches day 59
# and its return transfer is not marked as made.
BALANCE_LATEST_DEBIT_DAY = 59
BALANCE_COMPLIANCE_ALERT_DAY = 59
# Notices before the scheduled return date (setting `balance.return_notice_days_before`).
DEFAULT_RETURN_NOTICE_DAYS_BEFORE = (14, 10, 3)
# D9 (Vlad, 2026-11-17): the regular Swiss bank schedule, as settings.
DEFAULT_BANK_PROCESSING_BUSINESS_DAYS = 1
DEFAULT_BANK_CUTOFF_TIME = "12:00"
# F01: money that funds a direct loan must reach the borrower by day 56 of its lot; the close
# leaves this many business days for signing and payment (setting).
DEFAULT_PAYOUT_MARGIN_BUSINESS_DAYS = 3
DIRECT_LOAN_PAYOUT_LAST_DAY = 56
# Q02: compliance takes a failed return after this many calendar days, and at once when the
# lot is at day 57 or later.
DEFAULT_RETURN_FAILURE_COMPLIANCE_AFTER_DAYS = 5
RETURN_FAILURE_COMPLIANCE_HOLDING_DAY = 57
# Bound for the day searches below.
_MAX_SCHEDULE_STEPS = 40


class SettlementCalendar(Protocol):
    def previous_or_same(self, value: date) -> date: ...

    def previous(self, value: date) -> date: ...

    def add(self, value: date, days: int) -> date: ...


@dataclass(frozen=True, slots=True)
class BalanceReturnSchedule:
    """The dates of one lot: last day, return request day, planned latest debit, legal limit."""

    day_zero: date
    return_after_days: int
    # On the last day the money can only be withdrawn.
    last_day: date
    # The day the platform makes the return request (the date shown to the investor).
    return_date: date
    # Day return_after_days + 1, before any calendar adjustment.
    nominal_return_date: date
    # The latest day the bank should debit Garanta's account for the return.
    latest_debit_date: date
    legal_limit_date: date
    legacy: bool

    @property
    def adjusted(self) -> bool:
        return self.return_date != self.nominal_return_date

    def holding_day(self, on: date) -> int:
        return (on - self.day_zero).days


def latest_funding_deadline(opening_date: date) -> date:
    # The deadline is the last inclusive subscription date; close runs next day.
    return opening_date + timedelta(days=MAX_FUNDING_PERIOD_DAYS - 1)


def normalized_auto_return_after_days(value: object) -> int:
    """The configured return day for new lots, or the default when it is not usable.

    The return can come earlier than day 57, never later.
    """
    if type(value) is not int or not 1 <= value <= MAX_BALANCE_RETURN_AFTER_DAYS:
        return BALANCE_AUTO_RETURN_AFTER_DAYS
    return value


def normalized_lot_return_after_days(value: object) -> int:
    """A lot's stored return days (new rule, or 58 for lots from before the switch)."""
    if type(value) is not int or not 1 <= value <= LEGACY_BALANCE_RETURN_AFTER_DAYS:
        return BALANCE_AUTO_RETURN_AFTER_DAYS
    return value


def normalized_return_notice_days(value: object) -> tuple[int, ...]:
    """Days before the return date that get a notice, largest first; the default if unusable."""
    if (
        isinstance(value, list)
        and value
        and all(type(day) is int and 1 <= day <= BALANCE_HOLDING_LIMIT_DAYS for day in value)
    ):
        return tuple(sorted(set(value), reverse=True))
    return DEFAULT_RETURN_NOTICE_DAYS_BEFORE


def normalized_business_days(value: object, *, default: int, maximum: int = 10) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        return default
    return value


def normalized_cutoff_time(value: object) -> time:
    """`HH:MM` (Europe/Zurich); the default 12:00 when the value is not a valid time."""
    text = value if isinstance(value, str) else ""
    try:
        hours, minutes = (int(part) for part in text.split(":"))
        return time(hours, minutes)
    except ValueError:
        hours, minutes = (int(part) for part in DEFAULT_BANK_CUTOFF_TIME.split(":"))
        return time(hours, minutes)


def balance_deadline_date(withdrawal_deadline_at: datetime) -> date:
    """Europe/Zurich legal deadline date of a balance source (holding day 60)."""
    return business_date(withdrawal_deadline_at)


def balance_day_zero(withdrawal_deadline_at: datetime) -> date:
    """Day 0 of a lot: its value date (FX proceeds keep the dates of their source)."""
    return balance_deadline_date(withdrawal_deadline_at) - timedelta(
        days=BALANCE_HOLDING_LIMIT_DAYS
    )


def balance_return_schedule(
    *,
    withdrawal_deadline_at: datetime,
    return_after_days: int,
    calendar: SettlementCalendar | None,
    processing_business_days: int = DEFAULT_BANK_PROCESSING_BUSINESS_DAYS,
) -> BalanceReturnSchedule:
    """The return dates of a lot (Q01).

    New rule: the return request is made on day ``return_after_days + 1`` (day 57), moved to the
    previous settlement day of the currency when that day is closed, and earlier still when the
    bank's processing time would put the debit after the latest debit day (day 59, or the
    settlement day before it). The last day is the day before the return request.

    Lots from before the switch (more days than the current maximum) keep their dates: no
    calendar adjustment. Without a calendar the nominal dates are used.
    """
    day_zero = balance_day_zero(withdrawal_deadline_at)
    nominal_return = day_zero + timedelta(days=return_after_days + 1)
    legal_limit = day_zero + timedelta(days=BALANCE_HOLDING_LIMIT_DAYS)
    latest_debit = day_zero + timedelta(days=BALANCE_LATEST_DEBIT_DAY)
    legacy = return_after_days > MAX_BALANCE_RETURN_AFTER_DAYS
    return_date = nominal_return
    if not legacy and calendar is not None:
        latest_debit = calendar.previous_or_same(latest_debit)
        return_date = calendar.previous_or_same(nominal_return)
        for _ in range(_MAX_SCHEDULE_STEPS):
            if calendar.add(return_date, processing_business_days) <= latest_debit:
                break
            return_date = calendar.previous(return_date)
        return_date = max(return_date, day_zero + timedelta(days=1))
    return BalanceReturnSchedule(
        day_zero=day_zero,
        return_after_days=return_after_days,
        last_day=return_date - timedelta(days=1),
        return_date=return_date,
        nominal_return_date=nominal_return,
        latest_debit_date=latest_debit,
        legal_limit_date=legal_limit,
        legacy=legacy,
    )


def balance_covers_funding(
    *, schedule: BalanceReturnSchedule, funding_deadline: date, as_of: datetime
) -> bool:
    """A lot can fund an opportunity only if the whole funding window ends before its last day.

    The last subscription date must be earlier than the lot's last day, so the funding close
    (the next day) happens at the latest on the last day. An immediate purchase passes today.
    """
    return business_date(as_of) < schedule.last_day and funding_deadline < schedule.last_day


def direct_loan_payout_limit(schedule: BalanceReturnSchedule) -> date:
    """F01: the last day the money of this lot may reach a direct loan's borrower (day 56)."""
    days = min(schedule.return_after_days, DIRECT_LOAN_PAYOUT_LAST_DAY)
    return schedule.day_zero + timedelta(days=days)


def direct_funding_fits(
    *,
    schedule: BalanceReturnSchedule,
    funding_deadline: date,
    as_of: datetime,
    calendar: SettlementCalendar,
    payout_margin_business_days: int,
) -> bool:
    """F01: funding close + the payout margin (business days) <= day 56 of the lot.

    The close runs the day after the last subscription date; the margin is counted in the
    settlement days of the loan's currency. The general rule (before the last day) applies too.
    """
    if not balance_covers_funding(
        schedule=schedule, funding_deadline=funding_deadline, as_of=as_of
    ):
        return False
    close_date = funding_deadline + timedelta(days=1)
    payout_by = calendar.add(close_date, payout_margin_business_days)
    return payout_by <= direct_loan_payout_limit(schedule)


def direct_funding_until(
    *,
    schedule: BalanceReturnSchedule,
    as_of: datetime,
    calendar: SettlementCalendar,
    payout_margin_business_days: int,
) -> date | None:
    """The latest last-subscription date of a direct loan this lot can fund, or None."""
    today = business_date(as_of)
    candidate = min(schedule.last_day, direct_loan_payout_limit(schedule)) - timedelta(days=1)
    for _ in range(_MAX_SCHEDULE_STEPS):
        if candidate < today:
            return None
        if direct_funding_fits(
            schedule=schedule,
            funding_deadline=candidate,
            as_of=as_of,
            calendar=calendar,
            payout_margin_business_days=payout_margin_business_days,
        ):
            return candidate
        candidate -= timedelta(days=1)
    return None


def balance_return_is_due(*, schedule: BalanceReturnSchedule, as_of: datetime) -> bool:
    """True from the return date: the money must go back to the investor's bank."""
    return business_date(as_of) >= schedule.return_date


def balance_is_overdue(*, schedule: BalanceReturnSchedule, as_of: datetime) -> bool:
    """True after the legal 60-day limit."""
    return business_date(as_of) > schedule.legal_limit_date


def balance_holding_day(*, withdrawal_deadline_at: datetime, as_of: datetime) -> int:
    """Holding day counted back from the deadline, so FX proceeds keep the source's age."""
    days_left = (balance_deadline_date(withdrawal_deadline_at) - business_date(as_of)).days
    return BALANCE_HOLDING_LIMIT_DAYS - days_left


def return_order_deadline(return_date: date, cutoff: time) -> datetime:
    """The time by which the team sends the return transfer on the return date (cut-off)."""
    return datetime.combine(return_date, cutoff, tzinfo=business_timezone())
