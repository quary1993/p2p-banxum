from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client

from backend.apps.platform_core.models import Currency, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    BorrowerRepaymentEventType,
    InvestorRepaymentDistributionLine,
)
from backend.apps.servicing.services import (
    RecordBorrowerRepaymentCommand,
    ScanLoanServicingStatusesCommand,
    ServicingValidationError,
    record_borrower_repayment,
    scan_loan_servicing_statuses,
)


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="servicing-admin@example.test",
            password="AdminPass123!",
            full_name="Servicing Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor_one() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="servicing-investor-1@example.test",
            full_name="Servicing Investor One",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


@pytest.fixture
def investor_two() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="servicing-investor-2@example.test",
            full_name="Servicing Investor Two",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


def _funded_loan_with_holdings(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> Model:
    currency = Currency.objects.get(code="CHF")
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    borrower = borrower_model.objects.create(
        legal_name="Servicing Borrower AG",
        year_founded=2018,
        kyb_status="approved",
        compliance_hold=False,
        country="Switzerland",
        created_by_admin_id=admin_user.pk,
    )
    loan_model = apps.get_model("loans", "Loan")
    loan = cast(
        Model,
        loan_model.objects.create(
            borrower=borrower,
            status="funded",
            title="Servicing Loan",
            investor_summary="Servicing test loan.",
            purpose="working_capital",
            principal_minor=30_000_00,
            currency=currency,
            interest_rate_bps=1_000,
            term_months=2,
            repayment_type="equal_installments",
            funding_deadline=date(2026, 1, 31),
            first_payment_date=date(2026, 2, 28),
            collateral_type="real_estate",
            collateral_value_minor=60_000_00,
            risk_rating="BBB",
            borrower_success_fee_bps=200,
            committed_principal_minor=30_000_00,
            total_scheduled_principal_minor=30_000_00,
            created_by_admin_id=admin_user.pk,
        ),
    )
    installment_model = apps.get_model("loans", "LoanInstallment")
    installment_model.objects.create(
        loan=loan,
        schedule_version=1,
        installment_number=1,
        due_date=date(2026, 2, 28),
        principal_minor=3_000_00,
        interest_minor=300_00,
        total_minor=3_300_00,
    )
    installment_model.objects.create(
        loan=loan,
        schedule_version=1,
        installment_number=2,
        due_date=date(2026, 3, 31),
        principal_minor=27_000_00,
        interest_minor=200_00,
        total_minor=27_200_00,
    )
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holding_model.objects.create(
        loan=loan,
        investor_user_id=investor_one.pk,
        source_type="primary_market",
        source_id="servicing-order-1",
        status="active",
        original_principal_minor=10_000_00,
        current_principal_minor=10_000_00,
        currency=currency,
        loan_share_ppm=333_333,
        assignment_effective_at="2026-02-01T00:00:00Z",
        created_by_admin_id=admin_user.pk,
        idempotency_key="servicing-holding-1",
    )
    holding_model.objects.create(
        loan=loan,
        investor_user_id=investor_two.pk,
        source_type="primary_market",
        source_id="servicing-order-2",
        status="active",
        original_principal_minor=20_000_00,
        current_principal_minor=20_000_00,
        currency=currency,
        loan_share_ppm=666_667,
        assignment_effective_at="2026-02-01T00:00:00Z",
        created_by_admin_id=admin_user.pk,
        idempotency_key="servicing-holding-2",
    )
    return loan


def _funded_amortizing_loan_with_holdings(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> Model:
    currency = Currency.objects.get(code="CHF")
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    borrower = borrower_model.objects.create(
        legal_name="Servicing Amortizing Borrower AG",
        year_founded=2019,
        kyb_status="approved",
        compliance_hold=False,
        country="Switzerland",
        created_by_admin_id=admin_user.pk,
    )
    loan_model = apps.get_model("loans", "Loan")
    loan = cast(
        Model,
        loan_model.objects.create(
            borrower=borrower,
            status="funded",
            title="Servicing Amortizing Loan",
            investor_summary="Servicing amortizing test loan.",
            purpose="working_capital",
            principal_minor=30_000_00,
            currency=currency,
            interest_rate_bps=1_000,
            term_months=4,
            repayment_type="amortizing_principal_interest",
            funding_deadline=date(2026, 1, 31),
            first_payment_date=date(2026, 2, 28),
            collateral_type="real_estate",
            collateral_value_minor=60_000_00,
            risk_rating="BBB",
            borrower_success_fee_bps=200,
            committed_principal_minor=30_000_00,
            total_scheduled_principal_minor=30_000_00,
            created_by_admin_id=admin_user.pk,
        ),
    )
    installment_model = apps.get_model("loans", "LoanInstallment")
    for number, due_date, principal, interest in [
        (1, date(2026, 2, 28), 3_000_00, 300_00),
        (2, date(2026, 3, 31), 9_000_00, 225_00),
        (3, date(2026, 4, 30), 9_000_00, 150_00),
        (4, date(2026, 5, 31), 9_000_00, 75_00),
    ]:
        installment_model.objects.create(
            loan=loan,
            schedule_version=1,
            installment_number=number,
            due_date=due_date,
            principal_minor=principal,
            interest_minor=interest,
            total_minor=principal + interest,
        )
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holding_model.objects.create(
        loan=loan,
        investor_user_id=investor_one.pk,
        source_type="primary_market",
        source_id="servicing-amortizing-order-1",
        status="active",
        original_principal_minor=10_000_00,
        current_principal_minor=10_000_00,
        currency=currency,
        loan_share_ppm=333_333,
        assignment_effective_at="2026-02-01T00:00:00Z",
        created_by_admin_id=admin_user.pk,
        idempotency_key="servicing-amortizing-holding-1",
    )
    holding_model.objects.create(
        loan=loan,
        investor_user_id=investor_two.pk,
        source_type="primary_market",
        source_id="servicing-amortizing-order-2",
        status="active",
        original_principal_minor=20_000_00,
        current_principal_minor=20_000_00,
        currency=currency,
        loan_share_ppm=666_667,
        assignment_effective_at="2026-02-01T00:00:00Z",
        created_by_admin_id=admin_user.pk,
        idempotency_key="servicing-amortizing-holding-2",
    )
    return loan


def _repayment_command(
    admin_user: Model,
    loan: Model,
    *,
    amount_minor: int = 3_300_00,
    booking_date: date = date(2026, 3, 1),
    value_date: date = date(2026, 3, 1),
    warning_acknowledged: bool = False,
    idempotency_key: str = "servicing-repayment-1",
) -> RecordBorrowerRepaymentCommand:
    return RecordBorrowerRepaymentCommand(
        actor=admin_user,
        loan_id=str(loan.pk),
        amount_minor=amount_minor,
        booking_date=booking_date,
        value_date=value_date,
        collection_account_identifier="CH00GARANTALEDGER",
        payer_name="Servicing Borrower AG",
        payer_account_identifier="CH22BORROWER",
        bank_reference=f"BANK-{idempotency_key}",
        payment_reference=f"LOAN-{loan.pk}",
        evidence_reference=f"statement:{idempotency_key}",
        admin_notes="Borrower repayment received.",
        warning_acknowledged=warning_acknowledged,
        idempotency_key=idempotency_key,
    )


@pytest.mark.django_db
def test_record_borrower_repayment_distributes_to_lender_balances(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    result = record_borrower_repayment(_repayment_command(admin_user, loan))
    event = result.repayment_event
    lines = list(
        InvestorRepaymentDistributionLine.objects.filter(repayment_event=event)
        .select_related("holding", "balance_lot")
        .order_by("amount_minor")
    )
    holdings = {
        str(holding.investor_user_id): holding
        for holding in apps.get_model("holdings", "InvestorLoanHolding").objects.filter(
            loan=loan
        )
    }
    postings = list(
        event.journal_entry.postings.select_related("account").order_by("side", "amount_minor")
    )
    ledger = import_module("backend.apps.ledger.services")
    snapshot = ledger.create_reconciliation_snapshot(
        ledger.CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 3, 1),
            bank_stated_balance_minor=3_300_00,
        )
    )

    assert event.event_type == BorrowerRepaymentEventType.REGULAR_INSTALLMENT
    assert event.amount_minor == 3_300_00
    assert event.interest_applied_minor == 300_00
    assert event.principal_applied_minor == 3_000_00
    assert event.expected_due_minor == 3_300_00
    assert event.bank_operation.operation_type == "borrower_repayment"
    assert event.journal_entry.event_type == "borrower_repayment_distributed"
    assert [(line.principal_minor, line.interest_minor, line.amount_minor) for line in lines] == [
        (1_000_00, 100_00, 1_100_00),
        (2_000_00, 200_00, 2_200_00),
    ]
    assert holdings[str(investor_one.pk)].current_principal_minor == 9_000_00
    assert holdings[str(investor_two.pk)].current_principal_minor == 18_000_00
    assert [line.balance_lot.available_amount_minor for line in lines] == [1_100_00, 2_200_00]
    assert {line.balance_lot.source_type for line in lines} == {"installment"}
    assert [(posting.side, posting.amount_minor) for posting in postings] == [
        ("credit", 1_100_00),
        ("credit", 2_200_00),
        ("debit", 3_300_00),
    ]
    assert snapshot.reconciliation_difference_minor == 0
    assert snapshot.investor_balance_liability_minor == 3_300_00
    assert DomainEvent.objects.filter(
        event_type="BorrowerRepaymentRecorded",
        aggregate_id=str(event.id),
    ).exists()


@pytest.mark.django_db
def test_partial_repayment_requires_warning_acknowledgement(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    with pytest.raises(ServicingValidationError, match="warning acknowledgement"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=1_000_00,
                idempotency_key="servicing-partial-no-warning",
            )
        )

    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=1_000_00,
            warning_acknowledged=True,
            idempotency_key="servicing-partial",
        )
    )
    lines = list(
        InvestorRepaymentDistributionLine.objects.filter(
            repayment_event=result.repayment_event
        ).order_by("amount_minor")
    )

    assert result.repayment_event.event_type == BorrowerRepaymentEventType.PARTIAL_INSTALLMENT
    assert result.repayment_event.interest_applied_minor == 300_00
    assert result.repayment_event.principal_applied_minor == 700_00
    assert result.repayment_event.remaining_installment_principal_minor == 2_300_00
    assert [(line.principal_minor, line.interest_minor, line.amount_minor) for line in lines] == [
        (233_33, 100_00, 333_33),
        (466_67, 200_00, 666_67),
    ]


