from __future__ import annotations

from datetime import date, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.platform_core.models import (
    AuditEvent,
    Currency,
    DomainEvent,
    OutboxMessage,
    PlatformSetting,
)
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    BorrowerRepaymentEventType,
    InvestorLossRecognitionLine,
    InvestorRecoveryDistributionLine,
    InvestorRepaymentDistributionLine,
    LoanRecoveryEvent,
    LoanRiskNote,
    LoanWriteOffEvent,
)
from backend.apps.servicing.services import (
    AddLoanRiskNoteCommand,
    PreviewAdvanceRepaymentCommand,
    RecordBorrowerRepaymentCommand,
    RecordLoanRecoveryPaymentCommand,
    RecordLoanWriteOffCommand,
    ScanLoanServicingStatusesCommand,
    ServicingAuthorizationError,
    ServicingValidationError,
    add_loan_risk_note,
    get_loan_repayment_schedule_snapshots,
    get_loan_servicing_status_snapshot,
    list_public_loan_risk_notes,
    preview_borrower_repayment_in_advance,
    record_borrower_repayment,
    record_loan_recovery_payment,
    record_loan_write_off,
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
            status="active",
            title="Servicing Loan",
            investor_summary="Servicing test loan.",
            purpose="working_capital",
            original_principal_minor=30_000_00,
            principal_minor=30_000_00,
            currency=currency,
            interest_rate_bps=1_000,
            term_months=2,
            repayment_type="equal_installments",
            loan_start_date=date(2026, 1, 31),
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
            status="active",
            title="Servicing Amortizing Loan",
            investor_summary="Servicing amortizing test loan.",
            purpose="working_capital",
            original_principal_minor=30_000_00,
            principal_minor=30_000_00,
            currency=currency,
            interest_rate_bps=1_000,
            term_months=4,
            repayment_type="amortizing_principal_interest",
            loan_start_date=date(2026, 1, 31),
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
    repayment_in_advance: bool = False,
    borrower_repayment_bank_date: date | None = None,
    early_regular_payment_acknowledged: bool = False,
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
        repayment_in_advance=repayment_in_advance,
        borrower_repayment_bank_date=borrower_repayment_bank_date,
        early_regular_payment_acknowledged=early_regular_payment_acknowledged,
        idempotency_key=idempotency_key,
    )


def _approve_financial_access(investor: Model) -> None:
    now = timezone.now()
    cast(Any, investor).phone_verified_at = now
    investor.save(update_fields=["phone_verified_at"])
    kyc_case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    kyc_case_model.objects.update_or_create(
        user_id=investor.pk,
        defaults={
            "subject_reference": f"user:{investor.pk}",
            "provider_environment": "test",
            "workflow_id": "test-workflow",
            "vendor_data": f"user:{investor.pk}",
            "status": "approved",
            "decision_at": now,
        },
    )


@pytest.mark.django_db
def test_portfolio_lifetime_interest_survives_holding_transfer(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    record_borrower_repayment(_repayment_command(admin_user, loan))
    _approve_financial_access(investor_one)

    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holding = holding_model.objects.get(loan=loan, investor_user_id=investor_one.pk)
    holding.status = "transferred"
    holding.current_principal_minor = 0
    holding.save(update_fields=["status", "current_principal_minor"])

    portal = import_module("backend.apps.investor_portal.services")
    payload = portal.get_investor_portfolio(actor=investor_one)

    # The holding was sold, so it leaves the active list — but lifetime
    # invested principal and received interest must keep counting it.
    assert payload["summary"]["active_holding_count"] == 0
    assert payload["summary"]["original_principal_by_currency"] == [
        {"currency": "CHF", "amount_minor": 10_000_00}
    ]
    assert payload["summary"]["realized_interest_by_currency"] == [
        {"currency": "CHF", "amount_minor": 100_00}
    ]


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
    repayment_emails = OutboxMessage.objects.filter(
        topic="email.repayment_distribution_credited"
    ).order_by("idempotency_key")
    assert repayment_emails.count() == 2
    assert {message.payload["user_id"] for message in repayment_emails} == {
        str(investor_one.pk),
        str(investor_two.pk),
    }
    assert all(
        "secondary_listing_repriced" not in message.payload["metadata"]
        for message in repayment_emails
    )
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
def test_repayment_email_aggregates_multiple_holdings_for_one_investor(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    second_holding = (
        apps.get_model("holdings", "InvestorLoanHolding")
        .objects.filter(loan=loan, investor_user_id=investor_two.pk)
        .get()
    )
    second_holding.investor_user_id = investor_one.pk
    second_holding.save(update_fields=["investor_user_id", "updated_at"])

    result = record_borrower_repayment(_repayment_command(admin_user, loan))

    repayment_emails = OutboxMessage.objects.filter(
        topic="email.repayment_distribution_credited"
    )
    assert repayment_emails.count() == 1
    repayment_email = repayment_emails.get()
    assert repayment_email.payload["user_id"] == str(investor_one.pk)
    assert repayment_email.payload["metadata"]["amount_minor"] == 3_300_00
    assert repayment_email.payload["metadata"]["principal_minor"] == 3_000_00
    assert repayment_email.payload["metadata"]["interest_minor"] == 300_00
    assert len(repayment_email.payload["metadata"]["holding_ids"]) == 2
    assert len(repayment_email.payload["metadata"]["balance_lot_ids"]) == 2
    assert result.repayment_event.amount_minor == 3_300_00


@pytest.mark.django_db
def test_regular_repayment_must_match_next_installment_amount(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    # Partial payments no longer exist on the regular path.
    with pytest.raises(ServicingValidationError, match="must equal the outstanding amount"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=1_000_00,
                idempotency_key="servicing-partial-rejected",
            )
        )
    # Overpayments no longer exist on the regular path either.
    with pytest.raises(ServicingValidationError, match="must equal the outstanding amount"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=3_301_00,
                idempotency_key="servicing-overpayment-rejected",
            )
        )

    assert BorrowerRepaymentEvent.objects.count() == 0


@pytest.mark.django_db
def test_funded_loan_rejects_repayment_until_borrower_disbursement(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    cast(Any, loan).status = "funded"
    loan.save(update_fields=["status", "updated_at"])

    with pytest.raises(ServicingValidationError, match="must be disbursed"):
        record_borrower_repayment(_repayment_command(admin_user, loan))

    assert not BorrowerRepaymentEvent.objects.filter(loan=loan).exists()


@pytest.mark.django_db
def test_regular_repayment_more_than_one_day_early_requires_acknowledgement(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    with pytest.raises(ServicingValidationError, match="more than one day before"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                booking_date=date(2026, 2, 26),
                value_date=date(2026, 2, 26),
                idempotency_key="servicing-early-regular-warning",
            )
        )

    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            booking_date=date(2026, 2, 26),
            value_date=date(2026, 2, 26),
            early_regular_payment_acknowledged=True,
            idempotency_key="servicing-early-regular-confirmed",
        )
    )

    assert result.repayment_event.interest_applied_minor == 300_00
    assert result.repayment_event.warning_acknowledged is True
    assert result.repayment_event.metadata["early_regular_payment_acknowledged"] is True


