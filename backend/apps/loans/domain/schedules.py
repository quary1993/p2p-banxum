from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from backend.apps.platform_core.domain.money import Money, split_evenly


class ScheduleGenerationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ScheduleInstallmentDraft:
    installment_number: int
    due_date: date
    principal_minor: int
    interest_minor: int
    total_minor: int
    admin_overridden: bool = False


@dataclass(frozen=True, slots=True)
class ManualScheduleRow:
    due_date: date
    principal_minor: int
    interest_minor: int


def add_months(value: date, months: int) -> date:
    if months < 0:
        raise ScheduleGenerationError("months cannot be negative.")
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def monthly_rate_from_bps(annual_bps: int) -> Decimal:
    if type(annual_bps) is not int or annual_bps < 0:
        raise ScheduleGenerationError("Annual interest rate must be a non-negative integer bps.")
    return Decimal(annual_bps) / Decimal("120000")


def _round_minor(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _due_dates(first_due_date: date, term_months: int) -> list[date]:
    return [add_months(first_due_date, index) for index in range(term_months)]


def _validate_common_inputs(
    *,
    principal_minor: int,
    currency: str,
    term_months: int,
    annual_interest_bps: int,
) -> None:
    Money(principal_minor, currency)
    if principal_minor <= 0:
        raise ScheduleGenerationError("Principal must be positive.")
    if type(term_months) is not int or term_months <= 0:
        raise ScheduleGenerationError("Term must be a positive number of months.")
    monthly_rate_from_bps(annual_interest_bps)


def _annuity_schedule(
    *,
    principal_minor: int,
    currency: str,
    term_months: int,
    annual_interest_bps: int,
    first_due_date: date,
    start_number: int = 1,
) -> list[ScheduleInstallmentDraft]:
    _validate_common_inputs(
        principal_minor=principal_minor,
        currency=currency,
        term_months=term_months,
        annual_interest_bps=annual_interest_bps,
    )
    monthly_rate = monthly_rate_from_bps(annual_interest_bps)
    outstanding = principal_minor
    due_dates = _due_dates(first_due_date, term_months)
    rows: list[ScheduleInstallmentDraft] = []
    if monthly_rate == 0:
        principal_parts = split_evenly(Money(principal_minor, currency), term_months)
        for index, principal_part in enumerate(principal_parts):
            rows.append(
                ScheduleInstallmentDraft(
                    installment_number=start_number + index,
                    due_date=due_dates[index],
                    principal_minor=principal_part.amount_minor,
                    interest_minor=0,
                    total_minor=principal_part.amount_minor,
                )
            )
        return rows

    denominator = Decimal(1) - ((Decimal(1) + monthly_rate) ** -term_months)
    monthly_payment = (Decimal(principal_minor) * monthly_rate) / denominator
    rounded_payment = _round_minor(monthly_payment)
    for index in range(term_months):
        interest = _round_minor(Decimal(outstanding) * monthly_rate)
        if index == term_months - 1:
            principal = outstanding
            total = principal + interest
        else:
            principal = max(0, min(outstanding, rounded_payment - interest))
            total = principal + interest
        outstanding -= principal
        rows.append(
            ScheduleInstallmentDraft(
                installment_number=start_number + index,
                due_date=due_dates[index],
                principal_minor=principal,
                interest_minor=interest,
                total_minor=total,
            )
        )
    return rows


def generate_equal_installment_schedule(
    *,
    principal_minor: int,
    currency: str,
    term_months: int,
    annual_interest_bps: int,
    first_due_date: date,
) -> list[ScheduleInstallmentDraft]:
    return _annuity_schedule(
        principal_minor=principal_minor,
        currency=currency,
        term_months=term_months,
        annual_interest_bps=annual_interest_bps,
        first_due_date=first_due_date,
    )


def generate_equal_principal_schedule(
    *,
    principal_minor: int,
    currency: str,
    term_months: int,
    annual_interest_bps: int,
    first_due_date: date,
) -> list[ScheduleInstallmentDraft]:
    _validate_common_inputs(
        principal_minor=principal_minor,
        currency=currency,
        term_months=term_months,
        annual_interest_bps=annual_interest_bps,
    )
    monthly_rate = monthly_rate_from_bps(annual_interest_bps)
    principal_parts = split_evenly(Money(principal_minor, currency), term_months)
    outstanding = principal_minor
    rows: list[ScheduleInstallmentDraft] = []
    for index, principal_part in enumerate(principal_parts):
        principal = principal_part.amount_minor
        interest = _round_minor(Decimal(outstanding) * monthly_rate)
        rows.append(
            ScheduleInstallmentDraft(
                installment_number=index + 1,
                due_date=add_months(first_due_date, index),
                principal_minor=principal,
                interest_minor=interest,
                total_minor=principal + interest,
            )
        )
        outstanding -= principal
    return rows


def generate_bullet_schedule(
    *,
    principal_minor: int,
    currency: str,
    term_months: int,
    annual_interest_bps: int,
    first_due_date: date,
) -> list[ScheduleInstallmentDraft]:
    _validate_common_inputs(
        principal_minor=principal_minor,
        currency=currency,
        term_months=term_months,
        annual_interest_bps=annual_interest_bps,
    )
    monthly_rate = monthly_rate_from_bps(annual_interest_bps)
    interest = _round_minor(Decimal(principal_minor) * monthly_rate)
    rows: list[ScheduleInstallmentDraft] = []
    for index in range(term_months):
        principal = principal_minor if index == term_months - 1 else 0
        rows.append(
            ScheduleInstallmentDraft(
                installment_number=index + 1,
                due_date=add_months(first_due_date, index),
                principal_minor=principal,
                interest_minor=interest,
                total_minor=principal + interest,
            )
        )
    return rows


def generate_interest_only_then_amortizing_schedule(
    *,
    principal_minor: int,
    currency: str,
    term_months: int,
    annual_interest_bps: int,
    first_due_date: date,
    interest_only_months: int,
) -> list[ScheduleInstallmentDraft]:
    _validate_common_inputs(
        principal_minor=principal_minor,
        currency=currency,
        term_months=term_months,
        annual_interest_bps=annual_interest_bps,
    )
    if interest_only_months <= 0 or interest_only_months >= term_months:
        raise ScheduleGenerationError(
            "Interest-only months must be between 1 and term_months - 1."
        )
    monthly_rate = monthly_rate_from_bps(annual_interest_bps)
    interest = _round_minor(Decimal(principal_minor) * monthly_rate)
    rows: list[ScheduleInstallmentDraft] = []
    for index in range(interest_only_months):
        rows.append(
            ScheduleInstallmentDraft(
                installment_number=index + 1,
                due_date=add_months(first_due_date, index),
                principal_minor=0,
                interest_minor=interest,
                total_minor=interest,
            )
        )
    amortizing_first_due = add_months(first_due_date, interest_only_months)
    rows.extend(
        _annuity_schedule(
            principal_minor=principal_minor,
            currency=currency,
            term_months=term_months - interest_only_months,
            annual_interest_bps=annual_interest_bps,
            first_due_date=amortizing_first_due,
            start_number=interest_only_months + 1,
        )
    )
    return rows


def schedule_from_manual_rows(
    *,
    principal_minor: int,
    term_months: int,
    rows: list[ManualScheduleRow],
) -> list[ScheduleInstallmentDraft]:
    if len(rows) != term_months:
        raise ScheduleGenerationError("Manual schedule rows must match the loan term.")
    previous_due_date: date | None = None
    principal_sum = 0
    installments: list[ScheduleInstallmentDraft] = []
    for index, row in enumerate(rows):
        if row.principal_minor < 0 or row.interest_minor < 0:
            raise ScheduleGenerationError("Manual schedule amounts cannot be negative.")
        if previous_due_date is not None and row.due_date <= previous_due_date:
            raise ScheduleGenerationError("Manual schedule due dates must be strictly increasing.")
        previous_due_date = row.due_date
        principal_sum += row.principal_minor
        installments.append(
            ScheduleInstallmentDraft(
                installment_number=index + 1,
                due_date=row.due_date,
                principal_minor=row.principal_minor,
                interest_minor=row.interest_minor,
                total_minor=row.principal_minor + row.interest_minor,
                admin_overridden=True,
            )
        )
    if principal_sum != principal_minor:
        raise ScheduleGenerationError("Manual schedule principal must equal loan principal.")
    return installments
