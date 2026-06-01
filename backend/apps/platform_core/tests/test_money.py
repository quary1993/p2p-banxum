from __future__ import annotations

from decimal import Decimal

import pytest

from backend.apps.platform_core.domain.money import (
    Money,
    MoneyError,
    Rate,
    decimal_to_minor_units,
    minor_units_to_decimal,
)


def test_money_addition_requires_same_currency() -> None:
    assert Money(100, "chf") + Money(250, "CHF") == Money(350, "CHF")

    with pytest.raises(MoneyError):
        _ = Money(100, "CHF") + Money(100, "EUR")


def test_half_up_decimal_conversion_to_minor_units() -> None:
    assert decimal_to_minor_units(Decimal("10.235"), minor_units=2) == 1024
    assert decimal_to_minor_units(Decimal("10.234"), minor_units=2) == 1023
    assert minor_units_to_decimal(1024, minor_units=2) == Decimal("10.24")


def test_rate_applies_to_minor_units_with_half_up_rounding() -> None:
    assert Rate.percent(Decimal("1.5")).apply_to_minor_units(10000) == 150
    assert Rate(Decimal("0.3333")).apply_to_minor_units(100) == 33