@pytest.mark.django_db
def test_repayment_in_advance_flag_and_bank_date_must_be_paired(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    with pytest.raises(ServicingValidationError, match="bank date is required"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=13_300_00,
                repayment_in_advance=True,
                idempotency_key="servicing-advance-missing-bank-date",
            )
        )
    with pytest.raises(ServicingValidationError, match="only used with repayment in advance"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=3_300_00,
                borrower_repayment_bank_date=date(2026, 3, 1),
                idempotency_key="servicing-bank-date-without-advance",
            )
        )

    assert BorrowerRepaymentEvent.objects.count() == 0


@pytest.mark.django_db
def test_repayment_in_advance_recalculates_future_schedule(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    # Bank date 2026-03-15 sits mid-period between the due dates 2026-02-28 and
    # 2026-03-31. Interest due until the bank date is the unpaid scheduled interest
    # of installment 1 (300_00) plus ACT/365 accrued interest on the outstanding
    # principal: 30_000_00 x 1000/10000 x 15/365 = 123_29 (ROUND_HALF_UP).
    # The amount covers that interest plus a 10_000_00 principal reduction.
    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=10_423_29,
            booking_date=date(2026, 3, 15),
            value_date=date(2026, 3, 15),
            repayment_in_advance=True,
            borrower_repayment_bank_date=date(2026, 3, 15),
            idempotency_key="servicing-advance-repayment",
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
    assert event.warning_acknowledged is True
    assert event.metadata["scheduled_interest_due_minor"] == 300_00
    assert event.metadata["accrued_interest_minor"] == 123_29
    assert event.metadata["interest_accrual_start_date"] == "2026-02-28"
    assert event.metadata["interest_accrual_end_date"] == "2026-03-15"
    assert event.metadata["accrued_interest_days"] == 15
    assert event.interest_applied_minor == 423_29
    assert event.principal_applied_minor == 3_000_00
    assert event.future_principal_applied_minor == 7_000_00
    assert event.expected_due_minor == 3_300_00
    assert event.remaining_installment_principal_minor == 0
    assert [(line.principal_minor, line.interest_minor, line.amount_minor) for line in lines] == [
        (3_333_33, 141_10, 3_474_43),
        (6_666_67, 282_19, 6_948_86),
    ]
    assert holdings[str(investor_one.pk)].current_principal_minor == 6_666_67
    assert holdings[str(investor_two.pk)].current_principal_minor == 13_333_33
    assert cast(Any, loan).status == "active"
    assert cast(Any, loan).schedule_version == 2
    assert cast(Any, loan).total_scheduled_principal_minor == 20_000_00
    assert cast(Any, loan).total_scheduled_interest_minor == 87_67
    # Only the future row survives, re-amortized over the reduced principal and
    # keeping the old due date and installment number. Its interest is prorated
    # for the remainder of the period: 20_000_00 x 1000/10000 x 16/365 = 87_67.
    assert [
        (
            row.installment_number,
            row.due_date,
            row.principal_minor,
            row.interest_minor,
            row.total_minor,
            row.admin_overridden,
        )
        for row in version_two_rows
    ] == [
        (2, date(2026, 3, 31), 20_000_00, 87_67, 20_087_67, False),
    ]
    assert DomainEvent.objects.filter(
        event_type="LoanScheduleRecalculated",
        aggregate_id=str(loan.pk),
    ).exists()
    full_schedule = get_loan_repayment_schedule_snapshots(
        loans=[loan],
        as_of_date=date(2026, 3, 15),
    )[str(loan.pk)]
    assert [row.row_type for row in full_schedule] == [
        "repayment_event",
        "scheduled_installment",
    ]
    assert full_schedule[0].label == "Repayment in advance"
    assert full_schedule[0].payment_date == date(2026, 3, 15)
    assert full_schedule[0].principal_minor == 10_000_00
    assert full_schedule[0].interest_minor == 423_29
    assert full_schedule[1].schedule_version == 2
    assert full_schedule[1].outstanding_principal_minor == 20_000_00
    assert sum(row.principal_minor for row in full_schedule) == 30_000_00


@pytest.mark.django_db
def test_second_same_day_advance_repayment_charges_no_future_interest(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    first = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=1_123_29,
            booking_date=date(2026, 2, 15),
            value_date=date(2026, 2, 15),
            repayment_in_advance=True,
            borrower_repayment_bank_date=date(2026, 2, 15),
            idempotency_key="servicing-same-day-advance-first",
        )
    )
    second = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=100_00,
            booking_date=date(2026, 2, 15),
            value_date=date(2026, 2, 15),
            repayment_in_advance=True,
            borrower_repayment_bank_date=date(2026, 2, 15),
            idempotency_key="servicing-same-day-advance-second",
        )
    )
    loan.refresh_from_db()

    assert first.repayment_event.metadata["accrued_interest_days"] == 15
    assert first.repayment_event.interest_applied_minor == 123_29
    assert second.repayment_event.metadata["interest_accrual_start_date"] == "2026-02-15"
    assert second.repayment_event.metadata["interest_accrual_end_date"] == "2026-02-15"
    assert second.repayment_event.metadata["accrued_interest_days"] == 0
    assert second.repayment_event.interest_applied_minor == 0
    assert second.repayment_event.principal_applied_minor == 100_00
    assert cast(Any, loan).schedule_version == 3
    assert sum(
        holding.current_principal_minor
        for holding in apps.get_model("holdings", "InvestorLoanHolding").objects.filter(
            loan=loan
        )
    ) == 28_900_00


@pytest.mark.django_db
def test_full_repayment_in_advance_marks_loan_repaid(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    # Interest until the bank date: scheduled 300_00 + accrued 123_29 (15/365 at
    # the 10% annual rate on 30_000_00); the remainder settles all principal.
    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=30_423_29,
            booking_date=date(2026, 3, 15),
            value_date=date(2026, 3, 15),
            repayment_in_advance=True,
            borrower_repayment_bank_date=date(2026, 3, 15),
            idempotency_key="servicing-full-advance-payoff",
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
    assert event.metadata["scheduled_interest_due_minor"] == 300_00
    assert event.metadata["accrued_interest_minor"] == 123_29
    assert event.interest_applied_minor == 423_29
    assert event.principal_applied_minor == 3_000_00
    assert event.future_principal_applied_minor == 27_000_00
    assert cast(Any, loan).status == "repaid"
    assert cast(Any, loan).schedule_version == 2
    # A full payoff regenerates an empty schedule version: no rows remain.
    assert version_two_rows == []
    assert cast(Any, loan).total_scheduled_principal_minor == 0
    assert cast(Any, loan).total_scheduled_interest_minor == 0
    assert {holding.current_principal_minor for holding in holdings} == {0}
    assert {holding.status for holding in holdings} == {"closed"}
    assert DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
        payload__new_status="repaid",
    ).exists()


