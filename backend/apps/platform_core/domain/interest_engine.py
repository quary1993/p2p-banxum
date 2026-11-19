"""IP of Webby-Soft SRL. 18.6 interest engine for new direct loans (Q07, Q08, F10-F14, F17).

The rules (validated 2026-11-18, "BANXUM: Interest, Late Payments, Penalties And Default"):

- Normal interest: Actual/365 Fixed, ``principal x rate x days / 365`` (365 also in leap years).
  Interest starts on the payout day (day 1). A period runs from its start (included) to the due
  date (excluded): on its due date an installment's principal earns nothing; the rest keeps earning.
- Due dates follow the payout day and the frequency (short months use their last day, then the
  reference day returns), move to the previous settlement day of the currency, then the grace adds
  its business days. Interest, penalties and statuses use that date; the unadjusted date is kept.
- Types: equal total installments (interest first, the rest repays principal; the last installment
  settles the rest), periodic interest with the principal at the end, full payment at maturity,
  initial interest-only periods, and custom schedules (due date + principal per row).
- Penalty X: a daily rate (% per day) on each overdue amount, from the day after its due date (or an
  expense's value date) to the day the money arrives, included; never on penalties. Until a Default
  declaration it is counted per installment (principal + interest) and per expense; from the day
  after the declaration on the whole amount still owed (penalties excluded).
- A payment pays, before Default: expenses (amount, then its X), then the oldest due installment in
  full (X, interest, principal), then the next; money beyond everything due is a prepayment (F12):
  interest to the day before the value date, the rest repays principal, and the next installments
  are recalculated, smaller, with the same last due date. After Default: expenses, penalties,
  interest, principal.

Everything here is pure (no database). Amounts are integer minor units; interest and penalties are
counted exactly (Decimal) and rounded half up to the cent per installment or item.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from backend.apps.platform_core.domain.settlement_calendar import SettlementDays

CONVENTION_ACT_365_FIXED = "act_365_fixed"
CONVENTION_LEGACY_MONTHLY = "legacy_monthly"

FREQUENCY_MONTHS: dict[str, int] = {
    "monthly": 1,
    "quarterly": 3,
    "half_yearly": 6,
    "annual": 12,
}

KIND_EQUAL_INSTALLMENTS = "equal_installments"
KIND_PERIODIC_INTEREST = "periodic_interest"
KIND_FULL_AT_MATURITY = "full_at_maturity"
KIND_CUSTOM = "custom"
SCHEDULE_KINDS = (
    KIND_EQUAL_INSTALLMENTS,
    KIND_PERIODIC_INTEREST,
    KIND_FULL_AT_MATURITY,
    KIND_CUSTOM,
)

# Repayment types of the loan record -> schedule kind of the engine.
REPAYMENT_TYPE_KINDS: dict[str, str] = {
    "equal_installments": KIND_EQUAL_INSTALLMENTS,
    "interest_only_then_amortizing": KIND_EQUAL_INSTALLMENTS,
    "bullet_periodic_interest": KIND_PERIODIC_INTEREST,
    "interest_only_then_bullet": KIND_PERIODIC_INTEREST,
    "full_at_maturity": KIND_FULL_AT_MATURITY,
    "custom_schedule": KIND_CUSTOM,
}

PENDING_BUSINESS_DAYS = 2
DAYS_PER_YEAR = 365
CENT = Decimal("1")
ZERO = Decimal("0")


class InterestEngineError(ValueError):
    pass


def round_minor(value: Decimal) -> int:
    return int(value.quantize(CENT, rounding=ROUND_HALF_UP))


def interest_exact(principal_minor: int, annual_rate_bps: int, days: int) -> Decimal:
    """Actual/365 Fixed interest in minor units, not rounded."""
    if days <= 0 or principal_minor <= 0 or annual_rate_bps <= 0:
        return ZERO
    return (
        Decimal(principal_minor)
        * Decimal(annual_rate_bps)
        * Decimal(days)
        / Decimal(10_000 * DAYS_PER_YEAR)
    )


def interest_minor(principal_minor: int, annual_rate_bps: int, start: date, end: date) -> int:
    """Interest from ``start`` (included) to ``end`` (excluded), rounded to the cent."""
    return round_minor(interest_exact(principal_minor, annual_rate_bps, (end - start).days))


def penalty_rate_fraction(percent_per_day: Decimal) -> Decimal:
    """0.05 (% per day) -> 0.0005."""
    if percent_per_day < 0:
        raise InterestEngineError("The penalty rate cannot be negative.")
    return Decimal(percent_per_day) / Decimal(100)


def add_months_from_anchor(anchor: date, months: int) -> date:
    """``anchor`` + ``months``, keeping the anchor's day (the last day of a shorter month)."""
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def adjust_due_date(original: date, days: SettlementDays, grace_business_days: int) -> date:
    """The previous settlement day when ``original`` is closed, then + the grace business days."""
    if grace_business_days < 0:
        raise InterestEngineError("Grace days cannot be negative.")
    adjusted = days.previous_or_same(original)
    if grace_business_days:
        adjusted = days.add(adjusted, grace_business_days)
    return adjusted


