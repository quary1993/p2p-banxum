# IP of Webby-Soft SRL.
# source-seal: SVAgQkVMT05HUyBUTyBXRUJCWS1TT0ZUIFNSTC4=
from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
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


# U33-DEC-32: the investor's number format. European "1.234,56" by default, Swiss "1'234.56" as the
# alternative. Values and calculations never change; only the text does.
NUMBER_FORMAT_EUROPEAN = "european"
NUMBER_FORMAT_SWISS = "swiss"
NUMBER_FORMATS = (NUMBER_FORMAT_EUROPEAN, NUMBER_FORMAT_SWISS)
DEFAULT_NUMBER_FORMAT = NUMBER_FORMAT_EUROPEAN
# The canonical text form that messages are written in (and stored in): Swiss with "'".
_CANONICAL_SEPARATORS = ("'", ".")
# The Swiss group sign is the ASCII apostrophe: PDFs are written in Latin-1.
_NUMBER_FORMAT_SEPARATORS = {
    NUMBER_FORMAT_EUROPEAN: (".", ","),
    NUMBER_FORMAT_SWISS: ("'", "."),
}
_ACTIVE_NUMBER_FORMAT: ContextVar[str | None] = ContextVar("banxum_number_format", default=None)
_TEXT_CURRENCIES = "CHF|EUR|USD|GBP|JPY"
_CANONICAL_AMOUNT = re.compile(
    rf"\b({_TEXT_CURRENCIES}) (-?)(\d{{1,3}}(?:'\d{{3}})*)(?:\.(\d+))?(?![\d'])"
)
_CANONICAL_PERCENT = re.compile(r"(?<![\d.,'])(-?\d+)\.(\d+)(?=\s?%)")


def clean_number_format(value: object) -> str:
    return str(value) if value in NUMBER_FORMATS else DEFAULT_NUMBER_FORMAT


@contextmanager
def number_format_context(number_format: str | None) -> Iterator[None]:
    """Write amounts in this format inside the block (a report built for one investor)."""
    token = _ACTIVE_NUMBER_FORMAT.set(clean_number_format(number_format))
    try:
        yield
    finally:
        _ACTIVE_NUMBER_FORMAT.reset(token)


def format_amount_minor(amount_minor: int, currency: str, *, minor_units: int = 2) -> str:
    """Human-readable amount for user-facing text, e.g. "CHF 46'941.30".

    Messages are written in the canonical Swiss form and shown in each investor's format when
    they are rendered (``localize_number_text``). Inside ``number_format_context`` the amount is
    written in that format directly.
    """
    active = _ACTIVE_NUMBER_FORMAT.get()
    group, decimal = (
        _NUMBER_FORMAT_SEPARATORS[active] if active is not None else _CANONICAL_SEPARATORS
    )
    code = normalize_currency(currency)
    sign = "-" if amount_minor < 0 else ""
    value = abs(minor_units_to_decimal(amount_minor, minor_units=minor_units))
    quantized = f"{value:.{minor_units}f}"
    units, _, fraction = quantized.partition(".")
    groups: list[str] = []
    while units:
        groups.append(units[-3:])
        units = units[:-3]
    grouped = group.join(reversed(groups))
    suffix = f"{decimal}{fraction}" if fraction else ""
    return f"{code} {sign}{grouped}{suffix}"


def format_number_minor(amount_minor: int, *, minor_units: int = 2) -> str:
    """A number in currency units without the currency ("46'941.30"), in the active format.

    Outside ``number_format_context`` it is the canonical Swiss form; inside, the investor's
    format (C09: every newly generated personal report).
    """
    return format_amount_minor(amount_minor, "CHF", minor_units=minor_units).removeprefix("CHF ")


def csv_number_format(number_format: str | None) -> tuple[str, str]:
    """F15: (column separator, decimal sign) of a personal CSV, without thousands separators:
    European "1234,56" with ";" columns, Swiss "1234.56" with "," columns."""
    if clean_number_format(number_format) == NUMBER_FORMAT_SWISS:
        return ",", "."
    return ";", ","


def localize_number_text(text: str, number_format: str | None) -> str:
    """Show the canonical amounts ("CHF 1'234.50") and percentages ("7.40%") of a message in
    the investor's format. Other numbers (dates, references) are not touched."""
    if not text:
        return text
    group, decimal = _NUMBER_FORMAT_SEPARATORS[clean_number_format(number_format)]

    def amount(match: re.Match[str]) -> str:
        code, sign, units, fraction = match.groups()
        grouped = units.replace("'", group)
        return f"{code} {sign}{grouped}{decimal + fraction if fraction else ''}"

    text = _CANONICAL_AMOUNT.sub(amount, text)
    return _CANONICAL_PERCENT.sub(lambda match: f"{match.group(1)}{decimal}{match.group(2)}", text)


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