@pytest.mark.django_db
def test_sequential_repayments_in_advance_create_consistent_schedule_versions(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_amortizing_loan_with_holdings(admin_user, investor_one, investor_two)

    # First declaration lands exactly on the first due date: interest due is only
    # the scheduled 300_00 of installment 1 (zero days accrued), and 8_000_00
    # reduces principal from 30_000_00 to 22_000_00.
    first = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=8_300_00,
            booking_date=date(2026, 2, 28),
            value_date=date(2026, 2, 28),
            repayment_in_advance=True,
            borrower_repayment_bank_date=date(2026, 2, 28),
            idempotency_key="servicing-first-sequential-advance",
        )
    )
    cast(Any, loan).refresh_from_db()
    version_two_rows = list(
        apps.get_model("loans", "LoanInstallment").objects.filter(
            loan=loan,
            schedule_version=2,
        ).order_by("installment_number")
    )
    # Second declaration lands on the due date of regenerated installment 2:
    # interest due is its scheduled 186_85, and 9_333_34 reduces principal from
    # 22_000_00 to 12_666_66.
    second = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=9_520_19,
            booking_date=date(2026, 4, 1),
            value_date=date(2026, 4, 1),
            repayment_in_advance=True,
            borrower_repayment_bank_date=date(2026, 3, 31),
            idempotency_key="servicing-second-sequential-advance",
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

    assert first.repayment_event.metadata["scheduled_interest_due_minor"] == 300_00
    assert first.repayment_event.metadata["accrued_interest_minor"] == 0
    assert first.repayment_event.interest_applied_minor == 300_00
    assert first.repayment_event.principal_applied_minor == 3_000_00
    assert first.repayment_event.future_principal_applied_minor == 5_000_00
    # Version 2 keeps the old future due dates and numbers, re-amortized over the
    # reduced 22_000_00 principal (equal-principal repayment type).
    assert [
        (
            row.installment_number,
            row.due_date,
            row.principal_minor,
            row.interest_minor,
            row.total_minor,
            row.admin_overridden,
        )
        for row in version_two_rows
    ] == [
        (2, date(2026, 3, 31), 7_333_34, 186_85, 7_520_19, False),
        (3, date(2026, 4, 30), 7_333_33, 122_22, 7_455_55, False),
        (4, date(2026, 5, 31), 7_333_33, 61_11, 7_394_44, False),
    ]
    assert second.repayment_event.installment.installment_number == 2
    assert second.repayment_event.installment.schedule_version == 2
    assert second.repayment_event.metadata["scheduled_interest_due_minor"] == 186_85
    assert second.repayment_event.metadata["accrued_interest_minor"] == 0
    assert second.repayment_event.interest_applied_minor == 186_85
    assert second.repayment_event.principal_applied_minor == 7_333_34
    assert second.repayment_event.future_principal_applied_minor == 2_000_00
    assert cast(Any, loan).schedule_version == 3
    assert cast(Any, loan).total_scheduled_principal_minor == 12_666_66
    # Regeneration preserves the due dates of the old future rows, so month-end
    # schedules do not drift.
    assert [
        (
            row.installment_number,
            row.due_date,
            row.principal_minor,
            row.interest_minor,
            row.total_minor,
            row.admin_overridden,
        )
        for row in version_three_rows
    ] == [
        (3, date(2026, 4, 30), 6_333_33, 104_11, 6_437_44, False),
        (4, date(2026, 5, 31), 6_333_33, 52_78, 6_386_11, False),
    ]
    assert sum(holding.current_principal_minor for holding in holdings) == 12_666_66
    assert cast(Any, loan).status == "active"
    assert DomainEvent.objects.filter(
        event_type="LoanScheduleRecalculated",
        aggregate_id=str(loan.pk),
    ).count() == 2


@pytest.mark.django_db
def test_preview_borrower_repayment_in_advance_returns_plan_without_writing(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    plan = preview_borrower_repayment_in_advance(
        PreviewAdvanceRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=10_423_29,
            borrower_repayment_bank_date=date(2026, 3, 15),
        )
    )

    assert plan.loan_id == str(loan.pk)
    assert plan.currency == "CHF"
    assert plan.amount_minor == 10_423_29
    assert plan.bank_date == date(2026, 3, 15)
    assert plan.scheduled_interest_due_minor == 300_00
    assert plan.interest_accrual_start_date == date(2026, 2, 28)
    assert plan.interest_accrual_end_date == date(2026, 3, 15)
    assert plan.accrued_interest_days == 15
    assert plan.accrued_interest_minor == 123_29
    assert plan.interest_applied_minor == 423_29
    assert plan.principal_applied_minor == 10_000_00
    assert plan.outstanding_principal_before_minor == 30_000_00
    assert plan.outstanding_principal_after_minor == 20_000_00
    assert plan.anchor_installment_number == 1
    assert [
        (row.installment_number, row.due_date, row.principal_minor, row.interest_minor)
        for row in plan.old_schedule_rows
    ] == [
        (1, date(2026, 2, 28), 3_000_00, 300_00),
        (2, date(2026, 3, 31), 27_000_00, 200_00),
    ]
    assert [
        (
            row.installment_number,
            row.due_date,
            row.principal_minor,
            row.interest_minor,
            row.total_minor,
        )
        for row in plan.new_schedule_rows
    ] == [
        (2, date(2026, 3, 31), 20_000_00, 87_67, 20_087_67),
    ]

    # The preview is a dry run: nothing is recorded and the schedule stays put.
    loan.refresh_from_db()
    assert cast(Any, loan).schedule_version == 1
    assert not BorrowerRepaymentEvent.objects.exists()
    assert not apps.get_model("loans", "LoanInstallment").objects.filter(
        loan=loan,
        schedule_version=2,
    ).exists()
    holdings = apps.get_model("holdings", "InvestorLoanHolding").objects.filter(loan=loan)
    assert {holding.current_principal_minor for holding in holdings} == {
        10_000_00,
        20_000_00,
    }


@pytest.mark.django_db
def test_late_loan_can_declare_repayment_in_advance(
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
    loan.refresh_from_db()
    assert cast(Any, loan).status == "late"

    # Interest due until the bank date: scheduled 300_00 of the overdue
    # installment plus 30_000_00 x 1000/10000 x 5/365 = 41_10 accrued.
    with pytest.raises(ServicingValidationError, match="cover all interest due"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=300_00,
                booking_date=date(2026, 3, 5),
                value_date=date(2026, 3, 5),
                repayment_in_advance=True,
                borrower_repayment_bank_date=date(2026, 3, 5),
                idempotency_key="servicing-late-advance-too-small",
            )
        )

    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=5_341_10,
            booking_date=date(2026, 3, 5),
            value_date=date(2026, 3, 5),
            repayment_in_advance=True,
            borrower_repayment_bank_date=date(2026, 3, 5),
            idempotency_key="servicing-late-advance",
        )
    )
    event = result.repayment_event
    loan.refresh_from_db()
    version_two_rows = list(
        apps.get_model("loans", "LoanInstallment").objects.filter(
            loan=loan,
            schedule_version=2,
        ).order_by("installment_number")
    )

    assert event.event_type == BorrowerRepaymentEventType.EARLY_REPAYMENT
    assert event.metadata["scheduled_interest_due_minor"] == 300_00
    assert event.metadata["accrued_interest_minor"] == 41_10
    assert event.interest_applied_minor == 341_10
    assert event.principal_applied_minor == 3_000_00
    assert event.future_principal_applied_minor == 2_000_00
    # The arrears are settled, so the loan returns to active on the new schedule.
    assert cast(Any, loan).status == "active"
    assert cast(Any, loan).schedule_version == 2
    assert [
        (row.installment_number, row.due_date, row.principal_minor, row.interest_minor)
        for row in version_two_rows
    ] == [
        (2, date(2026, 3, 31), 25_000_00, 178_08),
    ]
    assert DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
        payload__new_status="active",
    ).exists()


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
                amount_minor=27_200_00,
            )
        )
    with pytest.raises(ServicingValidationError, match="different repayment request"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                repayment_in_advance=True,
                borrower_repayment_bank_date=date(2026, 3, 1),
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
            booking_date=date(2026, 3, 31),
            value_date=date(2026, 3, 31),
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
            booking_date=date(2026, 3, 31),
            value_date=date(2026, 3, 31),
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
    assert result.changes[0].previous_status == "active"
    assert result.changes[0].new_status == "late"
    assert result.changes[0].days_past_due == 5
    assert result.changes[0].outstanding_minor == 3_300_00
    assert DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
    ).exists()