def frequency_months(frequency: str) -> int:
    try:
        return FREQUENCY_MONTHS[frequency]
    except KeyError as exc:
        raise InterestEngineError("Choose a payment frequency.") from exc


def scheduled_original_dates(
    *, payout_date: date, term_months: int, frequency: str, kind: str
) -> list[date]:
    if term_months <= 0:
        raise InterestEngineError("The term must be a positive number of months.")
    if kind == KIND_FULL_AT_MATURITY:
        return [add_months_from_anchor(payout_date, term_months)]
    step = frequency_months(frequency)
    if term_months % step:
        raise InterestEngineError("The term must be a whole number of payment periods.")
    return [
        add_months_from_anchor(payout_date, step * number)
        for number in range(1, term_months // step + 1)
    ]


@dataclass(frozen=True, slots=True)
class CustomRow:
    original_due_date: date
    principal_minor: int


@dataclass(frozen=True, slots=True)
class ScheduleTerms:
    principal_minor: int
    annual_rate_bps: int
    payout_date: date
    term_months: int
    frequency: str
    kind: str
    interest_only_periods: int = 0
    grace_business_days: int = 0
    custom_rows: tuple[CustomRow, ...] = ()


@dataclass(frozen=True, slots=True)
class EngineRow:
    number: int
    original_due_date: date
    due_date: date
    interest_start: date
    principal_minor: int
    interest_minor: int

    @property
    def total_minor(self) -> int:
        return self.principal_minor + self.interest_minor

    @property
    def interest_days(self) -> int:
        return (self.due_date - self.interest_start).days


def _annuity_payment(principal_minor: int, annual_rate_bps: int, period_days: Sequence[int]) -> int:
    """The level installment that repays ``principal_minor`` over periods of the given days."""
    if annual_rate_bps == 0:
        return -(-principal_minor // len(period_days))
    rate = Decimal(annual_rate_bps) / Decimal(10_000)
    discount = Decimal(1)
    discount_sum = ZERO
    for days in period_days:
        discount = discount / (Decimal(1) + rate * Decimal(days) / Decimal(DAYS_PER_YEAR))
        discount_sum += discount
    return round_minor(Decimal(principal_minor) / discount_sum)


def _rows_from_principal_parts(
    *,
    numbers: Sequence[int],
    dates: Sequence[tuple[date, date]],
    principal_parts: Sequence[int],
    first_interest_start: date,
    outstanding_minor: int,
    annual_rate_bps: int,
) -> list[EngineRow]:
    rows: list[EngineRow] = []
    start = first_interest_start
    outstanding = outstanding_minor
    for number, (original, adjusted), principal in zip(
        numbers, dates, principal_parts, strict=True
    ):
        if adjusted <= start:
            raise InterestEngineError(
                "Each due date must be after the start of its interest period."
            )
        rows.append(
            EngineRow(
                number=number,
                original_due_date=original,
                due_date=adjusted,
                interest_start=start,
                principal_minor=principal,
                interest_minor=interest_minor(outstanding, annual_rate_bps, start, adjusted),
            )
        )
        outstanding -= principal
        start = adjusted
    if outstanding != 0:
        raise InterestEngineError("The schedule principal must equal the loan principal.")
    return rows


def _equal_installment_rows(
    *,
    numbers: Sequence[int],
    dates: Sequence[tuple[date, date]],
    first_interest_start: date,
    outstanding_minor: int,
    annual_rate_bps: int,
    interest_only_count: int,
) -> list[EngineRow]:
    rows: list[EngineRow] = []
    start = first_interest_start
    for index in range(interest_only_count):
        original, adjusted = dates[index]
        rows.append(
            EngineRow(
                number=numbers[index],
                original_due_date=original,
                due_date=adjusted,
                interest_start=start,
                principal_minor=0,
                interest_minor=interest_minor(outstanding_minor, annual_rate_bps, start, adjusted),
            )
        )
        start = adjusted
    amortizing = list(range(interest_only_count, len(dates)))
    if not amortizing:
        raise InterestEngineError("The schedule needs at least one repayment period.")
    period_days: list[int] = []
    period_start = start
    for index in amortizing:
        period_days.append((dates[index][1] - period_start).days)
        period_start = dates[index][1]
    if any(days <= 0 for days in period_days):
        raise InterestEngineError("Each due date must be after the start of its interest period.")
    payment = _annuity_payment(outstanding_minor, annual_rate_bps, period_days)
    outstanding = outstanding_minor
    for position, index in enumerate(amortizing):
        original, adjusted = dates[index]
        interest = interest_minor(outstanding, annual_rate_bps, start, adjusted)
        if position == len(amortizing) - 1:
            principal = outstanding
        else:
            principal = max(0, min(outstanding, payment - interest))
        rows.append(
            EngineRow(
                number=numbers[index],
                original_due_date=original,
                due_date=adjusted,
                interest_start=start,
                principal_minor=principal,
                interest_minor=interest,
            )
        )
        outstanding -= principal
        start = adjusted
    return rows


def validate_custom_rows(
    rows: Sequence[CustomRow], *, principal_minor: int, payout_date: date
) -> None:
    if not rows:
        raise InterestEngineError("A custom schedule needs at least one row.")
    previous: date | None = None
    total = 0
    for index, row in enumerate(rows, start=1):
        if row.principal_minor < 0:
            raise InterestEngineError(f"Row {index}: the principal cannot be negative.")
        if row.original_due_date <= payout_date:
            raise InterestEngineError(
                f"Row {index}: the due date must be after the interest start."
            )
        if previous is not None and row.original_due_date <= previous:
            raise InterestEngineError(f"Row {index}: the due dates must increase.")
        previous = row.original_due_date
        total += row.principal_minor
        if total > principal_minor:
            raise InterestEngineError(f"Row {index}: the principal is more than the loan amount.")
    if total != principal_minor:
        raise InterestEngineError("The principal of the rows must equal the loan amount.")


def generate_schedule(terms: ScheduleTerms, days: SettlementDays) -> list[EngineRow]:
    if terms.principal_minor <= 0:
        raise InterestEngineError("The principal must be positive.")
    if terms.annual_rate_bps < 0:
        raise InterestEngineError("The interest rate cannot be negative.")
    if terms.kind not in SCHEDULE_KINDS:
        raise InterestEngineError("Choose a repayment type.")
    if terms.kind == KIND_CUSTOM:
        validate_custom_rows(
            terms.custom_rows, principal_minor=terms.principal_minor, payout_date=terms.payout_date
        )
        originals = [row.original_due_date for row in terms.custom_rows]
    else:
        originals = scheduled_original_dates(
            payout_date=terms.payout_date,
            term_months=terms.term_months,
            frequency=terms.frequency,
            kind=terms.kind,
        )
    dates = [
        (original, adjust_due_date(original, days, terms.grace_business_days))
        for original in originals
    ]
    for index in range(1, len(dates)):
        if dates[index][1] <= dates[index - 1][1]:
            raise InterestEngineError("Two due dates fall on the same settlement day.")
    numbers = list(range(1, len(dates) + 1))
    if terms.kind == KIND_EQUAL_INSTALLMENTS:
        if not 0 <= terms.interest_only_periods < len(dates):
            raise InterestEngineError(
                "The interest-only periods must leave at least one repayment period."
            )
        return _equal_installment_rows(
            numbers=numbers,
            dates=dates,
            first_interest_start=terms.payout_date,
            outstanding_minor=terms.principal_minor,
            annual_rate_bps=terms.annual_rate_bps,
            interest_only_count=terms.interest_only_periods,
        )
    if terms.kind == KIND_CUSTOM:
        parts = [row.principal_minor for row in terms.custom_rows]
    else:
        parts = [0] * (len(dates) - 1) + [terms.principal_minor]
    return _rows_from_principal_parts(
        numbers=numbers,
        dates=dates,
        principal_parts=parts,
        first_interest_start=terms.payout_date,
        outstanding_minor=terms.principal_minor,
        annual_rate_bps=terms.annual_rate_bps,
    )


def _largest_remainder(total: int, weights: Sequence[int]) -> list[int]:
    weight_sum = sum(weights)
    if weight_sum <= 0:
        parts = [0] * len(weights)
        if parts:
            parts[-1] = total
        return parts
    exact = [Decimal(total) * Decimal(weight) / Decimal(weight_sum) for weight in weights]
    floors = [int(value) for value in exact]
    remainder = total - sum(floors)
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - floors[i]), i))
    for index in order[:remainder]:
        floors[index] += 1
    return floors


