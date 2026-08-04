from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Protocol

from backend.apps.platform_core.domain.money import Money, allocate_by_weights


class PricingValidationError(ValueError):
    pass


class ScheduleCashFlow(Protocol):
    @property
    def installment_number(self) -> int: ...

    @property
    def accrual_start_date(self) -> date: ...

    @property
    def due_date(self) -> date: ...

    @property
    def principal_minor(self) -> int: ...

    @property
    def interest_minor(self) -> int: ...

    @property
    def penalty_minor(self) -> int: ...


@dataclass(frozen=True, slots=True)
class PricedCashFlow:
    installment_number: int
    accrual_start_date: date
    due_date: date
    principal_minor: int
    interest_minor: int
    penalty_minor: int
    total_minor: int
    days_to_payment: int
    present_value_minor: int


@dataclass(frozen=True, slots=True)
class OriginatorClaimPrice:
    requested_cash_minor: int
    executable_cash_minor: int
    assigned_principal_minor: int
    share_ppm: int
    premium_discount_minor: int
    platform_fee_minor: int
    originator_payable_minor: int
    rounding_remainder_minor: int
    cash_flows: tuple[PricedCashFlow, ...]


def _round_minor(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _allocated_interest(
    *,
    scheduled_interest_minor: int,
    assigned_principal_minor: int,
    current_outstanding_principal_minor: int,
    accrual_start_date: date,
    due_date: date,
    pricing_date: date,
) -> int:
    if scheduled_interest_minor <= 0 or pricing_date >= due_date:
        return 0
    total_days = (due_date - accrual_start_date).days
    if total_days <= 0:
        raise PricingValidationError("Schedule accrual periods must be positive.")
    entitlement_start = max(pricing_date, accrual_start_date)
    entitled_days = (due_date - entitlement_start).days
    if entitled_days <= 0:
        return 0
    return _round_minor(
        Decimal(scheduled_interest_minor)
        * Decimal(assigned_principal_minor)
        / Decimal(current_outstanding_principal_minor)
        * Decimal(entitled_days)
        / Decimal(total_days)
    )


def price_assigned_principal(
    *,
    schedule_rows: Sequence[ScheduleCashFlow],
    current_outstanding_principal_minor: int,
    assigned_principal_minor: int,
    target_yield_bps: int,
    pricing_date: date,
    currency: str,
) -> tuple[int, tuple[PricedCashFlow, ...]]:
    if current_outstanding_principal_minor <= 0:
        raise PricingValidationError("Current outstanding principal must be positive.")
    if (
        assigned_principal_minor <= 0
        or assigned_principal_minor > current_outstanding_principal_minor
    ):
        raise PricingValidationError(
            "Assigned principal must be within current outstanding principal."
        )
    if target_yield_bps <= 0:
        raise PricingValidationError("Target yield must be positive.")
    future_rows = [row for row in schedule_rows if row.due_date > pricing_date]
    if not future_rows:
        raise PricingValidationError("At least one future cash flow is required.")
    principal_weights = [row.principal_minor for row in future_rows]
    if sum(principal_weights) != current_outstanding_principal_minor:
        raise PricingValidationError(
            "Future schedule principal must equal current outstanding principal."
        )
    principal_parts = allocate_by_weights(
        Money(assigned_principal_minor, currency), principal_weights
    )
    annual_yield = Decimal(target_yield_bps) / Decimal(10_000)
    priced_rows: list[PricedCashFlow] = []
    present_value = Decimal(0)
    with localcontext() as context:
        context.prec = 50
        for row, principal_part in zip(future_rows, principal_parts, strict=True):
            interest_minor = _allocated_interest(
                scheduled_interest_minor=row.interest_minor,
                assigned_principal_minor=assigned_principal_minor,
                current_outstanding_principal_minor=current_outstanding_principal_minor,
                accrual_start_date=row.accrual_start_date,
                due_date=row.due_date,
                pricing_date=pricing_date,
            )
            penalty_minor = _round_minor(
                Decimal(row.penalty_minor)
                * Decimal(assigned_principal_minor)
                / Decimal(current_outstanding_principal_minor)
            )
            total_minor = principal_part.amount_minor + interest_minor + penalty_minor
            days_to_payment = (row.due_date - pricing_date).days
            discount_factor = (Decimal(1) + annual_yield) ** (
                Decimal(days_to_payment) / Decimal(365)
            )
            row_present_value = Decimal(total_minor) / discount_factor
            rounded_row_pv = _round_minor(row_present_value)
            present_value += row_present_value
            priced_rows.append(
                PricedCashFlow(
                    installment_number=row.installment_number,
                    accrual_start_date=max(pricing_date, row.accrual_start_date),
                    due_date=row.due_date,
                    principal_minor=principal_part.amount_minor,
                    interest_minor=interest_minor,
                    penalty_minor=penalty_minor,
                    total_minor=total_minor,
                    days_to_payment=days_to_payment,
                    present_value_minor=rounded_row_pv,
                )
            )
    return _round_minor(present_value), tuple(priced_rows)


def quote_cash_consideration(
    *,
    schedule_rows: Sequence[ScheduleCashFlow],
    current_outstanding_principal_minor: int,
    unsold_principal_minor: int,
    requested_cash_minor: int,
    minimum_investment_minor: int,
    target_yield_bps: int,
    premium_fee_bps: int,
    pricing_date: date,
    currency: str,
) -> OriginatorClaimPrice:
    if requested_cash_minor < minimum_investment_minor:
        raise PricingValidationError("Requested cash is below the loan minimum investment.")
    if unsold_principal_minor <= 0 or unsold_principal_minor > current_outstanding_principal_minor:
        raise PricingValidationError("Unsold principal is invalid.")
    if premium_fee_bps < 0 or premium_fee_bps > 10_000:
        raise PricingValidationError("Premium fee must be between 0 and 10000 bps.")

    low = 1
    high = unsold_principal_minor
    selected_principal = 0
    selected_price = 0
    selected_flows: tuple[PricedCashFlow, ...] = ()
    while low <= high:
        candidate = (low + high) // 2
        price_minor, flows = price_assigned_principal(
            schedule_rows=schedule_rows,
            current_outstanding_principal_minor=current_outstanding_principal_minor,
            assigned_principal_minor=candidate,
            target_yield_bps=target_yield_bps,
            pricing_date=pricing_date,
            currency=currency,
        )
        if price_minor <= requested_cash_minor:
            selected_principal = candidate
            selected_price = price_minor
            selected_flows = flows
            low = candidate + 1
        else:
            high = candidate - 1
    if selected_principal <= 0 or selected_price <= 0:
        raise PricingValidationError("Requested cash cannot purchase a positive claim share.")
    if selected_price < minimum_investment_minor and selected_principal < unsold_principal_minor:
        raise PricingValidationError("Executable cash is below the loan minimum investment.")

    premium_discount = selected_price - selected_principal
    positive_premium = max(premium_discount, 0)
    platform_fee = _round_minor(
        Decimal(positive_premium) * Decimal(premium_fee_bps) / Decimal(10_000)
    )
    platform_fee = min(platform_fee, selected_price)
    originator_payable = selected_price - platform_fee
    share_ppm = _round_minor(
        Decimal(selected_principal)
        * Decimal(1_000_000)
        / Decimal(current_outstanding_principal_minor)
    )
    return OriginatorClaimPrice(
        requested_cash_minor=requested_cash_minor,
        executable_cash_minor=selected_price,
        assigned_principal_minor=selected_principal,
        share_ppm=share_ppm,
        premium_discount_minor=premium_discount,
        platform_fee_minor=platform_fee,
        originator_payable_minor=originator_payable,
        rounding_remainder_minor=requested_cash_minor - selected_price,
        cash_flows=selected_flows,
    )