@pytest.mark.django_db
def test_servicing_status_snapshot_reports_days_past_due_without_mutating_loan(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    snapshot = get_loan_servicing_status_snapshot(
        loan=loan,
        as_of_date=date(2026, 3, 5),
    )
    loan.refresh_from_db()

    assert snapshot.loan_id == str(loan.pk)
    assert snapshot.status == "late"
    assert snapshot.days_past_due == 5
    assert snapshot.outstanding_minor == 3_300_00
    assert snapshot.triggering_due_date == date(2026, 2, 28)
    assert cast(Any, loan).status == "active"
    assert not DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
    ).exists()


@pytest.mark.django_db
def test_refinancing_loan_servicing_schedule_starts_at_installment_one(
    admin_user: Model,
    investor_one: Model,
) -> None:
    # A refinancing loan's servicing schedule is generated from the financeable
    # principal and always starts at installment 1. The original loan's paid
    # installments live only in the informational original schedule and never
    # appear in servicing.
    currency = Currency.objects.get(code="CHF")
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    borrower = borrower_model.objects.create(
        legal_name="Refinancing Servicing Borrower AG",
        year_founded=2018,
        kyb_status="approved",
        compliance_hold=False,
        country="Switzerland",
        created_by_admin_id=admin_user.pk,
    )
    today = timezone.localdate()
    loans = import_module("backend.apps.loans.services")
    loan = loans.create_loan(
        loans.CreateLoanCommand(
            actor=admin_user,
            borrower_id=str(borrower.pk),
            title="Refinanced working capital loan",
            investor_summary="Refinancing of an ongoing loan.",
            purpose="working_capital",
            principal_minor=1_100_00,
            currency="CHF",
            interest_rate_bps=1_000,
            term_months=2,
            repayment_type="equal_installments",
            collateral_type="real_estate",
            collateral_value_minor=3_000_00,
            risk_rating="BBB",
            is_refinancing=True,
            original_principal_minor=1_500_00,
            original_interest_rate_bps=1_200,
            original_term_months=12,
            original_repayment_type="equal_installments",
            original_interest_only_months=0,
            original_loan_start_date=today - timedelta(days=400),
        )
    )
    installments = list(
        apps.get_model("loans", "LoanInstallment").objects.filter(
            loan=loan,
            schedule_version=1,
        ).order_by("installment_number")
    )

    # The servicing schedule covers only the financeable principal and contains
    # no pre-paid rows from the original loan.
    assert [row.installment_number for row in installments] == [1, 2]
    assert sum(row.principal_minor for row in installments) == 1_100_00
    assert cast(Any, loan).is_refinancing is True
    assert cast(Any, loan).original_principal_minor == 1_500_00
    assert cast(Any, loan).pre_publication_paid_installments == []

    cast(Any, loan).status = "active"
    loan.save(update_fields=["status", "updated_at"])
    apps.get_model("holdings", "InvestorLoanHolding").objects.create(
        loan=loan,
        investor_user_id=investor_one.pk,
        source_type="primary_market",
        source_id="servicing-refinancing-order-1",
        status="active",
        original_principal_minor=1_100_00,
        current_principal_minor=1_100_00,
        currency=currency,
        loan_share_ppm=1_000_000,
        assignment_effective_at=timezone.now(),
        created_by_admin_id=admin_user.pk,
        idempotency_key="servicing-refinancing-holding-1",
    )

    first_installment = installments[0]
    result = record_borrower_repayment(
        _repayment_command(
            admin_user,
            loan,
            amount_minor=int(first_installment.total_minor),
            booking_date=today,
            value_date=today,
            early_regular_payment_acknowledged=True,
            idempotency_key="servicing-refinancing-repayment-1",
        )
    )
    event = result.repayment_event

    # The first regular repayment applies to installment 1 of the loan's own
    # (financeable-principal) schedule.
    assert event.event_type == BorrowerRepaymentEventType.REGULAR_INSTALLMENT
    assert event.installment.installment_number == 1
    assert event.installment.schedule_version == 1
    assert event.principal_applied_minor == int(first_installment.principal_minor)
    assert event.interest_applied_minor == int(first_installment.interest_minor)