@pytest.mark.django_db
def test_early_repayment_requires_warning_acknowledgement(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    with pytest.raises(ServicingValidationError, match="warning acknowledgement"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=3_301_00,
                idempotency_key="servicing-overpayment",
            )
        )


@pytest.mark.django_db
def test_early_repayment_recalculates_future_schedule(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=13_300_00,
            warning_acknowledged=True,
            idempotency_key="servicing-early-repayment",
        )
    )
    event = result.repayment_event
    lines = list(
        InvestorRepaymentDistributionLine.objects.filter(repayment_event=event).order_by(
            "amount_minor"
        )
    )
    loan.refresh_from_db()
    version_two_rows = list(
        apps.get_model("loans", "LoanInstallment").objects.filter(
            loan=loan,
            schedule_version=2,
        ).order_by("installment_number")
    )
    holdings = {
        str(holding.investor_user_id): holding
        for holding in apps.get_model("holdings", "InvestorLoanHolding").objects.filter(
            loan=loan
        )
    }

    assert event.event_type == BorrowerRepaymentEventType.EARLY_REPAYMENT
    assert event.interest_applied_minor == 300_00
    assert event.principal_applied_minor == 3_000_00
    assert event.future_principal_applied_minor == 10_000_00
    assert [(line.principal_minor, line.interest_minor, line.amount_minor) for line in lines] == [
        (4_333_33, 100_00, 4_433_33),
        (8_666_67, 200_00, 8_866_67),
    ]
    assert holdings[str(investor_one.pk)].current_principal_minor == 5_666_67
    assert holdings[str(investor_two.pk)].current_principal_minor == 11_333_33
    assert cast(Any, loan).status == "funded"
    assert cast(Any, loan).schedule_version == 2
    assert [
        (
            row.installment_number,
            row.principal_minor,
            row.interest_minor,
            row.total_minor,
            row.admin_overridden,
        )
        for row in version_two_rows
    ] == [
        (1, 3_000_00, 300_00, 3_300_00, False),
        (2, 17_000_00, 141_67, 17_141_67, False),
    ]
    assert DomainEvent.objects.filter(
        event_type="LoanScheduleRecalculated",
        aggregate_id=str(loan.pk),
    ).exists()