def regenerate_future_rows(
    *,
    kind: str,
    rows: Sequence[EngineRow],
    outstanding_minor: int,
    annual_rate_bps: int,
    first_interest_start: date,
) -> list[EngineRow]:
    """F12: recalculate the rows not yet due after a prepayment; same due dates (same maturity).

    ``rows`` are the remaining rows of the current schedule (oldest first); the first new period
    starts at ``first_interest_start`` (the prepayment's value date).
    """
    if not rows:
        return []
    numbers = [row.number for row in rows]
    dates = [(row.original_due_date, row.due_date) for row in rows]
    if outstanding_minor <= 0:
        return []
    if kind == KIND_EQUAL_INSTALLMENTS:
        interest_only_count = 0
        for row in rows[:-1]:
            if row.principal_minor != 0:
                break
            interest_only_count += 1
        return _equal_installment_rows(
            numbers=numbers,
            dates=dates,
            first_interest_start=first_interest_start,
            outstanding_minor=outstanding_minor,
            annual_rate_bps=annual_rate_bps,
            interest_only_count=interest_only_count,
        )
    if kind == KIND_CUSTOM:
        parts = _largest_remainder(outstanding_minor, [row.principal_minor for row in rows])
    else:
        parts = [0] * (len(rows) - 1) + [outstanding_minor]
    return _rows_from_principal_parts(
        numbers=numbers,
        dates=dates,
        principal_parts=parts,
        first_interest_start=first_interest_start,
        outstanding_minor=outstanding_minor,
        annual_rate_bps=annual_rate_bps,
    )