@pytest.mark.django_db
def test_late_loan_returns_to_active_after_catchup_repayment(
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

    assert cast(Any, loan).status == "active"
    assert result.repayment_event.metadata["installment_number"] == 1
    assert DomainEvent.objects.filter(
        event_type="LoanServicingStatusChanged",
        aggregate_id=str(loan.pk),
        payload__new_status="active",
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
    # Repayment in advance is also rejected for defaulted loans.
    with pytest.raises(ServicingValidationError, match="recovery workflow"):
        record_borrower_repayment(
            _repayment_command(
                admin_user,
                loan,
                amount_minor=30_423_29,
                booking_date=date(2026, 3, 16),
                value_date=date(2026, 3, 16),
                repayment_in_advance=True,
                borrower_repayment_bank_date=date(2026, 3, 16),
                idempotency_key="servicing-defaulted-advance",
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
    PlatformSetting.objects.create(
        key="payments.deposit_instructions_by_currency",
        value={"CHF": {"collection_account_identifier": "Garanta_CHF"}},
    )
    client.force_login(cast(Any, admin_user))

    repayment_request = {
        "loan_id": str(loan.pk),
        "amount_minor": 3_300_00,
        "booking_date": "2026-03-01",
        "value_date": "2026-03-01",
        "payer_name": "Servicing Borrower AG",
        "payer_account_identifier": "CH22BORROWER",
        "bank_reference": "BANK-SERVICING-API",
        "payment_reference": f"LOAN-{loan.pk}",
        "evidence_reference": "statement:servicing-api",
        "idempotency_key": "servicing-api",
    }
    response = client.post(
        "/api/v1/servicing/admin/borrower-repayments/",
        data=repayment_request,
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["repayment_event"]["event_type"] == "regular_installment"
    assert payload["repayment_event"]["amount_minor"] == 3_300_00
    assert payload["repayment_event"]["warning_acknowledged"] is False
    assert len(payload["distribution_lines"]) == 2
    repayment_event = BorrowerRepaymentEvent.objects.get(
        id=payload["repayment_event"]["id"]
    )
    assert repayment_event.bank_operation.collection_account_identifier == "Garanta_CHF"

    # Server-derived configuration is not part of caller intent. A retry remains
    # idempotent even if the configured collector changes after the first post.
    PlatformSetting.objects.filter(
        key="payments.deposit_instructions_by_currency"
    ).update(value={"CHF": {"collection_account_identifier": "Garanta_CHF_NEW"}})
    replay_response = client.post(
        "/api/v1/servicing/admin/borrower-repayments/",
        data=repayment_request,
        content_type="application/json",
    )
    assert replay_response.status_code == 201
    assert replay_response.json()["repayment_event"]["id"] == payload["repayment_event"]["id"]
    assert (
        BorrowerRepaymentEvent.objects.filter(idempotency_key="servicing-api").count()
        == 1
    )

    schedule_response = client.get(f"/api/v1/loans/admin/loans/{loan.pk}/schedule/")
    assert schedule_response.status_code == 200
    schedule_payload = schedule_response.json()
    assert schedule_payload[0]["installment_number"] == 1
    assert schedule_payload[0]["is_paid"] is True
    assert schedule_payload[0]["paid_principal_minor"] == 3_000_00
    assert schedule_payload[0]["paid_interest_minor"] == 300_00
    assert schedule_payload[0]["outstanding_total_minor"] == 0
    assert schedule_payload[1]["installment_number"] == 2
    assert schedule_payload[1]["is_paid"] is False
    assert schedule_payload[1]["outstanding_total_minor"] == 27_200_00

    # A non-matching amount without the repayment-in-advance flag is rejected.
    mismatch_response = client.post(
        "/api/v1/servicing/admin/borrower-repayments/",
        data={
            "loan_id": str(loan.pk),
            "amount_minor": 1_000_00,
            "booking_date": "2026-03-01",
            "value_date": "2026-03-01",
            "collection_account_identifier": "CH00GARANTALEDGER",
            "payer_name": "Servicing Borrower AG",
            "idempotency_key": "servicing-api-mismatch",
        },
        content_type="application/json",
    )
    assert mismatch_response.status_code == 400
    assert "must equal the outstanding amount" in mismatch_response.json()["detail"]

    # The remaining principal (27_000_00) plus accrued interest until the bank
    # date (27_000_00 x 1000/10000 x 15/365 = 110_96) settles the loan early.
    advance_response = client.post(
        "/api/v1/servicing/admin/borrower-repayments/",
        data={
            "loan_id": str(loan.pk),
            "amount_minor": 27_110_96,
            "booking_date": "2026-03-15",
            "value_date": "2026-03-15",
            "collection_account_identifier": "CH00GARANTALEDGER",
            "payer_name": "Servicing Borrower AG",
            "payer_account_identifier": "CH22BORROWER",
            "bank_reference": "BANK-SERVICING-API-ADVANCE",
            "payment_reference": f"LOAN-{loan.pk}",
            "evidence_reference": "statement:servicing-api-advance",
            "repayment_in_advance": True,
            "borrower_repayment_bank_date": "2026-03-15",
            "idempotency_key": "servicing-api-advance",
        },
        content_type="application/json",
    )
    loan.refresh_from_db()

    assert advance_response.status_code == 201
    advance_payload = advance_response.json()
    assert advance_payload["repayment_event"]["event_type"] == "early_repayment"
    assert advance_payload["repayment_event"]["amount_minor"] == 27_110_96
    assert advance_payload["repayment_event"]["interest_applied_minor"] == 110_96
    assert advance_payload["repayment_event"]["warning_acknowledged"] is True
    assert cast(Any, loan).status == "repaid"
    assert cast(Any, loan).schedule_version == 2


@pytest.mark.django_db
def test_advance_preview_admin_api(
    client: Client,
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    client.force_login(cast(Any, admin_user))

    response = client.post(
        "/api/v1/servicing/admin/borrower-repayments/advance-preview/",
        data={
            "loan_id": str(loan.pk),
            "amount_minor": 10_423_29,
            "borrower_repayment_bank_date": "2026-03-15",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["loan_id"] == str(loan.pk)
    assert payload["currency"] == "CHF"
    assert payload["amount_minor"] == 10_423_29
    assert payload["bank_date"] == "2026-03-15"
    assert payload["scheduled_interest_due_minor"] == 300_00
    assert payload["interest_accrual_start_date"] == "2026-02-28"
    assert payload["interest_accrual_end_date"] == "2026-03-15"
    assert payload["accrued_interest_days"] == 15
    assert payload["accrued_interest_minor"] == 123_29
    assert payload["interest_applied_minor"] == 423_29
    assert payload["principal_applied_minor"] == 10_000_00
    assert payload["outstanding_principal_before_minor"] == 30_000_00
    assert payload["outstanding_principal_after_minor"] == 20_000_00
    assert payload["anchor_installment_number"] == 1
    assert [
        (row["installment_number"], row["due_date"], row["total_minor"])
        for row in payload["old_schedule_rows"]
    ] == [
        (1, "2026-02-28", 3_300_00),
        (2, "2026-03-31", 27_200_00),
    ]
    assert payload["new_schedule_rows"] == [
        {
            "installment_number": 2,
            "due_date": "2026-03-31",
            "principal_minor": 20_000_00,
            "interest_minor": 87_67,
            "total_minor": 20_087_67,
        }
    ]

    # The preview endpoint writes nothing.
    loan.refresh_from_db()
    assert cast(Any, loan).schedule_version == 1
    assert not BorrowerRepaymentEvent.objects.exists()

    validation_response = client.post(
        "/api/v1/servicing/admin/borrower-repayments/advance-preview/",
        data={
            "loan_id": str(loan.pk),
            "amount_minor": 100_00,
            "borrower_repayment_bank_date": "2026-03-15",
        },
        content_type="application/json",
    )
    assert validation_response.status_code == 400
    assert "cover all interest due" in validation_response.json()["detail"]


@pytest.mark.django_db
def test_admin_adds_internal_and_public_risk_notes_with_investor_visibility(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    _approve_financial_access(investor_one)
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    internal_note = add_loan_risk_note(
        AddLoanRiskNoteCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            visibility="internal",
            note_type="internal_note",
            title="Internal follow-up",
            body="Borrower called operations and requested a callback.",
            evidence_reference="drive://internal-note",
            idempotency_key="servicing-risk-note-internal",
        )
    )
    public_note = add_loan_risk_note(
        AddLoanRiskNoteCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            visibility="public",
            note_type="public_update",
            title="Payment update",
            body="Garanta is following up with the borrower regarding the late payment.",
            idempotency_key="servicing-risk-note-public",
        )
    )

    replay = add_loan_risk_note(
        AddLoanRiskNoteCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            visibility="public",
            note_type="public_update",
            title="Payment update",
            body="Garanta is following up with the borrower regarding the late payment.",
            idempotency_key="servicing-risk-note-public",
        )
    )
    assert replay.id == public_note.id

    notes = list_public_loan_risk_notes(actor=investor_one, loan_id=str(loan.pk))
    assert [note.id for note in notes] == [public_note.id]
    assert internal_note.id not in {note.id for note in notes}
    investor_one_holding = apps.get_model("holdings", "InvestorLoanHolding").objects.get(
        loan=loan,
        investor_user_id=investor_one.pk,
    )
    investor_one_holding.status = "transferred"
    investor_one_holding.current_principal_minor = 0
    investor_one_holding.save(update_fields=["status", "current_principal_minor"])
    historical_notes = list_public_loan_risk_notes(actor=investor_one, loan_id=str(loan.pk))
    assert [note.id for note in historical_notes] == [public_note.id]
    assert DomainEvent.objects.filter(event_type="LoanRiskNoteAdded").count() == 2
    assert AuditEvent.objects.filter(action="servicing.loan_risk_note_added").count() == 2

    user_model: Any = get_user_model()
    unrelated_investor = cast(
        Model,
        user_model.objects.create_user(
            email="servicing-unrelated@example.test",
            full_name="Servicing Unrelated",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )
    _approve_financial_access(unrelated_investor)
    with pytest.raises(ServicingValidationError, match="different risk-note"):
        add_loan_risk_note(
            AddLoanRiskNoteCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                visibility="public",
                note_type="public_update",
                title="Changed title",
                body="Garanta is following up with the borrower regarding the late payment.",
                idempotency_key="servicing-risk-note-public",
            )
        )
    with pytest.raises(ServicingAuthorizationError, match="Investor can only view"):
        list_public_loan_risk_notes(actor=unrelated_investor, loan_id=str(loan.pk))


@pytest.mark.django_db
def test_risk_note_api_redacts_public_response(
    client: Client,
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    _approve_financial_access(investor_one)
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    client.force_login(cast(Any, admin_user))

    create_response = client.post(
        "/api/v1/servicing/admin/risk-notes/",
        data={
            "loan_id": str(loan.pk),
            "visibility": "public",
            "note_type": "public_update",
            "title": "Payment update",
            "body": "Garanta is following up with the borrower.",
            "evidence_reference": "statement:private",
            "metadata": {"internal_case": "RISK-1"},
            "idempotency_key": "servicing-risk-note-api",
        },
        content_type="application/json",
    )
    assert create_response.status_code == 201
    assert create_response.json()["evidence_reference"] == "statement:private"

    client.force_login(cast(Any, investor_one))
    public_response = client.get(
        f"/api/v1/servicing/loan-risk-notes/?loan_id={loan.pk}",
    )

    assert public_response.status_code == 200
    public_note = public_response.json()[0]
    assert public_note["title"] == "Payment update"
    private_fields = {
        "borrower_id",
        "evidence_reference",
        "created_by_admin_id",
        "metadata",
        "idempotency_key",
        "created_at",
        "updated_at",
    }
    assert private_fields.isdisjoint(public_note)


@pytest.mark.django_db
def test_record_recovery_payment_distributes_net_recovery_and_updates_holdings(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )

    result = record_loan_recovery_payment(
        RecordLoanRecoveryPaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            gross_recovered_minor=10_000_00,
            externally_deducted_costs_minor=1_000_00,
            third_party_costs_from_received_minor=500_00,
            recovery_fee_applied=True,
            recovery_fee_bps=1000,
            principal_recovered_minor=6_000_00,
            contractual_interest_recovered_minor=1_000_00,
            default_interest_recovered_minor=500_00,
            penalties_recovered_minor=100_00,
            other_costs_recovered_minor=50_00,
            booking_date=date(2026, 3, 20),
            value_date=date(2026, 3, 20),
            collection_account_identifier="CH00GARANTARECOVERY",
            payer_name="Recovery counsel",
            payer_account_identifier="CH0000000000000000009",
            bank_reference="REC-2026-001",
            payment_reference="LOAN-RECOVERY",
            evidence_reference="recovery-pack-1",
            notes="Partial recovery after enforcement.",
            idempotency_key="servicing-recovery-1",
        )
    )

    event = result.recovery_event
    assert event.gross_recovered_minor == 10_000_00
    assert event.externally_deducted_costs_minor == 1_000_00
    assert event.net_received_minor == 9_000_00
    assert event.third_party_costs_from_received_minor == 500_00
    assert event.recovery_fee_base_minor == 8_500_00
    assert event.recovery_fee_minor == 850_00
    assert event.net_available_for_distribution_minor == 7_650_00
    assert event.rounding_difference_minor == 0
    assert event.recovery_waterfall_config["allocation_method"] == (
        "pro_rata_by_current_principal"
    )

    lines = {str(line.investor_user_id): line for line in result.distribution_lines}
    investor_one_line = lines[str(investor_one.pk)]
    investor_two_line = lines[str(investor_two.pk)]
    assert investor_one_line.amount_minor == 2_550_00
    assert investor_two_line.amount_minor == 5_100_00
    assert investor_one_line.principal_minor == 2_000_00
    assert investor_two_line.principal_minor == 4_000_00
    assert investor_one_line.contractual_interest_minor == 333_33
    assert investor_two_line.contractual_interest_minor == 666_67
    assert investor_one_line.default_interest_minor == 166_67
    assert investor_two_line.default_interest_minor == 333_33
    assert investor_one_line.penalties_minor == 33_33
    assert investor_two_line.penalties_minor == 66_67
    assert investor_one_line.other_costs_minor == 16_67
    assert investor_two_line.other_costs_minor == 33_33
    assert {line.balance_lot.source_type for line in lines.values()} == {
        "recovery_distribution"
    }
    assert {line.balance_lot.available_amount_minor for line in lines.values()} == {
        2_550_00,
        5_100_00,
    }
    recovery_emails = OutboxMessage.objects.filter(
        topic="email.recovery_distribution_credited"
    ).order_by("idempotency_key")
    assert recovery_emails.count() == 2
    assert {message.payload["user_id"] for message in recovery_emails} == {
        str(investor_one.pk),
        str(investor_two.pk),
    }

    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holdings = {
        str(holding.investor_user_id): holding
        for holding in holding_model.objects.filter(loan=loan).order_by("investor_user_id")
    }
    assert holdings[str(investor_one.pk)].current_principal_minor == 8_000_00
    assert holdings[str(investor_two.pk)].current_principal_minor == 16_000_00

    postings = {
        (
            posting.account.account_type,
            posting.account.owner_type,
            posting.side,
            posting.amount_minor,
        )
        for posting in event.journal_entry.postings.select_related("account")
    }
    assert ("collection_cash", "", "debit", 9_000_00) in postings
    assert ("platform_fee_revenue", "garanta", "credit", 850_00) in postings
    assert ("recovery_distribution_payable", "loan", "credit", 500_00) in postings

    ledger = import_module("backend.apps.ledger.services")
    snapshot = ledger.create_reconciliation_snapshot(
        ledger.CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 3, 20),
            bank_stated_balance_minor=9_000_00,
        )
    )
    assert snapshot.reconciliation_difference_minor == 0
    assert snapshot.garanta_accrued_revenue_minor == 850_00
    assert snapshot.metadata["platform_fee_revenue_minor"] == 850_00
    assert snapshot.metadata["recovery_distribution_payable_minor"] == 500_00
    assert AuditEvent.objects.filter(action="servicing.loan_recovery_recorded").exists()
    assert DomainEvent.objects.filter(event_type="LoanRecoveryRecorded").exists()
    assert DomainEvent.objects.filter(event_type="LoanRecoveryDistributed").exists()

    replay = record_loan_recovery_payment(
        RecordLoanRecoveryPaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            gross_recovered_minor=10_000_00,
            externally_deducted_costs_minor=1_000_00,
            third_party_costs_from_received_minor=500_00,
            recovery_fee_applied=True,
            recovery_fee_bps=1000,
            principal_recovered_minor=6_000_00,
            contractual_interest_recovered_minor=1_000_00,
            default_interest_recovered_minor=500_00,
            penalties_recovered_minor=100_00,
            other_costs_recovered_minor=50_00,
            booking_date=date(2026, 3, 20),
            value_date=date(2026, 3, 20),
            collection_account_identifier="CH00GARANTARECOVERY",
            payer_name="Recovery counsel",
            payer_account_identifier="CH0000000000000000009",
            bank_reference="REC-2026-001",
            payment_reference="LOAN-RECOVERY",
            evidence_reference="recovery-pack-1",
            notes="Partial recovery after enforcement.",
            idempotency_key="servicing-recovery-1",
        )
    )
    assert replay.recovery_event.id == event.id


@pytest.mark.django_db
def test_recovery_payment_requires_defaulted_loan_and_reconciled_category_split(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    with pytest.raises(ServicingValidationError, match="before final loss recognition"):
        record_loan_recovery_payment(
            RecordLoanRecoveryPaymentCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                gross_recovered_minor=1_000_00,
                externally_deducted_costs_minor=0,
                third_party_costs_from_received_minor=0,
                recovery_fee_applied=False,
                recovery_fee_bps=0,
                principal_recovered_minor=1_000_00,
                contractual_interest_recovered_minor=0,
                default_interest_recovered_minor=0,
                penalties_recovered_minor=0,
                other_costs_recovered_minor=0,
                booking_date=date(2026, 3, 20),
                value_date=date(2026, 3, 20),
                collection_account_identifier="CH00GARANTARECOVERY",
                payer_name="Recovery counsel",
                idempotency_key="servicing-recovery-funded",
            )
        )

    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )
    with pytest.raises(ServicingValidationError, match="category split"):
        record_loan_recovery_payment(
            RecordLoanRecoveryPaymentCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                gross_recovered_minor=1_000_00,
                externally_deducted_costs_minor=0,
                third_party_costs_from_received_minor=0,
                recovery_fee_applied=False,
                recovery_fee_bps=0,
                principal_recovered_minor=900_00,
                contractual_interest_recovered_minor=0,
                default_interest_recovered_minor=0,
                penalties_recovered_minor=0,
                other_costs_recovered_minor=0,
                booking_date=date(2026, 3, 20),
                value_date=date(2026, 3, 20),
                collection_account_identifier="CH00GARANTARECOVERY",
                payer_name="Recovery counsel",
                idempotency_key="servicing-recovery-mismatch",
            )
        )


@pytest.mark.django_db
def test_recovery_payment_admin_api(
    client: Client,
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )
    client.force_login(cast(Any, admin_user))

    response = client.post(
        "/api/v1/servicing/admin/recoveries/",
        data={
            "loan_id": str(loan.pk),
            "gross_recovered_minor": 3_000_00,
            "externally_deducted_costs_minor": 0,
            "third_party_costs_from_received_minor": 0,
            "recovery_fee_applied": False,
            "recovery_fee_bps": 0,
            "principal_recovered_minor": 3_000_00,
            "contractual_interest_recovered_minor": 0,
            "default_interest_recovered_minor": 0,
            "penalties_recovered_minor": 0,
            "other_costs_recovered_minor": 0,
            "booking_date": "2026-03-20",
            "value_date": "2026-03-20",
            "collection_account_identifier": "CH00GARANTARECOVERY",
            "payer_name": "Recovery counsel",
            "idempotency_key": "servicing-recovery-api",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["recovery_event"]["loan_id"] == str(loan.pk)
    assert payload["recovery_event"]["net_available_for_distribution_minor"] == 3_000_00
    assert sum(line["principal_minor"] for line in payload["distribution_lines"]) == 3_000_00


@pytest.mark.django_db
def test_record_write_off_changes_defaulted_loan_to_written_off_and_is_idempotent(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )

    write_off = record_loan_write_off(
        RecordLoanWriteOffCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            written_off_principal_minor=30_000_00,
            written_off_contractual_interest_minor=500_00,
            written_off_default_interest_minor=125_00,
            written_off_fees_minor=25_00,
            written_off_penalties_minor=50_00,
            reason="Recovery exhausted after legal review.",
            notes="Evidence retained offline.",
            evidence_reference="writeoff-pack-1",
            idempotency_key="servicing-write-off-1",
        )
    )
    loan.refresh_from_db()

    assert cast(Any, loan).status == "written_off"
    assert write_off.total_written_off_minor == 30_700_00
    assert write_off.previous_loan_status == "defaulted"
    assert write_off.new_loan_status == "written_off"
    assert write_off.currency_id == "CHF"
    loss_lines = list(write_off.loss_recognition_lines.order_by("investor_user_id"))
    assert len(loss_lines) == 2
    assert sum(line.principal_loss_minor for line in loss_lines) == 30_000_00
    assert sum(line.contractual_interest_loss_minor for line in loss_lines) == 500_00
    assert sum(line.default_interest_loss_minor for line in loss_lines) == 125_00
    assert sum(line.fees_loss_minor for line in loss_lines) == 25_00
    assert sum(line.penalties_loss_minor for line in loss_lines) == 50_00
    assert sum(line.total_loss_minor for line in loss_lines) == 30_700_00
    assert {
        line.current_principal_before_minor
        for line in loss_lines
    } == {10_000_00, 20_000_00}
    assert {line.current_principal_after_minor for line in loss_lines} == {0}

    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holdings = {
        str(holding.investor_user_id): holding
        for holding in holding_model.objects.filter(loan=loan)
    }
    assert holdings[str(investor_one.pk)].current_principal_minor == 0
    assert holdings[str(investor_two.pk)].current_principal_minor == 0
    assert {holding.status for holding in holdings.values()} == {"closed"}
    assert apps.get_model("loans", "LoanEvent").objects.filter(
        loan=loan,
        event_type="write_off_recorded",
        previous_status="defaulted",
        new_status="written_off",
    ).exists()
    assert AuditEvent.objects.filter(action="servicing.loan_write_off_recorded").exists()
    assert DomainEvent.objects.filter(event_type="LoanWriteOffRecorded").exists()
    assert DomainEvent.objects.filter(event_type="LoanLossRecognized").exists()

    replay = record_loan_write_off(
        RecordLoanWriteOffCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            written_off_principal_minor=30_000_00,
            written_off_contractual_interest_minor=500_00,
            written_off_default_interest_minor=125_00,
            written_off_fees_minor=25_00,
            written_off_penalties_minor=50_00,
            reason="Recovery exhausted after legal review.",
            notes="Evidence retained offline.",
            evidence_reference="writeoff-pack-1",
            idempotency_key="servicing-write-off-1",
        )
    )
    assert replay.id == write_off.id

    with pytest.raises(ServicingValidationError, match="different write-off"):
        record_loan_write_off(
            RecordLoanWriteOffCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                written_off_principal_minor=29_000_00,
                reason="Changed.",
                idempotency_key="servicing-write-off-1",
            )
        )
    with pytest.raises(ServicingValidationError, match="before final loss recognition"):
        record_loan_recovery_payment(
            RecordLoanRecoveryPaymentCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                gross_recovered_minor=1_000_00,
                externally_deducted_costs_minor=0,
                third_party_costs_from_received_minor=0,
                recovery_fee_applied=False,
                recovery_fee_bps=0,
                principal_recovered_minor=1_000_00,
                contractual_interest_recovered_minor=0,
                default_interest_recovered_minor=0,
                penalties_recovered_minor=0,
                other_costs_recovered_minor=0,
                booking_date=date(2026, 3, 20),
                value_date=date(2026, 3, 20),
                collection_account_identifier="CH00GARANTARECOVERY",
                payer_name="Recovery counsel",
                idempotency_key="servicing-recovery-after-write-off",
            )
        )


