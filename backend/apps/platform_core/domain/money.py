from __future__ import annotations

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