# ---------------------------------------------------------------------------------------------
# Status


STATUS_ON_SCHEDULE = "on_schedule"
STATUS_PENDING = "pending"
STATUS_DUE = "due"
STATUS_LATE = "late"
STATUS_DEFAULT = "default"
STATUS_REPAID = "repaid"


@dataclass(frozen=True, slots=True)
class InstallmentStatus:
    status: str
    days_late: int
    oldest_unpaid_due_date: date | None
    default_possible: bool


def installment_status(
    *,
    oldest_unpaid_due_date: date | None,
    as_of: date,
    days: SettlementDays,
    late_days: int,
    default_days: int,
    default_declared: bool,
    anything_owed: bool = True,
) -> InstallmentStatus:
    """The oldest unpaid installment decides: Pending / Due / Late; Default only when declared."""
    if default_declared:
        return InstallmentStatus(STATUS_DEFAULT, 0, oldest_unpaid_due_date, False)
    if not anything_owed:
        return InstallmentStatus(STATUS_REPAID, 0, None, False)
    if oldest_unpaid_due_date is None or oldest_unpaid_due_date > as_of:
        return InstallmentStatus(STATUS_ON_SCHEDULE, 0, None, False)
    days_late = (as_of - oldest_unpaid_due_date).days
    pending_until = days.add(oldest_unpaid_due_date, PENDING_BUSINESS_DAYS)
    if as_of <= pending_until and days_late < late_days:
        status = STATUS_PENDING
    elif days_late >= late_days:
        status = STATUS_LATE
    else:
        status = STATUS_DUE
    return InstallmentStatus(status, days_late, oldest_unpaid_due_date, days_late >= default_days)