@pytest.mark.django_db
def test_write_off_requires_defaulted_loan_and_positive_total(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)

    with pytest.raises(ServicingValidationError, match="Total written-off amount"):
        record_loan_write_off(
            RecordLoanWriteOffCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                written_off_principal_minor=0,
                reason="Zero total is invalid.",
                idempotency_key="servicing-write-off-zero",
            )
        )
    with pytest.raises(ServicingValidationError, match="Only defaulted"):
        record_loan_write_off(
            RecordLoanWriteOffCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                written_off_principal_minor=1_000_00,
                reason="Not defaulted.",
                idempotency_key="servicing-write-off-funded",
            )
        )

    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )
    with pytest.raises(ServicingValidationError, match="remaining active holding principal"):
        record_loan_write_off(
            RecordLoanWriteOffCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                written_off_principal_minor=29_000_00,
                reason="Partial principal loss is not final recognition.",
                idempotency_key="servicing-write-off-partial-principal",
            )
        )


@pytest.mark.django_db
def test_write_off_admin_api_records_loss_recognition(
    client: Client,
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )
    client.force_login(cast(Any, admin_user))

    response = client.post(
        "/api/v1/servicing/admin/write-offs/",
        data={
            "loan_id": str(loan.pk),
            "written_off_principal_minor": 30_000_00,
            "written_off_contractual_interest_minor": 500_00,
            "reason": "Recovery exhausted.",
            "notes": "Legal evidence retained.",
            "evidence_reference": "writeoff-api-pack",
            "idempotency_key": "servicing-write-off-api",
        },
        content_type="application/json",
    )
    loan.refresh_from_db()

    assert response.status_code == 201
    payload = response.json()
    assert payload["write_off_event"]["loan_id"] == str(loan.pk)
    assert payload["write_off_event"]["currency"] == "CHF"
    assert payload["write_off_event"]["total_written_off_minor"] == 30_500_00
    assert len(payload["loss_recognition_lines"]) == 2
    assert sum(
        line["principal_loss_minor"] for line in payload["loss_recognition_lines"]
    ) == 30_000_00
    assert cast(Any, loan).status == "written_off"


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


