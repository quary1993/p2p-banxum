from __future__ import annotations

import pytest

from backend.apps.platform_core.domain.payment_waterfall import (
    PAYMENT_WATERFALL_ORDER,
    PaymentWaterfallError,
    PaymentWaterfallObligations,
    allocate_payment_waterfall,
)


def test_payment_waterfall_applies_each_tier_before_principal() -> None:
    obligations = PaymentWaterfallObligations(
        costs_minor=100,
        penalty_minor=200,
        interest_minor=300,
        principal_minor=1_000,
    )

    costs_only = allocate_payment_waterfall(50, obligations)
    assert (costs_only.costs_minor, costs_only.penalty_minor) == (50, 0)

    through_penalty = allocate_payment_waterfall(250, obligations)
    assert (
        through_penalty.costs_minor,
        through_penalty.penalty_minor,
        through_penalty.interest_minor,
        through_penalty.principal_minor,
    ) == (100, 150, 0, 0)

    through_interest = allocate_payment_waterfall(550, obligations)
    assert (
        through_interest.costs_minor,
        through_interest.penalty_minor,
        through_interest.interest_minor,
        through_interest.principal_minor,
    ) == (100, 200, 250, 0)

    with_principal = allocate_payment_waterfall(700, obligations)
    assert (
        with_principal.costs_minor,
        with_principal.penalty_minor,
        with_principal.interest_minor,
        with_principal.principal_minor,
    ) == (100, 200, 300, 100)
    assert with_principal.applied_minor == 700


def test_payment_waterfall_rejects_excess_and_non_integer_amounts() -> None:
    obligations = PaymentWaterfallObligations(principal_minor=100)

    with pytest.raises(PaymentWaterfallError, match="exceeds"):
        allocate_payment_waterfall(101, obligations)
    with pytest.raises(PaymentWaterfallError, match="integer"):
        allocate_payment_waterfall(True, obligations)
    with pytest.raises(PaymentWaterfallError, match="non-negative"):
        PaymentWaterfallObligations(interest_minor=-1)


def test_payment_waterfall_order_is_the_universal_four_tier_contract() -> None:
    assert PAYMENT_WATERFALL_ORDER == (
        "garanta_legal_costs_and_recovery_fee",
        "penalty",
        "interest",
        "principal",
    )