@pytest.mark.django_db
def test_full_early_repayment_marks_loan_repaid(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=30_300_00,
            warning_acknowledged=True,
            idempotency_key="servicing-full-early-payoff",
        )
    )
    event = result.repayment_event
    loan.refresh_from_db()
    version_two_rows = list(
        apps.get_model("loans", "LoanInstallment").objects.filter(
            loan=loan,
            schedule_version=2,
        )
    )
    holdings = list(
        apps.get_model("holdings", "InvestorLoanHolding").objects.filter(loan=loan)
    )

    assert event.event_type == BorrowerRepaymentEventType.EARLY_REPAYMENT
    assert event.interest_applied_minor == 300_00
    assert event.principal_applied_minor == 3_000_00
    assert event.future_principal_applied_minor == 27_000_00
    assert cast(Any, loan).status == "repaid"
    assert cast(Any, loan).schedule_version == 2
    assert [(row.installment_number, row.principal_minor) for row in version_two_rows] == [
        (1, 3_000_00)
    ]
    assert {holding.current_principal_minor for holding in holdings} == {0}
    assert {holding.status for holding in holdings} == {"closed"}
    assert DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
        payload__new_status="repaid",
    ).exists()


@pytest.mark.django_db
def test_sequential_early_repayments_create_consistent_schedule_versions(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)

    first = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=8_300_00,
            warning_acknowledged=True,
            idempotency_key="servicing-first-sequential-early",
        )
    )
    cast(Any, loan).refresh_from_db()
    second = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=9_516_67,
            booking_date=date(2026, 4, 1),
            value_date=date(2026, 4, 1),
            warning_acknowledged=True,
            idempotency_key="servicing-second-sequential-early",
        )
    )
    cast(Any, loan).refresh_from_db()
    version_three_rows = list(
        apps.get_model("loans", "LoanInstallment").objects.filter(
            loan=loan,
            schedule_version=3,
        ).order_by("installment_number")
    )
    holdings = list(
        apps.get_model("holdings", "InvestorLoanHolding").objects.filter(loan=loan)
    )

    assert first.repayment_event.future_principal_applied_minor == 5_000_00
    assert second.repayment_event.installment.installment_number == 2
    assert second.repayment_event.interest_applied_minor == 183_33
    assert second.repayment_event.principal_applied_minor == 7_333_34
    assert second.repayment_event.future_principal_applied_minor == 2_000_00
    assert cast(Any, loan).schedule_version == 3
    assert cast(Any, loan).total_scheduled_principal_minor == 20_000_00
    assert [
        (
            row.installment_number,
            row.principal_minor,
            row.interest_minor,
            row.total_minor,
            row.admin_overridden,
        )
        for row in version_three_rows
    ] == [
        (2, 7_333_34, 183_33, 7_516_67, False),
        (3, 6_333_33, 105_56, 6_438_89, False),
        (4, 6_333_33, 52_78, 6_386_11, False),
    ]
    assert sum(holding.current_principal_minor for holding in holdings) == 12_666_66
    assert cast(Any, loan).status == "funded"
    assert DomainEvent.objects.filter(
        event_type="LoanScheduleRecalculated",
        aggregate_id=str(loan.pk),
    ).count() == 2


