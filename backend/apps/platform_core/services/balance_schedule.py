"""IP of Webby-Soft SRL. 18.4: the return dates of balance lots, with the currency calendars.

One ``BalanceScheduler`` per operation (a scan, a balance page, a reservation) reads the bank
settings and the settlement calendars once and gives each lot its schedule (Q01) and its direct-loan
funding limit (F01). It works on any object with ``withdrawal_deadline_at``, ``return_after_days``
and a currency (``currency_id`` or ``currency``), so apps that read lots through the app registry
use it too.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from backend.apps.platform_core.domain.funding import (
    BalanceReturnSchedule,
    balance_covers_funding,
    balance_return_schedule,
    direct_funding_fits,
    direct_funding_until,
    normalized_lot_return_after_days,
)
from backend.apps.platform_core.selectors.settings import (
    bank_cutoff_time,
    bank_processing_business_days,
    payout_margin_business_days,
)
from backend.apps.platform_core.services.settlement_calendar import SettlementCalendars


def _lot_currency(lot: Any) -> str:
    currency = getattr(lot, "currency_id", None)
    if currency is None:
        value = getattr(lot, "currency", "")
        currency = getattr(value, "code", value)
    return str(currency or "").upper()


class BalanceScheduler:
    def __init__(self) -> None:
        self.calendars = SettlementCalendars()
        self.processing_business_days = bank_processing_business_days()
        self.payout_margin_business_days = payout_margin_business_days()
        self._cutoff: time | None = None

    @property
    def cutoff(self) -> time:
        if self._cutoff is None:
            self._cutoff = bank_cutoff_time()
        return self._cutoff

    def schedule(self, lot: Any) -> BalanceReturnSchedule:
        return balance_return_schedule(
            withdrawal_deadline_at=lot.withdrawal_deadline_at,
            return_after_days=normalized_lot_return_after_days(
                getattr(lot, "return_after_days", None)
            ),
            calendar=self.calendars.for_currency(_lot_currency(lot)),
            processing_business_days=self.processing_business_days,
        )

    def covers_funding(self, lot: Any, *, funding_deadline: date, as_of: datetime) -> bool:
        """General rule: the funding window ends before the lot's last day."""
        return balance_covers_funding(
            schedule=self.schedule(lot), funding_deadline=funding_deadline, as_of=as_of
        )

    def covers_direct_funding(self, lot: Any, *, funding_deadline: date, as_of: datetime) -> bool:
        """F01 for direct loans: close + payout margin <= day 56 of the lot."""
        calendar = self.calendars.for_currency(_lot_currency(lot))
        schedule = self.schedule(lot)
        if calendar is None:
            return balance_covers_funding(
                schedule=schedule, funding_deadline=funding_deadline, as_of=as_of
            )
        return direct_funding_fits(
            schedule=schedule,
            funding_deadline=funding_deadline,
            as_of=as_of,
            calendar=calendar,
            payout_margin_business_days=self.payout_margin_business_days,
        )

    def direct_funding_until(self, lot: Any, *, as_of: datetime) -> date | None:
        calendar = self.calendars.for_currency(_lot_currency(lot))
        if calendar is None:
            return None
        return direct_funding_until(
            schedule=self.schedule(lot),
            as_of=as_of,
            calendar=calendar,
            payout_margin_business_days=self.payout_margin_business_days,
        )