# ---------------------------------------------------------------------------------------------
# Obligations, penalties and payment allocation


@dataclass(slots=True)
class OpenInstallment:
    """An installment of the current schedule with what is still owed on it."""

    key: str
    number: int
    due_date: date
    interest_start: date
    principal_owed: int
    interest_owed: int
    original_due_date: date
    scheduled_principal: int = 0
    scheduled_interest: int = 0
    penalty_accrued: Decimal = ZERO
    penalty_paid: int = 0

    @property
    def owed(self) -> int:
        return self.principal_owed + self.interest_owed

    @property
    def penalty_owed(self) -> int:
        return round_minor(self.penalty_accrued) - self.penalty_paid


@dataclass(slots=True)
class OpenExpense:
    key: str
    value_date: date
    amount_owed: int
    penalty_accrued: Decimal = ZERO
    penalty_paid: int = 0

    @property
    def penalty_owed(self) -> int:
        return round_minor(self.penalty_accrued) - self.penalty_paid


@dataclass(slots=True)
class LoanPosition:
    """Everything still owed on one loan, with penalties counted through ``through_date``."""

    through_date: date
    penalty_rate: Decimal  # fraction per day (0.05 % -> 0.0005)
    installments: list[OpenInstallment]
    expenses: list[OpenExpense] = field(default_factory=list)
    default_on: date | None = None
    # Penalties counted per item up to the Default declaration, kept as cents (owed, outside the
    # X base), and the X on the whole amount after it.
    frozen_penalty_minor: int = 0
    frozen_penalty_paid: int = 0
    default_penalty_accrued: Decimal = ZERO
    default_penalty_paid: int = 0

    def due_installments(self, as_of: date) -> list[OpenInstallment]:
        return [row for row in self.installments if row.due_date <= as_of and row.owed > 0]

    def oldest_unpaid_due_date(self, as_of: date) -> date | None:
        due = self.due_installments(as_of)
        return min((row.due_date for row in due), default=None)

    @property
    def principal_owed(self) -> int:
        return sum(row.principal_owed for row in self.installments)

    @property
    def penalty_owed(self) -> int:
        return (
            sum(row.penalty_owed for row in self.installments)
            + sum(item.penalty_owed for item in self.expenses)
            + (self.frozen_penalty_minor - self.frozen_penalty_paid)
            + (round_minor(self.default_penalty_accrued) - self.default_penalty_paid)
        )

    @property
    def expenses_owed(self) -> int:
        return sum(item.amount_owed for item in self.expenses)