@pytest.mark.django_db
def test_early_repayment_is_not_used_for_late_multi_installment_catchup(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 5),
            loan_ids=(str(loan.pk),),
        )
    )

    with pytest.raises(ServicingValidationError, match="Multiple-installment catch-up"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=13_300_00,
                warning_acknowledged=True,
                idempotency_key="servicing-late-overpayment",
            )
        )


@pytest.mark.django_db
def test_repayment_idempotency_rejects_different_payload(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    result = record_borrower_repayment(_repayment_command(admin_user, loan))
    idempotent = record_borrower_repayment(_repayment_command(admin_user, loan))
    with pytest.raises(ServicingValidationError, match="different repayment request"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=1_000_00,
                warning_acknowledged=True,
            )
        )

    assert idempotent.repayment_event.id == result.repayment_event.id
    assert BorrowerRepaymentEvent.objects.count() == 1


@pytest.mark.django_db
def test_second_repayment_advances_to_next_unpaid_installment(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    first = record_borrower_repayment(_repayment_command(admin_user, loan))
    second = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=27_200_00,
            idempotency_key="servicing-second-installment",
        )
    )
    lines = list(
        InvestorRepaymentDistributionLine.objects.filter(
            repayment_event=second.repayment_event
        ).order_by("amount_minor")
    )
    holdings = list(
        apps.get_model("holdings", "InvestorLoanHolding").objects.filter(loan=loan)
    )

    assert first.repayment_event.installment.installment_number == 1
    assert second.repayment_event.installment.installment_number == 2
    assert second.repayment_event.interest_applied_minor == 200_00
    assert second.repayment_event.principal_applied_minor == 27_000_00
    assert second.repayment_event.remaining_installment_principal_minor == 0
    assert [(line.principal_minor, line.interest_minor, line.amount_minor) for line in lines] == [
        (9_000_00, 66_67, 9_066_67),
        (18_000_00, 133_33, 18_133_33),
    ]
    assert {holding.current_principal_minor for holding in holdings} == {0}
    assert {holding.status for holding in holdings} == {"closed"}
    cast(Any, loan).refresh_from_db()
    assert cast(Any, loan).status == "repaid"
    assert DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
        payload__new_status="repaid",
    ).exists()


