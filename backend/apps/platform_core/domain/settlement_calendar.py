"""IP of Webby-Soft SRL. 18.4 (F17): settlement days of the CHF and EUR payment systems.

CHF uses the Swiss interbank system (SIX SIC), EUR the TARGET calendar for ordinary EUR payments.
Saturdays and Sundays are never settlement days. The rule lists below are the regular bank
holidays; operations check each year's list against the bank and the published calendars and can
change it in the admin (Vlad, 2026-11-17).

The functions here are pure: they take a set of holiday dates and do not read the database.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from datetime import date, timedelta

SETTLEMENT_CURRENCIES = ("CHF", "EUR")

# SIX SIC banking holidays (CHF). 24 and 31 December are value days.
SIC_FIXED_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (1, 2, "Berchtold's Day"),
    (5, 1, "Labour Day"),
    (8, 1, "Swiss National Day"),
    (12, 25, "Christmas Day"),
    (12, 26, "St Stephen's Day"),
)
# TARGET closing days (EUR).
TARGET_FIXED_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (5, 1, "Labour Day"),
    (12, 25, "Christmas Day"),
    (12, 26, "Christmas Holiday"),
)

# A safety bound for the day searches below: no real calendar has this many closed days in a row.
MAX_CLOSED_DAYS_IN_A_ROW = 31


def easter_sunday(year: int) -> date:
    """Western Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def rule_holidays(currency: str, year: int) -> dict[date, str]:
    """The regular bank holidays of the currency's payment system in one year, by rule."""
    code = currency.upper()
    easter = easter_sunday(year)
    holidays: dict[date, str] = {
        easter - timedelta(days=2): "Good Friday",
        easter + timedelta(days=1): "Easter Monday",
    }
    if code == "CHF":
        fixed = SIC_FIXED_HOLIDAYS
        holidays[easter + timedelta(days=39)] = "Ascension Day"
        holidays[easter + timedelta(days=50)] = "Whit Monday"
    elif code == "EUR":
        fixed = TARGET_FIXED_HOLIDAYS
    else:
        raise ValueError(f"No settlement calendar rule for {currency}.")
    for month, day, name in fixed:
        holidays[date(year, month, day)] = name
    return dict(sorted(holidays.items()))


def is_weekend(value: date) -> bool:
    return value.weekday() >= 5


class SettlementDays:
    """Settlement-day arithmetic for one currency.

    ``holidays_for_year`` gives the closed days (other than weekends) of a year; each year is
    loaded once, when a date of that year is first checked.
    """

    def __init__(self, holidays_for_year: Callable[[int], Collection[date]]) -> None:
        self._holidays_for_year = holidays_for_year
        self._years: dict[int, frozenset[date]] = {}

    @classmethod
    def from_dates(cls, holidays: Iterable[date]) -> SettlementDays:
        fixed = frozenset(holidays)
        return cls(lambda _year: fixed)

    def holidays(self, year: int) -> frozenset[date]:
        if year not in self._years:
            self._years[year] = frozenset(self._holidays_for_year(year))
        return self._years[year]

    def is_settlement_day(self, value: date) -> bool:
        return not is_weekend(value) and value not in self.holidays(value.year)

    def previous_or_same(self, value: date) -> date:
        """The day itself when it is a settlement day, otherwise the previous one."""
        return self._step(value, -1, include_start=True)

    def next_or_same(self, value: date) -> date:
        return self._step(value, 1, include_start=True)

    def previous(self, value: date) -> date:
        """The last settlement day strictly before ``value``."""
        return self._step(value, -1, include_start=False)

    def add(self, value: date, days: int) -> date:
        """The ``days``-th settlement day after ``value`` (``value`` itself does not count).

        ``add(d, 0)`` is ``d`` when it is a settlement day, otherwise the next one.
        """
        if days < 0:
            raise ValueError("Settlement days to add must not be negative.")
        current = self.next_or_same(value) if days == 0 else value
        for _ in range(days):
            current = self._step(current, 1, include_start=False)
        return current

    def _step(self, value: date, direction: int, *, include_start: bool) -> date:
        current = value if include_start else value + timedelta(days=direction)
        for _ in range(MAX_CLOSED_DAYS_IN_A_ROW + 7):
            if self.is_settlement_day(current):
                return current
            current += timedelta(days=direction)
        raise ValueError("The settlement calendar has no open day near this date.")


def settlement_days_from_rules(currency: str) -> SettlementDays:
    """Settlement days by the rule list alone (tests, and years without a stored calendar)."""
    return SettlementDays(lambda year: rule_holidays(currency, year).keys())