def accrue_penalties(position: LoanPosition, to_date: date) -> None:
    """Count X for every day after ``through_date`` up to ``to_date`` (included)."""
    if to_date <= position.through_date:
        return
    rate = position.penalty_rate
    day = position.through_date + timedelta(days=1)
    while day <= to_date:
        if rate > 0:
            if position.default_on is None or day <= position.default_on:
                for row in position.installments:
                    if row.due_date < day and row.owed > 0:
                        row.penalty_accrued += Decimal(row.owed) * rate
                for item in position.expenses:
                    if item.value_date < day and item.amount_owed > 0:
                        item.penalty_accrued += Decimal(item.amount_owed) * rate
            else:
                base = sum(row.owed for row in position.installments) + sum(
                    item.amount_owed for item in position.expenses if item.value_date < day
                )
                position.default_penalty_accrued += Decimal(base) * rate
        day += timedelta(days=1)
    position.through_date = to_date


def freeze_penalties_at_default(position: LoanPosition, declared_on: date) -> None:
    """At a Default declaration: per-item penalties become one owed amount outside the X base."""
    accrue_penalties(position, declared_on)
    frozen = 0
    for row in position.installments:
        frozen += row.penalty_owed
        row.penalty_paid += row.penalty_owed
    for item in position.expenses:
        frozen += item.penalty_owed
        item.penalty_paid += item.penalty_owed
    position.frozen_penalty_minor += frozen
    position.default_on = declared_on


def default_whole_amount(
    *, position: LoanPosition, declared_on: date, annual_rate_bps: int
) -> tuple[int, int]:
    """(principal, interest) that become due at a Default declaration on ``declared_on``.

    All principal still owed; the interest of unpaid due installments; the interest built up on
    the principal not yet due from its period start to the declaration day, included.
    """
    principal = position.principal_owed
    interest = 0
    for row in position.installments:
        if row.due_date <= declared_on:
            interest += row.interest_owed
    not_yet_due = [row for row in position.installments if row.due_date > declared_on]
    if not_yet_due:
        start = min(row.interest_start for row in not_yet_due)
        base = sum(row.principal_owed for row in not_yet_due)
        interest += round_minor(
            interest_exact(base, annual_rate_bps, (declared_on - start).days + 1)
        )
    return principal, interest


@dataclass(slots=True)
class Allocation:
    """How one payment is used; ``installments``: row key -> (penalty, interest, principal)."""

    amount_minor: int
    value_date: date
    expenses_minor: int = 0
    expense_keys: dict[str, int] = field(default_factory=dict)
    penalty_minor: int = 0
    interest_minor: int = 0
    principal_minor: int = 0
    installments: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    prepayment_minor: int = 0
    prepayment_interest_minor: int = 0
    accrued_interest_days: int = 0
    # Rows not yet due after a prepayment (recalculated), or None when the schedule is unchanged.
    new_future_rows: list[EngineRow] | None = None
    # True when a prepayment changed the amounts of the rows not yet due (a new schedule version).
    schedule_changed: bool = False
    unapplied_minor: int = 0

    @property
    def applied_minor(self) -> int:
        return self.expenses_minor + self.penalty_minor + self.interest_minor + self.principal_minor


def _take(remaining: int, owed: int) -> int:
    return max(0, min(remaining, owed))


def _add_installment(
    allocation: Allocation, key: str, penalty: int, interest: int, principal: int
) -> None:
    previous = allocation.installments.get(key, (0, 0, 0))
    allocation.installments[key] = (
        previous[0] + penalty,
        previous[1] + interest,
        previous[2] + principal,
    )