@pytest.mark.django_db
def test_status_scan_marks_fully_paid_late_loan_repaid(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    first = record_borrower_repayment(_repayment_command(admin_user, loan))
    second = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=27_200_00,
            idempotency_key="servicing-scan-repaid-second",
        )
    )
    cast(Any, loan).status = "late"
    cast(Any, loan).save(update_fields=["status", "updated_at"])

    result = scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 4, 1),
            loan_ids=(str(loan.pk),),
        )
    )
    cast(Any, loan).refresh_from_db()

    assert first.repayment_event.installment.installment_number == 1
    assert second.repayment_event.installment.installment_number == 2
    assert cast(Any, loan).status == "repaid"
    assert len(result.changes) == 1
    assert result.changes[0].previous_status == "late"
    assert result.changes[0].new_status == "repaid"
    assert result.changes[0].outstanding_minor == 0


@pytest.mark.django_db
def test_status_scan_marks_loan_late_on_day_five(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    result = scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 5),
            loan_ids=(str(loan.pk),),
        )
    )
    loan.refresh_from_db()

    assert cast(Any, loan).status == "late"
    assert len(result.changes) == 1
    assert result.changes[0].previous_status == "funded"
    assert result.changes[0].new_status == "late"
    assert result.changes[0].days_past_due == 5
    assert result.changes[0].outstanding_minor == 3_300_00
    assert DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
    ).exists()


