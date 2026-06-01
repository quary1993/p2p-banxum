from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


class MoneyError(ValueError):
    pass


def normalize_currency(currency: str) -> str:
    code = currency.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise MoneyError("Currency must be a 3-letter ISO code.")
    return code


@dataclass(frozen=True, slots=True)
class Money:
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if type(self.amount_minor) is not int:
            raise MoneyError("Money amount_minor must be an integer minor-unit amount.")
        object.__setattr__(self, "currency", normalize_currency(self.currency))

    def _assert_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise MoneyError("Money operations require the same currency.")

    def __add__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def is_negative(self) -> bool:
        return self.amount_minor < 0


def decimal_to_minor_units(
    amount: Decimal,
    *,
    minor_units: int,
    rounding: str = ROUND_HALF_UP,
) -> int:
    if minor_units < 0:
        raise MoneyError("minor_units cannot be negative.")

    exponent = Decimal("1").scaleb(-minor_units)
    quantized = amount.quantize(exponent, rounding=rounding)
    multiplier = Decimal(10) ** minor_units
    return int(quantized * multiplier)


def minor_units_to_decimal(amount_minor: int, *, minor_units: int) -> Decimal:
    if minor_units < 0:
        raise MoneyError("minor_units cannot be negative.")
    divisor = Decimal(10) ** minor_units
    return Decimal(amount_minor) / divisor


@dataclass(frozen=True, slots=True)
class Rate:
    value: Decimal

    def __post_init__(self) -> None:
        if self.value.is_nan() or self.value.is_infinite():
            raise MoneyError("Rate must be finite.")

    @classmethod
    def percent(cls, percent_value: Decimal) -> Rate:
        return cls(percent_value / Decimal("100"))

    def apply_to_minor_units(self, amount_minor: int, *, rounding: str = ROUND_HALF_UP) -> int:
        return int((Decimal(amount_minor) * self.value).quantize(Decimal("1"), rounding=rounding))


def allocate_by_weights(total: Money, weights: Sequence[int]) -> list[Money]:
    if total.amount_minor < 0:
        raise MoneyError("Cannot allocate a negative amount.")
    if not weights:
        raise MoneyError("At least one allocation weight is required.")
    if any(type(weight) is not int for weight in weights):
        raise MoneyError("Allocation weights must be integers.")
    if any(weight < 0 for weight in weights):
        raise MoneyError("Allocation weights cannot be negative.")

    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise MoneyError("At least one allocation weight must be positive.")

    raw_products = [total.amount_minor * weight for weight in weights]
    base_amounts = [product // weight_sum for product in raw_products]
    remainders = [product % weight_sum for product in raw_products]
    residue = total.amount_minor - sum(base_amounts)

    ranked_indexes = sorted(range(len(weights)), key=lambda index: (-remainders[index], index))
    for index in ranked_indexes[:residue]:
        base_amounts[index] += 1

    return [Money(amount, total.currency) for amount in base_amounts]


def split_evenly(total: Money, parts: int) -> list[Money]:
    if type(parts) is not int or parts <= 0:
        raise MoneyError("parts must be a positive integer.")
    return allocate_by_weights(total, [1] * parts)