def allocate_payment(
    position: LoanPosition,
    *,
    amount_minor: int,
    value_date: date,
    annual_rate_bps: int,
    kind: str,
) -> Allocation:
    """Apply one payment to ``position`` (which it changes) and say how it was used."""
    if amount_minor <= 0:
        raise InterestEngineError("The payment amount must be positive.")
    if value_date < position.through_date:
        raise InterestEngineError("The value date cannot be before the last recorded payment.")
    accrue_penalties(position, value_date)
    allocation = Allocation(amount_minor=amount_minor, value_date=value_date)
    remaining = amount_minor
    if position.default_on is not None:
        remaining = _allocate_after_default(position, allocation, remaining)
    else:
        remaining = _allocate_before_default(position, allocation, remaining, value_date)
        if remaining > 0:
            remaining = _apply_prepayment(
                position,
                allocation,
                remaining,
                value_date=value_date,
                annual_rate_bps=annual_rate_bps,
                kind=kind,
            )
    allocation.unapplied_minor = remaining
    return allocation


def _pay_expenses(
    position: LoanPosition, allocation: Allocation, remaining: int, *, with_penalty: bool
) -> int:
    for item in sorted(position.expenses, key=lambda value: (value.value_date, value.key)):
        paid = _take(remaining, item.amount_owed)
        if paid:
            item.amount_owed -= paid
            remaining -= paid
            allocation.expenses_minor += paid
            allocation.expense_keys[item.key] = allocation.expense_keys.get(item.key, 0) + paid
        if with_penalty:
            penalty = _take(remaining, item.penalty_owed)
            if penalty:
                item.penalty_paid += penalty
                remaining -= penalty
                allocation.penalty_minor += penalty
    return remaining


def _allocate_before_default(
    position: LoanPosition, allocation: Allocation, remaining: int, value_date: date
) -> int:
    remaining = _pay_expenses(position, allocation, remaining, with_penalty=True)
    for row in sorted(position.installments, key=lambda value: (value.due_date, value.number)):
        if row.due_date > value_date:
            break
        penalty = _take(remaining, row.penalty_owed)
        row.penalty_paid += penalty
        remaining -= penalty
        interest = _take(remaining, row.interest_owed)
        row.interest_owed -= interest
        remaining -= interest
        principal = _take(remaining, row.principal_owed)
        row.principal_owed -= principal
        remaining -= principal
        allocation.penalty_minor += penalty
        allocation.interest_minor += interest
        allocation.principal_minor += principal
        if penalty or interest or principal:
            _add_installment(allocation, row.key, penalty, interest, principal)
    return remaining


def _allocate_after_default(position: LoanPosition, allocation: Allocation, remaining: int) -> int:
    remaining = _pay_expenses(position, allocation, remaining, with_penalty=False)
    # Penalties: those counted before the declaration, then the X on the whole amount.
    penalty = _take(remaining, position.frozen_penalty_minor - position.frozen_penalty_paid)
    position.frozen_penalty_paid += penalty
    remaining -= penalty
    allocation.penalty_minor += penalty
    for item in position.expenses:
        expense_penalty = _take(remaining, item.penalty_owed)
        item.penalty_paid += expense_penalty
        remaining -= expense_penalty
        allocation.penalty_minor += expense_penalty
    default_penalty = _take(
        remaining, round_minor(position.default_penalty_accrued) - position.default_penalty_paid
    )
    position.default_penalty_paid += default_penalty
    remaining -= default_penalty
    allocation.penalty_minor += default_penalty
    rows = sorted(position.installments, key=lambda value: (value.due_date, value.number))
    for row in rows:
        interest = _take(remaining, row.interest_owed)
        row.interest_owed -= interest
        remaining -= interest
        allocation.interest_minor += interest
        if interest:
            _add_installment(allocation, row.key, 0, interest, 0)
    for row in rows:
        principal = _take(remaining, row.principal_owed)
        row.principal_owed -= principal
        remaining -= principal
        allocation.principal_minor += principal
        if principal:
            _add_installment(allocation, row.key, 0, 0, principal)
    return remaining