@pytest.mark.django_db
def test_late_loan_returns_to_funded_after_catchup_repayment(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 5),
            loan_ids=(str(loan.pk),),
        )
    )

    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            value_date=date(2026, 3, 6),
            idempotency_key="servicing-late-catchup",
        )
    )
    loan.refresh_from_db()

    assert cast(Any, loan).status == "funded"
    assert result.repayment_event.metadata["installment_number"] == 1
    assert DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
        payload__new_status="funded",
    ).exists()


@pytest.mark.django_db
def test_status_scan_marks_loan_defaulted_on_day_sixteen_and_blocks_normal_repayment(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    result = scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )
    loan.refresh_from_db()

    assert cast(Any, loan).status == "defaulted"
    assert len(result.changes) == 1
    assert result.changes[0].new_status == "defaulted"
    assert result.changes[0].days_past_due == 16
    with pytest.raises(ServicingValidationError, match="recovery workflow"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                idempotency_key="servicing-defaulted-repayment",
            )
        )


@pytest.mark.django_db
def test_status_scan_admin_api(
    client: Client,
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    client.force_login(cast(Any, admin_user))

    response = client.post(
        "/api/v1/servicing/admin/status-scan/",
        data={
            "as_of_date": "2026-03-05",
            "loan_ids": [str(loan.pk)],
        },
        content_type="application/json",
    )
    loan.refresh_from_db()

    assert response.status_code == 200
    payload = response.json()
    assert payload["as_of_date"] == "2026-03-05"
    assert payload["changes"][0]["loan_id"] == str(loan.pk)
    assert payload["changes"][0]["new_status"] == "late"
    assert cast(Any, loan).status == "late"


@pytest.mark.django_db
def test_repayment_admin_api(
    client: Client,
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    client.force_login(cast(Any, admin_user))

    response = client.post(
        "/api/v1/servicing/admin/borrower-repayments/",
        data={
            "loan_id": str(loan.pk),
            "amount_minor": 3_300_00,
            "booking_date": "2026-03-01",
            "value_date": "2026-03-01",
            "collection_account_identifier": "CH00GARANTALEDGER",
            "payer_name": "Servicing Borrower AG",
            "payer_account_identifier": "CH22BORROWER",
            "bank_reference": "BANK-SERVICING-API",
            "payment_reference": f"LOAN-{loan.pk}",
            "evidence_reference": "statement:servicing-api",
            "idempotency_key": "servicing-api",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["repayment_event"]["event_type"] == "regular_installment"
    assert payload["repayment_event"]["amount_minor"] == 3_300_00
    assert len(payload["distribution_lines"]) == 2


@pytest.mark.django_db
def test_servicing_append_only_records_have_app_and_db_guards(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    result = record_borrower_repayment(_repayment_command(admin_user, loan))
    line = result.distribution_lines[0]

    with pytest.raises(AppendOnlyViolation):
        result.repayment_event.notes = "mutated"
        result.repayment_event.save()
    with pytest.raises(AppendOnlyViolation):
        line.metadata = {"mutated": True}
        line.save()

    with pytest.raises(DatabaseError) as update_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE servicing_borrowerrepaymentevent SET notes = %s WHERE id = %s",
                ["mutated", result.repayment_event.id.hex],
            )
    assert "append-only" in str(update_error.value)

    with pytest.raises(DatabaseError) as delete_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM servicing_investorrepaymentdistributionline WHERE id = %s",
                [line.id.hex],
            )
    assert "append-only" in str(delete_error.value)
