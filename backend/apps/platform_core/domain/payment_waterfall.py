from __future__ import annotations

from dataclasses import dataclass

PAYMENT_WATERFALL_VERSION = "garanta_costs_penalty_interest_principal_v2"
PAYMENT_WATERFALL_ORDER = (
    "garanta_legal_costs_and_recovery_fee",
    "penalty",
    "interest",
    "principal",
)


class PaymentWaterfallError(ValueError):
    pass


def _minor_amount(value: int, label: str) -> int:
    if type(value) is not int or value < 0:
        raise PaymentWaterfallError(f"{label} must be a non-negative integer in minor units.")
    return value


@dataclass(frozen=True, slots=True)
class PaymentWaterfallObligations:
    costs_minor: int = 0
    penalty_minor: int = 0
    interest_minor: int = 0
    principal_minor: int = 0

    def __post_init__(self) -> None:
        _minor_amount(self.costs_minor, "Costs due")
        _minor_amount(self.penalty_minor, "Penalty due")
        _minor_amount(self.interest_minor, "Interest due")
        _minor_amount(self.principal_minor, "Principal outstanding")

    @property
    def total_minor(self) -> int:
        return (
            self.costs_minor
            + self.penalty_minor
            + self.interest_minor
            + self.principal_minor
        )


@dataclass(frozen=True, slots=True)
class PaymentWaterfallAllocation:
    amount_minor: int
    costs_minor: int
    penalty_minor: int
    interest_minor: int
    principal_minor: int
    unapplied_minor: int

    @property
    def applied_minor(self) -> int:
        return (
            self.costs_minor
            + self.penalty_minor
            + self.interest_minor
            + self.principal_minor
        )


def allocate_payment_waterfall(
    amount_minor: int,
    obligations: PaymentWaterfallObligations,
    *,
    reject_excess: bool = True,
) -> PaymentWaterfallAllocation:
    """Apply cash to the universal BANXUM payment waterfall.

    Every loan and payment state uses the same priority: Garanta legal/recovery
    costs, penalty, interest, then principal. Principal can receive cash only
    after every higher-priority obligation supplied to this calculation is paid.
    """

    remaining = _minor_amount(amount_minor, "Payment amount")
    allocations: list[int] = []
    for due in (
        obligations.costs_minor,
        obligations.penalty_minor,
        obligations.interest_minor,
        obligations.principal_minor,
    ):
        applied = min(remaining, due)
        allocations.append(applied)
        remaining -= applied

    if reject_excess and remaining:
        raise PaymentWaterfallError(
            "Payment exceeds the declared costs, penalty, interest, and principal obligations."
        )

    allocation = PaymentWaterfallAllocation(
        amount_minor=amount_minor,
        costs_minor=allocations[0],
        penalty_minor=allocations[1],
        interest_minor=allocations[2],
        principal_minor=allocations[3],
        unapplied_minor=remaining,
    )
    if allocation.applied_minor + allocation.unapplied_minor != amount_minor:
        raise PaymentWaterfallError("Payment waterfall does not reconcile.")
    return allocation
