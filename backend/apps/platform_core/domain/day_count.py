"""IP of Webby-Soft SRL. 18.7 (F03): day-count conventions of imported Loan Originator claims.

The admin records the exact convention of the claim contract at import; anything else is refused
until it is supported. The platform uses the convention to price the accrued interest of the
transferred rights (``accrued_interest_minor``); the originator's schedule amounts stay as imported.

Conventions (ISDA 2006 definitions):

- ``act_365_fixed``: actual days / 365.
- ``act_360``: actual days / 360.
- ``act_act_isda``: days in each calendar year / days of that year (365 or 366), added up.
- ``thirty_360_bond_basis``: 30/360 Bond Basis (ISDA 4.16(f)).
- ``thirty_e_360``: 30E/360, Eurobond basis (ISDA 4.16(g)).
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

ACT_365_FIXED = "act_365_fixed"
ACT_360 = "act_360"
ACT_ACT_ISDA = "act_act_isda"
THIRTY_360_BOND_BASIS = "thirty_360_bond_basis"
THIRTY_E_360 = "thirty_e_360"

CONVENTIONS: dict[str, str] = {
    ACT_365_FIXED: "Actual/365 Fixed",
    ACT_360: "Actual/360",
    ACT_ACT_ISDA: "Actual/Actual ISDA",
    THIRTY_360_BOND_BASIS: "30/360 Bond Basis",
    THIRTY_E_360: "30E/360",
}


class DayCountError(ValueError):
    pass


def require_convention(value: str) -> str:
    convention = str(value or "").strip()
    if convention not in CONVENTIONS:
        raise DayCountError(
            "Record the day-count convention of the claim contract: "
            + ", ".join(CONVENTIONS.values())
            + ". Another convention is not supported yet."
        )
    return convention


def _thirty_360_days(start: date, end: date, *, eurobond: bool) -> int:
    d1, d2 = start.day, end.day
    if eurobond:
        d1 = min(d1, 30)
        d2 = min(d2, 30)
    else:
        d1 = min(d1, 30)
        if d1 == 30:
            d2 = min(d2, 30)
    return 360 * (end.year - start.year) + 30 * (end.month - start.month) + (d2 - d1)


# Day units per year of each convention. Act/Act ISDA counts a day of a 365-day year as 366 units
# and a day of a leap year as 365 units, so its year fraction is units / (365 x 366) exactly.
_UNITS_PER_YEAR = {
    ACT_365_FIXED: 365,
    ACT_360: 360,
    THIRTY_360_BOND_BASIS: 360,
    THIRTY_E_360: 360,
    ACT_ACT_ISDA: 365 * 366,
}


def day_units(start: date, end: date, convention: str) -> int:
    """Whole day units from ``start`` (included) to ``end`` (excluded); 0 when end <= start."""
    convention = require_convention(convention)
    if end <= start:
        return 0
    if convention in (ACT_365_FIXED, ACT_360):
        return (end - start).days
    if convention == THIRTY_360_BOND_BASIS:
        return _thirty_360_days(start, end, eurobond=False)
    if convention == THIRTY_E_360:
        return _thirty_360_days(start, end, eurobond=True)
    total = 0
    cursor = start
    while cursor < end:
        piece_end = min(end, date(cursor.year + 1, 1, 1))
        weight = 365 if calendar.isleap(cursor.year) else 366
        total += (piece_end - cursor).days * weight
        cursor = piece_end
    return total


def year_fraction(start: date, end: date, convention: str) -> Decimal:
    """The fraction of a year from ``start`` (included) to ``end`` (excluded)."""
    units = day_units(start, end, convention)
    return Decimal(units) / Decimal(_UNITS_PER_YEAR[require_convention(convention)])


def accrued_interest_minor(
    *,
    period_interest_minor: int,
    period_principal_minor: int,
    principal_minor: int,
    accrual_start: date,
    due_date: date,
    reference_date: date,
    participation_bps: int,
    convention: str,
) -> int:
    """The investor's part of the interest of the running period up to ``reference_date``.

    ``period_interest_minor`` is the imported interest of the period (from ``accrual_start`` to
    ``due_date``) on ``period_principal_minor``. The part for ``principal_minor`` accrued to the
    reference date (excluded) is pro rata by the convention's day units, times the investor's
    interest participation; exact integer arithmetic, rounded half up to the cent once.
    """
    if not accrual_start < due_date:
        raise DayCountError("The interest period must end after it starts.")
    if not accrual_start <= reference_date < due_date:
        raise DayCountError("The reference day must be inside the running interest period.")
    if period_principal_minor <= 0 or principal_minor <= 0 or period_interest_minor <= 0:
        return 0
    if principal_minor > period_principal_minor:
        raise DayCountError("The principal cannot be more than the principal of the period.")
    part = day_units(accrual_start, reference_date, convention)
    whole = day_units(accrual_start, due_date, convention)
    if whole <= 0 or part <= 0:
        return 0
    numerator = period_interest_minor * principal_minor * part * participation_bps
    denominator = period_principal_minor * whole * 10_000
    return (2 * numerator + denominator) // (2 * denominator)