def _apply_prepayment(
    position: LoanPosition,
    allocation: Allocation,
    remaining: int,
    *,
    value_date: date,
    annual_rate_bps: int,
    kind: str,
) -> int:
    future = sorted(
        (row for row in position.installments if row.due_date > value_date and row.owed > 0),
        key=lambda value: (value.due_date, value.number),
    )
    if not future:
        return remaining
    current = future[0]
    outstanding = sum(row.principal_owed for row in future)
    accrued_days = max(0, (value_date - current.interest_start).days)
    accrued = round_minor(interest_exact(outstanding, annual_rate_bps, accrued_days))
    allocation.accrued_interest_days = accrued_days
    interest_paid = _take(remaining, accrued)
    remaining -= interest_paid
    allocation.interest_minor += interest_paid
    allocation.prepayment_interest_minor = interest_paid
    if interest_paid < accrued:
        # Not even the interest built up: it is part of the current installment's interest.
        current.interest_owed = max(0, current.interest_owed - interest_paid)
        _add_installment(allocation, current.key, 0, interest_paid, 0)
        allocation.prepayment_minor = interest_paid
        return remaining
    principal_paid = _take(remaining, outstanding)
    remaining -= principal_paid
    allocation.principal_minor += principal_paid
    allocation.prepayment_minor = interest_paid + principal_paid
    new_outstanding = outstanding - principal_paid
    if principal_paid < current.principal_owed:
        # A part of the current installment's principal: that installment stays, with the interest
        # built up so far plus the interest from the value date on the smaller principal.
        current.principal_owed -= principal_paid
        current.interest_owed = interest_minor(
            new_outstanding, annual_rate_bps, value_date, current.due_date
        )
        current.interest_start = value_date
        _add_installment(allocation, current.key, 0, interest_paid, principal_paid)
        allocation.schedule_changed = True
        return remaining
    # The current installment is settled early; the extra repays principal of the later ones,
    # which are recalculated from the value date (same due dates, so the same maturity).
    current_principal = current.principal_owed
    _add_installment(allocation, current.key, 0, interest_paid, current_principal)
    current.principal_owed = 0
    current.interest_owed = 0
    later = future[1:]
    later_outstanding = new_outstanding
    regenerated = regenerate_future_rows(
        kind=kind,
        rows=[
            EngineRow(
                number=row.number,
                original_due_date=row.original_due_date,
                due_date=row.due_date,
                interest_start=row.interest_start,
                principal_minor=row.scheduled_principal or row.principal_owed,
                interest_minor=row.interest_owed,
            )
            for row in later
        ],
        outstanding_minor=later_outstanding,
        annual_rate_bps=annual_rate_bps,
        first_interest_start=value_date,
    )
    by_number = {row.number: row for row in regenerated}
    for row in later:
        new_row = by_number.get(row.number)
        row.principal_owed = new_row.principal_minor if new_row else 0
        row.interest_owed = new_row.interest_minor if new_row else 0
        row.interest_start = new_row.interest_start if new_row else value_date
        row.scheduled_principal = row.principal_owed
        row.scheduled_interest = row.interest_owed
    allocation.new_future_rows = regenerated
    allocation.schedule_changed = True
    return remaining


def open_installments_from_rows(rows: Iterable[EngineRow]) -> list[OpenInstallment]:
    return [
        OpenInstallment(
            key=f"{row.number}:{row.due_date.isoformat()}",
            number=row.number,
            due_date=row.due_date,
            interest_start=row.interest_start,
            principal_owed=row.principal_minor,
            interest_owed=row.interest_minor,
            original_due_date=row.original_due_date,
            scheduled_principal=row.principal_minor,
            scheduled_interest=row.interest_minor,
        )
        for row in rows
    ]


def with_owed(row: EngineRow, *, principal_owed: int, interest_owed: int) -> EngineRow:
    return replace(row, principal_minor=principal_owed, interest_minor=interest_owed)
