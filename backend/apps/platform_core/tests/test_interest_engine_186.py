"""IP of Webby-Soft SRL. 18.6: the interest engine against the validated rules and examples.

The examples are the ones of "BANXUM: Interest, Late Payments, Penalties And Default" (validated by
Vlad on 18 November 2026): CHF 10,000 at 12%, payout Tuesday 15 December 2026, monthly installments
of CHF 900 principal, penalty X 0.05% per day, Late 15 / Default 60 days, no grace.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.apps.platform_core.domain import interest_engine as engine
from backend.apps.platform_core.domain.settlement_calendar import settlement_days_from_rules

CHF_DAYS = settlement_days_from_rules("CHF")
RATE_BPS = 1_200
X = engine.penalty_rate_fraction(Decimal("0.05"))
PAYOUT = date(2026, 12, 15)


def _example_rows() -> list[engine.EngineRow]:
    """The mechanics example: 11 rows of 900 principal and a last row of 100."""
    custom = tuple(
        engine.CustomRow(
            original_due_date=engine.add_months_from_anchor(PAYOUT, number),
            principal_minor=900_00 if number < 12 else 100_00,
        )
        for number in range(1, 13)
    )
    return engine.generate_schedule(
        engine.ScheduleTerms(
            principal_minor=10_000_00,
            annual_rate_bps=RATE_BPS,
            payout_date=PAYOUT,
            term_months=12,
            frequency="monthly",
            kind=engine.KIND_CUSTOM,
            custom_rows=custom,
        ),
        CHF_DAYS,
    )


def _position(rows: list[engine.EngineRow]) -> engine.LoanPosition:
    return engine.LoanPosition(
        through_date=PAYOUT,
        penalty_rate=X,
        installments=engine.open_installments_from_rows(rows),
    )


def test_the_first_three_installments_of_the_example() -> None:
    rows = _example_rows()

    assert [
        (row.due_date, row.interest_days, row.interest_minor, row.total_minor) for row in rows[:3]
    ] == [
        (date(2027, 1, 15), 31, 101_92, 1_001_92),
        (date(2027, 2, 15), 31, 92_75, 992_75),
        (date(2027, 3, 15), 28, 75_48, 975_48),
    ]
    # Interest starts on the payout day and each period ends the day before its due date.
    assert rows[0].interest_start == PAYOUT
    assert rows[1].interest_start == date(2027, 1, 15)


def test_case_a_paid_on_time_costs_no_penalty() -> None:
    position = _position(_example_rows())

    allocation = engine.allocate_payment(
        position,
        amount_minor=1_001_92,
        value_date=date(2027, 1, 15),
        annual_rate_bps=RATE_BPS,
        kind="custom",
    )

    assert (allocation.penalty_minor, allocation.interest_minor, allocation.principal_minor) == (
        0,
        101_92,
        900_00,
    )
    assert allocation.unapplied_minor == 0
    assert allocation.new_future_rows is None


def test_case_b_three_days_late_is_pending_then_pays_x_for_three_days() -> None:
    rows = _example_rows()
    status = [
        engine.installment_status(
            oldest_unpaid_due_date=date(2027, 1, 15),
            as_of=day,
            days=CHF_DAYS,
            late_days=15,
            default_days=60,
            default_declared=False,
        ).status
        for day in (date(2027, 1, 15), date(2027, 1, 18), date(2027, 1, 19), date(2027, 1, 20))
    ]
    position = _position(rows)

    allocation = engine.allocate_payment(
        position,
        amount_minor=1_003_42,
        value_date=date(2027, 1, 18),
        annual_rate_bps=RATE_BPS,
        kind="custom",
    )

    assert status == ["pending", "pending", "pending", "due"]
    # 16, 17 and 18 January (weekend included): 1,001.92 x 0.05% x 3 = 1.50.
    assert (allocation.penalty_minor, allocation.interest_minor, allocation.principal_minor) == (
        1_50,
        101_92,
        900_00,
    )
    assert allocation.unapplied_minor == 0


def test_case_c_lawyer_notice_then_the_borrower_catches_up() -> None:
    position = _position(_example_rows())
    position.expenses.append(
        engine.OpenExpense(key="lawyer", value_date=date(2027, 2, 1), amount_owed=300_00)
    )
    statuses = {
        day: engine.installment_status(
            oldest_unpaid_due_date=date(2027, 1, 15),
            as_of=day,
            days=CHF_DAYS,
            late_days=15,
            default_days=60,
            default_declared=False,
        )
        for day in (date(2027, 1, 20), date(2027, 1, 30))
    }

    allocation = engine.allocate_payment(
        position,
        amount_minor=1_316_29,
        value_date=date(2027, 2, 10),
        annual_rate_bps=RATE_BPS,
        kind="custom",
    )

    assert (statuses[date(2027, 1, 20)].status, statuses[date(2027, 1, 20)].days_late) == ("due", 5)
    assert statuses[date(2027, 1, 30)].status == "late"
    # Expense 300 + its X 1.35 (9 days), then installment 1: X 13.02 (26 days), 101.92, 900.
    assert allocation.expenses_minor == 300_00
    assert allocation.penalty_minor == 1_35 + 13_02
    assert (allocation.interest_minor, allocation.principal_minor) == (101_92, 900_00)
    assert allocation.unapplied_minor == 0
    assert position.oldest_unpaid_due_date(date(2027, 2, 10)) is None


def test_case_d_default_whole_amount_and_a_payment_after_it() -> None:
    position = _position(_example_rows())
    position.expenses.append(
        engine.OpenExpense(key="lawyer", value_date=date(2027, 2, 1), amount_owed=300_00)
    )
    declared_on = date(2027, 3, 19)
    alert = engine.installment_status(
        oldest_unpaid_due_date=date(2027, 1, 15),
        as_of=date(2027, 3, 16),
        days=CHF_DAYS,
        late_days=15,
        default_days=60,
        default_declared=False,
    )

    principal, interest = engine.default_whole_amount(
        position=position, declared_on=declared_on, annual_rate_bps=RATE_BPS
    )
    engine.freeze_penalties_at_default(position, declared_on)
    # The schedule stops: one row with the whole amount (the service writes it as a new version).
    position.installments = [
        engine.OpenInstallment(
            key="default",
            number=1,
            due_date=declared_on,
            interest_start=declared_on,
            principal_owed=principal,
            interest_owed=interest,
            original_due_date=declared_on,
        )
    ]

    assert alert.status == "late" and alert.default_possible
    assert (principal, interest) == (10_000_00, 270_15 + 12_00)
    assert position.frozen_penalty_minor == 31_56 + 6_90 + 15_88 + 1_95
    assert principal + interest + position.expenses_owed == 10_582_15

    allocation = engine.allocate_payment(
        position,
        amount_minor=2_000_00,
        value_date=date(2027, 3, 31),
        annual_rate_bps=RATE_BPS,
        kind="custom",
    )

    assert allocation.expenses_minor == 300_00
    assert allocation.penalty_minor == 56_29 + 63_49
    assert allocation.interest_minor == 282_15
    assert allocation.principal_minor == 1_298_07
    assert position.principal_owed == 8_701_93


def test_a_payment_cannot_be_more_than_what_is_owed() -> None:
    position = _position(_example_rows())

    allocation = engine.allocate_payment(
        position,
        amount_minor=20_000_00,
        value_date=date(2027, 1, 15),
        annual_rate_bps=RATE_BPS,
        kind="custom",
    )

    assert allocation.principal_minor == 10_000_00
    assert allocation.unapplied_minor > 0


def _equal(
    term_months: int = 12, frequency: str = "monthly", **extra: object
) -> list[engine.EngineRow]:
    return engine.generate_schedule(
        engine.ScheduleTerms(
            principal_minor=10_000_00,
            annual_rate_bps=RATE_BPS,
            payout_date=PAYOUT,
            term_months=term_months,
            frequency=frequency,
            kind=engine.KIND_EQUAL_INSTALLMENTS,
            **extra,  # type: ignore[arg-type]
        ),
        CHF_DAYS,
    )


def test_equal_total_installments_repay_the_principal_with_a_level_total() -> None:
    rows = _equal()

    assert sum(row.principal_minor for row in rows) == 10_000_00
    totals = {row.total_minor for row in rows[:-1]}
    assert len(totals) == 1
    assert abs(rows[-1].total_minor - totals.pop()) < 100
    assert rows[-1].original_due_date == date(2027, 12, 15)


def test_frequencies_interest_only_periods_and_full_payment_at_maturity() -> None:
    quarterly = _equal(term_months=24, frequency="quarterly")
    with_interest_only = _equal(term_months=12, interest_only_periods=3)
    maturity = engine.generate_schedule(
        engine.ScheduleTerms(
            principal_minor=10_000_00,
            annual_rate_bps=RATE_BPS,
            payout_date=PAYOUT,
            term_months=12,
            frequency="monthly",
            kind=engine.KIND_FULL_AT_MATURITY,
        ),
        CHF_DAYS,
    )
    bullet = engine.generate_schedule(
        engine.ScheduleTerms(
            principal_minor=10_000_00,
            annual_rate_bps=RATE_BPS,
            payout_date=PAYOUT,
            term_months=12,
            frequency="half_yearly",
            kind=engine.KIND_PERIODIC_INTEREST,
        ),
        CHF_DAYS,
    )

    assert len(quarterly) == 8 and quarterly[0].original_due_date == date(2027, 3, 15)
    assert [row.principal_minor for row in with_interest_only[:3]] == [0, 0, 0]
    assert sum(row.principal_minor for row in with_interest_only) == 10_000_00
    assert len(maturity) == 1 and maturity[0].principal_minor == 10_000_00
    # 15 Dec 2026 - 14 Dec 2027 = 365 days: exactly 12% of 10,000.
    assert maturity[0].interest_minor == 1_200_00
    assert [row.principal_minor for row in bullet] == [0, 10_000_00]
    with pytest.raises(engine.InterestEngineError):
        _equal(term_months=10, frequency="quarterly")


def test_due_dates_keep_the_payout_day_and_move_to_the_previous_business_day() -> None:
    # Short months use their last day, then the reference day returns.
    assert [engine.add_months_from_anchor(date(2027, 1, 31), months) for months in (1, 2)] == [
        date(2027, 2, 28),
        date(2027, 3, 31),
    ]
    # Saturday 15 May 2027 -> Friday 14 May.
    assert engine.adjust_due_date(date(2027, 5, 15), CHF_DAYS, 0) == date(2027, 5, 14)
    # Grace of 2 business days: Thursday 10 December -> Monday 14 December.
    assert engine.adjust_due_date(date(2026, 12, 10), CHF_DAYS, 2) == date(2026, 12, 14)


def test_custom_rows_are_checked_before_use() -> None:
    def check(rows: list[tuple[date, int]]) -> None:
        engine.validate_custom_rows(
            [
                engine.CustomRow(original_due_date=day, principal_minor=amount)
                for day, amount in rows
            ],
            principal_minor=1_000_00,
            payout_date=PAYOUT,
        )

    check([(date(2027, 1, 15), 0), (date(2027, 6, 15), 1_000_00)])
    for bad in (
        [(date(2026, 12, 15), 1_000_00)],
        [(date(2027, 2, 15), 500_00), (date(2027, 1, 15), 500_00)],
        [(date(2027, 1, 15), -1), (date(2027, 2, 15), 1_000_01)],
        [(date(2027, 1, 15), 999_00)],
    ):
        with pytest.raises(engine.InterestEngineError):
            check(bad)


def test_an_early_regular_payment_is_recalculated_and_the_maturity_stays() -> None:
    rows = _equal()
    position = _position(rows)

    # Installment 1 (due Friday 15 January) paid on Tuesday 12 January with its full total.
    allocation = engine.allocate_payment(
        position,
        amount_minor=rows[0].total_minor,
        value_date=date(2027, 1, 12),
        annual_rate_bps=RATE_BPS,
        kind=engine.KIND_EQUAL_INSTALLMENTS,
    )

    # 15 December - 11 January = 28 days of interest on 10,000; the rest repays principal.
    assert allocation.accrued_interest_days == 28
    assert allocation.interest_minor == 92_05
    assert allocation.principal_minor == rows[0].total_minor - 92_05
    assert allocation.new_future_rows is not None
    new_rows = allocation.new_future_rows
    assert new_rows[0].interest_start == date(2027, 1, 12)
    assert new_rows[-1].due_date == rows[-1].due_date
    assert sum(row.principal_minor for row in new_rows) == 10_000_00 - allocation.principal_minor
    assert new_rows[0].total_minor < rows[1].total_minor


def test_a_small_early_payment_reduces_the_current_installment_only() -> None:
    rows = _equal()
    position = _position(rows)

    allocation = engine.allocate_payment(
        position,
        amount_minor=300_00,
        value_date=date(2027, 1, 5),
        annual_rate_bps=RATE_BPS,
        kind=engine.KIND_EQUAL_INSTALLMENTS,
    )

    current = position.installments[0]
    assert allocation.new_future_rows is None
    assert allocation.interest_minor == engine.interest_minor(
        10_000_00, RATE_BPS, PAYOUT, date(2027, 1, 5)
    )
    assert current.principal_owed == rows[0].principal_minor - allocation.principal_minor
    assert current.interest_start == date(2027, 1, 5)
    # Later installments do not change.
    assert position.installments[1].owed == rows[1].total_minor
