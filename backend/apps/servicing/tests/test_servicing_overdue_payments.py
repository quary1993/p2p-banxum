"""Payments on loans with overdue installments, and interest after early installments.

Audit A-10: a payment on a loan with overdue installments goes to the overdue items
first (interest, then principal, oldest first). Overdue rows are never re-amortized
into the future and the loan stays Late until every overdue amount is paid. Only
money beyond all overdue amounts is a prepayment that re-amortizes future rows.

Audit A-11: after an early regular installment, a prepayment never charges again
the interest days that the early installment already paid.

Loan used by most tests (``_funded_amortizing_loan_with_holdings``): CHF 30,000 at
10 % (equal principal), holdings 10,000 / 20,000, schedule v1:
  1: 2026-02-28  3,000.00 + 300.00
  2: 2026-03-31  9,000.00 + 225.00
  3: 2026-04-30  9,000.00 + 150.00
  4: 2026-05-31  9,000.00 +  75.00
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.test import Client

from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    BorrowerRepaymentEventType,
    InvestorRepaymentDistributionLine,
)
from backend.apps.servicing.services import (
    PreviewAdvanceRepaymentCommand,
    ScanLoanServicingStatusesCommand,
    ServicingValidationError,
    get_loan_repayment_schedule_snapshots,
    preview_borrower_repayment_in_advance,
    record_borrower_repayment,
    scan_loan_servicing_statuses,
)
from backend.apps.servicing.tests.test_servicing_repayments import (  # noqa: F401
    _funded_amortizing_loan_with_holdings,
    _repayment_command,
    admin_user,
    investor_one,
    investor_two,
)


def _rows(loan: Model) -> list[tuple[int, date, int, int]]:
    loan.refresh_from_db()
    return [
        (row.installment_number, row.due_date, row.principal_minor, row.interest_minor)
        for row in apps.get_model("loans", "LoanInstallment")
        .objects.filter(loan=loan, schedule_version=cast(Any, loan).schedule_version)
        .order_by("installment_number")
    ]


def _holding_principals(loan: Model) -> list[int]:
    return [
        int(holding.current_principal_minor)
        for holding in apps.get_model("holdings", "InvestorLoanHolding")
        .objects.filter(loan=loan)
        .order_by("original_principal_minor")
    ]


def _scan(admin: Model, loan: Model, as_of: date) -> None:
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(actor=admin, as_of_date=as_of, loan_ids=(str(loan.pk),))
    )
    loan.refresh_from_db()


def _advance(admin: Model, loan: Model, amount: int, day: date, key: str) -> Any:
    return record_borrower_repayment(
        _repayment_command(
            admin,
            loan,
            amount_minor=amount,
            booking_date=day,
            value_date=day,
            repayment_in_advance=True,
            borrower_repayment_bank_date=day,
            idempotency_key=key,
        )
    )


@pytest.mark.django_db
def test_small_payment_on_late_loan_pays_overdue_items_and_keeps_loan_late(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)
    _scan(admin_user, loan, date(2026, 3, 5))
    assert cast(Any, loan).status == "late"

    # FINCODE-07 repro: 382.19 on 2026-03-10. Old code: interest 300.00 + 82.19
    # accrued, principal 0, all 30,000.00 re-amortized over rows 2-4, loan active.
    # New rule: overdue interest 300.00 first, then 82.19 of overdue principal.
    result = _advance(admin_user, loan, 382_19, date(2026, 3, 10), "late-small")
    event = result.repayment_event
    lines = list(
        InvestorRepaymentDistributionLine.objects.filter(repayment_event=event).order_by(
            "amount_minor"
        )
    )

    assert event.event_type == BorrowerRepaymentEventType.PARTIAL_INSTALLMENT
    assert event.interest_applied_minor == 300_00
    assert event.principal_applied_minor == 82_19
    assert event.future_principal_applied_minor == 0
    assert event.metadata["accrued_interest_minor"] == 0
    assert event.metadata["overdue_interest_applied_minor"] == 300_00
    assert event.metadata["overdue_principal_applied_minor"] == 82_19
    assert event.metadata["overdue_remaining_minor"] == 2_917_81
    assert event.metadata["prepayment_minor"] == 0
    # Interest of installment 1 is paid, so interest is paid through its due date.
    assert event.metadata["interest_paid_through_date"] == "2026-02-28"
    # Pro rata 1/3 : 2/3; the extra cent goes to the largest remainder.
    assert [(line.principal_minor, line.interest_minor) for line in lines] == [
        (27_40, 100_00),
        (54_79, 200_00),
    ]
    assert _holding_principals(loan) == [9_972_60, 19_945_21]
    # Installment 1 stays due on 2026-02-28 for what is left; rows 2-4 unchanged.
    assert _rows(loan) == [
        (1, date(2026, 2, 28), 2_917_81, 0),
        (2, date(2026, 3, 31), 9_000_00, 225_00),
        (3, date(2026, 4, 30), 9_000_00, 150_00),
        (4, date(2026, 5, 31), 9_000_00, 75_00),
    ]
    assert cast(Any, loan).status == "late"

    # The days-past-due clock keeps running from the original due date.
    _scan(admin_user, loan, date(2026, 3, 10))
    assert cast(Any, loan).status == "late"
    _scan(admin_user, loan, date(2026, 3, 16))
    assert cast(Any, loan).status == "defaulted"


@pytest.mark.django_db
def test_rest_of_overdue_installment_paid_as_regular_payment_cures_the_loan(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)
    _scan(admin_user, loan, date(2026, 3, 5))
    _advance(admin_user, loan, 59_22, date(2026, 3, 6), "late-tiny")
    loan.refresh_from_db()
    assert cast(Any, loan).status == "late"
    # 59.22 pays only part of the 300.00 overdue interest.
    assert _rows(loan)[0] == (1, date(2026, 2, 28), 3_000_00, 240_78)
    schedule = get_loan_repayment_schedule_snapshots(loans=[loan], as_of_date=date(2026, 3, 6))[
        str(loan.pk)
    ]
    assert [(row.label, row.status) for row in schedule[:2]] == [
        ("Remaining installment 1", "overdue"),
        ("Payment of overdue amounts", "paid"),
    ]

    # The regular payment is the rest of installment 1, exactly.
    regular = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=3_240_78,
            booking_date=date(2026, 3, 7),
            value_date=date(2026, 3, 7),
            idempotency_key="late-rest",
        )
    )
    loan.refresh_from_db()
    assert regular.repayment_event.event_type == BorrowerRepaymentEventType.REGULAR_INSTALLMENT
    assert regular.repayment_event.interest_applied_minor == 240_78
    assert regular.repayment_event.principal_applied_minor == 3_000_00
    assert cast(Any, loan).status == "active"
    assert _holding_principals(loan) == [9_000_00, 18_000_00]


@pytest.mark.django_db
def test_payment_dated_in_grace_period_does_not_cure_a_late_loan(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)
    _scan(admin_user, loan, date(2026, 3, 6))
    assert cast(Any, loan).status == "late"

    # Paid on day 3 but recorded after the loan went Late. 500.00 pays interest
    # 300.00 and principal 200.00 of installment 1; 2,800.00 stays overdue.
    _advance(admin_user, loan, 500_00, date(2026, 3, 3), "grace-partial")
    loan.refresh_from_db()

    assert cast(Any, loan).status == "late"
    assert _rows(loan)[0] == (1, date(2026, 2, 28), 2_800_00, 0)


@pytest.mark.django_db
def test_payment_beyond_all_overdue_amounts_is_a_prepayment(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)
    _scan(admin_user, loan, date(2026, 3, 5))

    plan = preview_borrower_repayment_in_advance(
        PreviewAdvanceRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=5_000_00,
            borrower_repayment_bank_date=date(2026, 3, 10),
        )
    )
    # Overdue: 300.00 + 3,000.00. Prepayment 1,700.00 = accrued interest
    # 30,000.00 x 10 % x 10/365 = 82.19, then principal 1,617.81.
    assert plan.overdue_interest_applied_minor == 300_00
    assert plan.overdue_principal_applied_minor == 3_000_00
    assert plan.overdue_remaining_minor == 0
    assert plan.prepayment_minor == 1_700_00
    assert plan.accrued_interest_minor == 82_19
    assert plan.accrued_interest_days == 10
    assert plan.interest_applied_minor == 382_19
    assert plan.principal_applied_minor == 4_617_81
    assert plan.outstanding_principal_after_minor == 25_382_19
    assert plan.first_new_installment_interest_start_date == date(2026, 3, 10)

    result = _advance(admin_user, loan, 5_000_00, date(2026, 3, 10), "late-cure")
    event = result.repayment_event
    assert event.event_type == BorrowerRepaymentEventType.EARLY_REPAYMENT
    assert event.principal_applied_minor == 3_000_00
    assert event.future_principal_applied_minor == 1_617_81
    assert event.metadata["interest_paid_through_date"] == "2026-03-10"
    # 25,382.19 / 3 = 8,460.73. Row 2 interest: 25,382.19 x 10 % x 21/365 = 146.03.
    # Rows 3 and 4 keep monthly interest on the remaining balance.
    assert _rows(loan) == [
        (2, date(2026, 3, 31), 8_460_73, 146_03),
        (3, date(2026, 4, 30), 8_460_73, 141_01),
        (4, date(2026, 5, 31), 8_460_73, 70_51),
    ]
    assert cast(Any, loan).status == "active"


@pytest.mark.django_db
def test_two_overdue_installments_interest_first_then_oldest_principal(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)

    # Installments 1 and 2 are both due by 2026-04-02. 1,000.00 pays both
    # interests (300.00 + 225.00) and 475.00 of installment 1 principal.
    plan = preview_borrower_repayment_in_advance(
        PreviewAdvanceRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=1_000_00,
            borrower_repayment_bank_date=date(2026, 4, 2),
        )
    )
    assert [
        (
            row.installment_number,
            row.interest_applied_minor,
            row.principal_applied_minor,
            row.remaining_minor,
        )
        for row in plan.overdue_rows
    ] == [(1, 300_00, 475_00, 2_525_00), (2, 225_00, 0, 9_000_00)]
    assert plan.overdue_only
    assert plan.interest_paid_through_date == date(2026, 3, 31)

    _advance(admin_user, loan, 1_000_00, date(2026, 4, 2), "two-overdue")
    assert _rows(loan) == [
        (1, date(2026, 2, 28), 2_525_00, 0),
        (2, date(2026, 3, 31), 9_000_00, 0),
        (3, date(2026, 4, 30), 9_000_00, 150_00),
        (4, date(2026, 5, 31), 9_000_00, 75_00),
    ]

    # Later, the borrower pays everything overdue plus 1,000.00 more. Interest is
    # already paid through 2026-03-31, so the prepayment owes 10 days on the
    # outstanding 29,525.00: 29,525.00 x 10 % x 10/365 = 80.89.
    plan = preview_borrower_repayment_in_advance(
        PreviewAdvanceRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=12_525_00,
            borrower_repayment_bank_date=date(2026, 4, 10),
        )
    )
    assert plan.overdue_interest_due_minor == 0
    assert plan.overdue_principal_applied_minor == 11_525_00
    assert plan.interest_accrual_start_date == date(2026, 3, 31)
    assert plan.accrued_interest_days == 10
    assert plan.accrued_interest_minor == 80_89
    assert plan.principal_applied_minor == 11_525_00 + 1_000_00 - 80_89


@pytest.mark.django_db
def test_prepayment_after_early_regular_installment_does_not_charge_interest_twice(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)
    record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=3_300_00,
            booking_date=date(2026, 2, 28),
            value_date=date(2026, 2, 28),
            idempotency_key="early-1",
        )
    )
    # Installment 2 (due 2026-03-31) paid early in full: interest paid to 03-31.
    record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=9_225_00,
            booking_date=date(2026, 3, 5),
            value_date=date(2026, 3, 5),
            early_regular_payment_acknowledged=True,
            idempotency_key="early-2",
        )
    )

    plan = preview_borrower_repayment_in_advance(
        PreviewAdvanceRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=2_000_00,
            borrower_repayment_bank_date=date(2026, 3, 10),
        )
    )
    # Nothing accrues: interest is already paid beyond the bank date. The period
    # shown never runs backwards.
    assert plan.accrued_interest_minor == 0
    assert plan.interest_accrual_start_date == date(2026, 3, 10)
    assert plan.interest_accrual_end_date == date(2026, 3, 10)
    assert plan.first_new_installment_interest_start_date == date(2026, 3, 31)

    _advance(admin_user, loan, 2_000_00, date(2026, 3, 10), "early-then-prepay")
    # 16,000.00 left over rows 3 and 4. Row 3 interest runs from 03-31 (not from
    # the bank date 03-10): 16,000.00 x 10 % x 30/365 = 131.51. The old code
    # charged 51 days (223.56), 21 of them already paid by installment 2.
    assert _rows(loan) == [
        (3, date(2026, 4, 30), 8_000_00, 131_51),
        (4, date(2026, 5, 31), 8_000_00, 66_67),
    ]


@pytest.mark.django_db
def test_advance_preview_api_shows_overdue_split(
    client: Client,
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)
    client.force_login(cast(Any, admin_user))

    response = client.post(
        "/api/v1/servicing/admin/borrower-repayments/advance-preview/",
        data={
            "loan_id": str(loan.pk),
            "amount_minor": 382_19,
            "borrower_repayment_bank_date": "2026-03-10",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["overdue_interest_due_minor"] == 300_00
    assert payload["overdue_principal_due_minor"] == 3_000_00
    assert payload["overdue_interest_applied_minor"] == 300_00
    assert payload["overdue_principal_applied_minor"] == 82_19
    assert payload["overdue_remaining_minor"] == 2_917_81
    assert payload["prepayment_minor"] == 0
    assert payload["accrued_interest_minor"] == 0
    assert payload["interest_paid_through_date"] == "2026-02-28"
    assert payload["first_new_installment_interest_start_date"] is None
    assert payload["overdue_rows"] == [
        {
            "installment_number": 1,
            "due_date": "2026-02-28",
            "interest_due_minor": 300_00,
            "principal_due_minor": 3_000_00,
            "interest_applied_minor": 300_00,
            "principal_applied_minor": 82_19,
            "remaining_minor": 2_917_81,
        }
    ]
    assert [row["installment_number"] for row in payload["new_schedule_rows"]] == [1, 2, 3, 4]
    assert not BorrowerRepaymentEvent.objects.exists()


@pytest.mark.django_db
def test_extra_money_below_accrued_interest_is_refused_with_clear_amounts(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)
    with pytest.raises(ServicingValidationError) as error:
        _advance(admin_user, loan, 3_350_00, date(2026, 3, 10), "below-accrued")
    message = str(error.value)
    assert "pays all overdue amounts (CHF 3'300.00)" in message
    assert "CHF 82.19" in message
    assert "at least CHF 3'382.19" in message
    assert not BorrowerRepaymentEvent.objects.exists()


@pytest.mark.django_db
def test_unpaid_installment_is_due_in_grace_period_and_overdue_from_day_five(
    admin_user: Model,  # noqa: F811
    investor_one: Model,  # noqa: F811
    investor_two: Model,  # noqa: F811
) -> None:
    # Audit A-30: the investor saw a red "Overdue" from day 1 while the loan
    # becomes Late only on day 5.
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)

    def first_row_status(as_of: date) -> tuple[str, int]:
        row = get_loan_repayment_schedule_snapshots(loans=[loan], as_of_date=as_of)[str(loan.pk)][0]
        return row.status, row.days_past_due

    assert first_row_status(date(2026, 2, 27)) == ("upcoming", 0)
    assert first_row_status(date(2026, 2, 28)) == ("due", 0)
    assert first_row_status(date(2026, 3, 1)) == ("due", 1)
    assert first_row_status(date(2026, 3, 4)) == ("due", 4)
    assert first_row_status(date(2026, 3, 5)) == ("overdue", 5)