@pytest.mark.django_db
def test_risk_note_and_write_off_records_have_app_and_db_guards(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    note = add_loan_risk_note(
        AddLoanRiskNoteCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            visibility="internal",
            note_type="internal_note",
            title="Internal note",
            body="Internal note body.",
            idempotency_key="servicing-append-risk-note",
        )
    )
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )
    write_off = record_loan_write_off(
        RecordLoanWriteOffCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            written_off_principal_minor=30_000_00,
            reason="Write-off append-only test.",
            idempotency_key="servicing-append-write-off",
        )
    )
    loss_line = InvestorLossRecognitionLine.objects.filter(write_off_event=write_off).first()
    assert loss_line is not None

    with pytest.raises(AppendOnlyViolation):
        note.body = "mutated"
        note.save()
    with pytest.raises(AppendOnlyViolation):
        write_off.reason = "mutated"
        write_off.save()
    with pytest.raises(AppendOnlyViolation):
        loss_line.metadata = {"mutated": True}
        loss_line.save()
    with pytest.raises(AppendOnlyViolation):
        LoanRiskNote.objects.filter(id=note.id).update(body="mutated")
    with pytest.raises(AppendOnlyViolation):
        LoanWriteOffEvent.objects.filter(id=write_off.id).update(reason="mutated")
    with pytest.raises(AppendOnlyViolation):
        InvestorLossRecognitionLine.objects.filter(id=loss_line.id).update(
            metadata={"mutated": True}
        )

    with pytest.raises(DatabaseError) as update_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE servicing_loanrisknote SET body = %s WHERE id = %s",
                ["mutated", note.id.hex],
            )
    assert "append-only" in str(update_error.value)

    with pytest.raises(DatabaseError) as delete_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM servicing_loanwriteoffevent WHERE id = %s",
                [write_off.id.hex],
            )
    assert "append-only" in str(delete_error.value)

    with pytest.raises(DatabaseError) as loss_update_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE servicing_investorlossrecognitionline "
                "SET metadata = %s WHERE id = %s",
                ['{"mutated": true}', loss_line.id.hex],
            )
    assert "append-only" in str(loss_update_error.value)


