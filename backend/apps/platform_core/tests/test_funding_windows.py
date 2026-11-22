"""IP of Webby-Soft SRL. Funding windows and the 18.4 return schedule (Q01, F01, F17)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.apps.platform_core.domain.funding import (
    BALANCE_AUTO_RETURN_AFTER_DAYS,
    DEFAULT_RETURN_NOTICE_DAYS_BEFORE,
    BalanceReturnSchedule,
    balance_covers_funding,
    balance_deadline_date,
    balance_holding_day,
    balance_is_overdue,
    balance_return_is_due,
    balance_return_schedule,
    direct_funding_fits,
    direct_funding_until,
    latest_funding_deadline,
    normalized_auto_return_after_days,
    normalized_cutoff_time,
    normalized_lot_return_after_days,
    normalized_return_notice_days,
)
from backend.apps.platform_core.domain.settlement_calendar import (
    SettlementDays,
    easter_sunday,
    rule_holidays,
    settlement_days_from_rules,
)

ZURICH = ZoneInfo("Europe/Zurich")
CHF = settlement_days_from_rules("CHF")
EUR = settlement_days_from_rules("EUR")


def _at(value: date, hour: int = 12) -> datetime:
    return datetime.combine(value, time(hour), tzinfo=ZURICH)


def _deadline(day_zero: date) -> datetime:
    """withdrawal_deadline_at of a lot whose value date is ``day_zero`` (day 60, midnight)."""
    return datetime.combine(day_zero + timedelta(days=60), time.min, tzinfo=ZURICH)


def _schedule(
    day_zero: date,
    *,
    days: int = 56,
    calendar: SettlementDays | None = CHF,
    processing: int = 1,
) -> BalanceReturnSchedule:
    return balance_return_schedule(
        withdrawal_deadline_at=_deadline(day_zero),
        return_after_days=days,
        calendar=calendar,
        processing_business_days=processing,
    )


def test_rule_calendars_follow_sic_and_target() -> None:
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert easter_sunday(2027) == date(2027, 3, 28)
    chf_2026 = rule_holidays("CHF", 2026)
    assert set(chf_2026) == {
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 5, 1),
        date(2026, 5, 14),
        date(2026, 5, 25),
        date(2026, 8, 1),
        date(2026, 12, 25),
        date(2026, 12, 26),
    }
    # TARGET: no Berchtold's Day, Ascension, Whit Monday or 1 August.
    assert set(rule_holidays("EUR", 2026)) == {
        date(2026, 1, 1),
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 5, 1),
        date(2026, 12, 25),
        date(2026, 12, 26),
    }
    assert CHF.previous_or_same(date(2026, 12, 27)) == date(2026, 12, 24)
    assert CHF.add(date(2026, 12, 24), 1) == date(2026, 12, 28)
    assert EUR.is_settlement_day(date(2026, 5, 14)) and not CHF.is_settlement_day(date(2026, 5, 14))


def test_day_56_is_the_last_day_and_the_return_is_requested_on_day_57() -> None:
    # Value date Monday 2026-09-07 (day 0): day 57 is Tuesday 2026-11-03 (a settlement day).
    day_zero = date(2026, 9, 7)
    schedule = _schedule(day_zero)
    assert BALANCE_AUTO_RETURN_AFTER_DAYS == 56
    assert schedule.return_date == date(2026, 11, 3)
    assert schedule.last_day == date(2026, 11, 2)
    assert schedule.holding_day(schedule.last_day) == 56
    assert schedule.latest_debit_date == date(2026, 11, 5)  # day 59
    assert (
        schedule.legal_limit_date == date(2026, 11, 6) == balance_deadline_date(_deadline(day_zero))
    )
    assert not schedule.adjusted and not schedule.legacy
    assert not balance_return_is_due(schedule=schedule, as_of=_at(schedule.last_day, 23))
    assert balance_return_is_due(schedule=schedule, as_of=_at(schedule.return_date, 0))
    assert not balance_is_overdue(schedule=schedule, as_of=_at(date(2026, 11, 6)))
    assert balance_is_overdue(schedule=schedule, as_of=_at(date(2026, 11, 7)))


def test_a_closed_day_57_moves_the_return_to_the_previous_settlement_day() -> None:
    # Day 57 on Saturday 2026-11-07 -> Friday 2026-11-06 (day 56); the last day becomes day 55.
    day_zero = date(2026, 9, 11)
    schedule = _schedule(day_zero)
    assert schedule.nominal_return_date == date(2026, 11, 7)
    assert schedule.return_date == date(2026, 11, 6)
    assert schedule.last_day == date(2026, 11, 5)
    assert schedule.adjusted


def test_the_processing_time_moves_the_return_earlier_so_the_debit_is_by_day_59() -> None:
    # Day 57 on Friday 2026-11-06: a debit one business day later would be Monday (day 60).
    day_zero = date(2026, 9, 10)
    schedule = _schedule(day_zero)
    assert schedule.nominal_return_date == date(2026, 11, 6)
    # Day 59 is Sunday -> latest debit Friday (day 57) -> the order goes on Thursday (day 56).
    assert schedule.latest_debit_date == date(2026, 11, 6)
    assert schedule.return_date == date(2026, 11, 5)
    assert schedule.last_day == date(2026, 11, 4)
    # Without processing time the return stays on day 57.
    assert _schedule(day_zero, processing=0).return_date == date(2026, 11, 6)


def test_holidays_count_for_each_currency() -> None:
    # Day 57 on Friday 2026-12-25 (Christmas, closed in both calendars).
    day_zero = date(2026, 10, 29)
    chf = _schedule(day_zero, calendar=CHF)
    assert chf.nominal_return_date == date(2026, 12, 25)
    # Day 59 = Sunday 27 -> latest debit Thursday 24; order Wednesday 23.
    assert chf.latest_debit_date == date(2026, 12, 24)
    assert chf.return_date == date(2026, 12, 23)
    # Ascension (closed for CHF only): day 57 on Thursday 2026-05-14.
    day_zero = date(2026, 3, 18)
    assert _schedule(day_zero, calendar=CHF).return_date == date(2026, 5, 13)
    assert _schedule(day_zero, calendar=EUR).return_date == date(2026, 5, 14)


def test_older_lots_keep_the_58_day_dates() -> None:
    day_zero = date(2026, 9, 11)
    schedule = _schedule(day_zero, days=58)
    assert schedule.legacy
    assert schedule.last_day == day_zero + timedelta(days=58)
    assert schedule.return_date == day_zero + timedelta(days=59)
    assert normalized_lot_return_after_days(58) == 58
    assert normalized_lot_return_after_days(None) == 56


def test_new_lots_take_at_most_56_days() -> None:
    assert normalized_auto_return_after_days(30) == 30
    for invalid in (None, 0, 57, 58, 60, "56", 56.0, True):
        assert normalized_auto_return_after_days(invalid) == 56


@pytest.mark.parametrize("remaining_days", [2, 5, 10, 30])
def test_general_rule_the_window_ends_before_the_last_day(remaining_days: int) -> None:
    day_zero = date(2026, 3, 2)
    schedule = _schedule(day_zero, calendar=None)
    as_of = _at(schedule.last_day - timedelta(days=remaining_days))
    last_subscription = schedule.last_day - timedelta(days=1)
    assert balance_covers_funding(
        schedule=schedule, funding_deadline=last_subscription, as_of=as_of
    )
    assert not balance_covers_funding(
        schedule=schedule, funding_deadline=schedule.last_day, as_of=as_of
    )
    assert not balance_covers_funding(
        schedule=schedule, funding_deadline=last_subscription, as_of=_at(schedule.last_day, 0)
    )
    assert (latest_funding_deadline(day_zero) - day_zero).days + 1 == 50


def test_f01_direct_loans_need_the_payout_margin_before_day_56() -> None:
    # Value date Monday 2026-09-07: day 56 is Monday 2026-11-02.
    day_zero = date(2026, 9, 7)
    schedule = _schedule(day_zero)
    as_of = _at(day_zero + timedelta(days=1))

    def fits(deadline: date, margin: int = 3) -> bool:
        return direct_funding_fits(
            schedule=schedule,
            funding_deadline=deadline,
            as_of=as_of,
            calendar=CHF,
            payout_margin_business_days=margin,
        )

    # Close Wednesday 28 Oct + 3 business days = Monday 2 Nov (day 56): fits.
    assert fits(date(2026, 10, 27))
    # Close Thursday 29 Oct + 3 = Tuesday 3 Nov (day 57): too late.
    assert not fits(date(2026, 10, 28))
    # A deadline on Friday (close Saturday) pays out on Wednesday.
    assert not fits(date(2026, 10, 30))
    assert direct_funding_until(
        schedule=schedule, as_of=as_of, calendar=CHF, payout_margin_business_days=3
    ) == date(2026, 10, 27)
    assert direct_funding_until(
        schedule=schedule, as_of=as_of, calendar=CHF, payout_margin_business_days=0
    ) == date(2026, 11, 1)
    # Nothing fits once the last fitting deadline is in the past.
    assert (
        direct_funding_until(
            schedule=schedule,
            as_of=_at(date(2026, 10, 28)),
            calendar=CHF,
            payout_margin_business_days=3,
        )
        is None
    )


def test_holding_day_counts_from_the_value_date() -> None:
    deadline_at = _deadline(date(2026, 1, 1))
    assert balance_holding_day(withdrawal_deadline_at=deadline_at, as_of=_at(date(2026, 1, 1))) == 0
    assert (
        balance_holding_day(withdrawal_deadline_at=deadline_at, as_of=_at(date(2026, 2, 26))) == 56
    )


def test_notice_days_and_cutoff_settings() -> None:
    assert DEFAULT_RETURN_NOTICE_DAYS_BEFORE == (14, 10, 3)
    assert normalized_return_notice_days([3, 14, 10, 3]) == (14, 10, 3)
    for invalid in (None, [], [0], ["3"], {"days": [3]}):
        assert normalized_return_notice_days(invalid) == (14, 10, 3)
    assert normalized_cutoff_time("09:30") == time(9, 30)
    assert normalized_cutoff_time("noon") == time(12, 0)