@pytest.mark.django_db
def test_recovery_records_have_app_and_db_guards(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 3, 16),
            loan_ids=(str(loan.pk),),
        )
    )
    result = record_loan_recovery_payment(
        RecordLoanRecoveryPaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            gross_recovered_minor=1_000_00,
            externally_deducted_costs_minor=0,
            third_party_costs_from_received_minor=0,
            recovery_fee_applied=False,
            recovery_fee_bps=0,
            principal_recovered_minor=1_000_00,
            contractual_interest_recovered_minor=0,
            default_interest_recovered_minor=0,
            penalties_recovered_minor=0,
            other_costs_recovered_minor=0,
            booking_date=date(2026, 3, 20),
            value_date=date(2026, 3, 20),
            collection_account_identifier="CH00GARANTARECOVERY",
            payer_name="Recovery counsel",
            idempotency_key="servicing-append-recovery",
        )
    )
    recovery_event = result.recovery_event
    recovery_line = result.distribution_lines[0]

    with pytest.raises(AppendOnlyViolation):
        recovery_event.notes = "mutated"
        recovery_event.save()
    with pytest.raises(AppendOnlyViolation):
        recovery_line.metadata = {"mutated": True}
        recovery_line.save()
    with pytest.raises(AppendOnlyViolation):
        LoanRecoveryEvent.objects.filter(id=recovery_event.id).update(notes="mutated")
    with pytest.raises(AppendOnlyViolation):
        InvestorRecoveryDistributionLine.objects.filter(id=recovery_line.id).update(
            metadata={"mutated": True}
        )

    with pytest.raises(DatabaseError) as update_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE servicing_loanrecoveryevent SET notes = %s WHERE id = %s",
                ["mutated", recovery_event.id.hex],
            )
    assert "append-only" in str(update_error.value)

    with pytest.raises(DatabaseError) as delete_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM servicing_investorrecoverydistributionline WHERE id = %s",
                [recovery_line.id.hex],
            )
    assert "append-only" in str(delete_error.value)
