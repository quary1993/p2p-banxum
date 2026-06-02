from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, cast
from unittest import mock

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.ledger.models import (
    BalanceLotStatus,
    BankOperation,
    InvestorBalanceLot,
    InvestorWithdrawalRequest,
    InvestorWithdrawalRequestStatus,
    LedgerAccountType,
    LedgerDirection,
    LedgerJournalEntry,
    LedgerPosting,
    LedgerPostingSide,
    ReconciliationSnapshot,
)
from backend.apps.ledger.services import (
    CancelInvestorWithdrawalCommand,
    CreateReconciliationSnapshotCommand,
    DeclareLenderDepositCommand,
    FinalizeInvestorWithdrawalCommand,
    LedgerValidationError,
    PostingCommand,
    PostJournalEntryCommand,
    RequestInvestorWithdrawalCommand,
    cancel_investor_withdrawal,
    create_reconciliation_snapshot,
    declare_lender_deposit,
    finalize_investor_withdrawal,
    get_or_create_ledger_account,
    plan_investment_balance_consumption,
    post_journal_entry,
    request_investor_withdrawal,
    summarize_investor_balance,
)
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import AuditEvent, Currency, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="ledger-admin@example.test",
            password="AdminPass123!",
            full_name="Ledger Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="ledger-investor@example.test",
            full_name="Ledger Investor",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


def _received_at(value_date: date) -> datetime:
    return datetime.combine(value_date, time.min, tzinfo=business_timezone())


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


def _deposit_command(
    admin_user: Model,
    investor: Model,
    *,
    amount_minor: int = 100_00,
    value_date: date = date(2026, 1, 1),
    idempotency_key: str = "deposit-1",
) -> DeclareLenderDepositCommand:
    return DeclareLenderDepositCommand(
        actor=admin_user,
        investor_user_id=str(investor.pk),
        amount_minor=amount_minor,
        currency="CHF",
        booking_date=value_date,
        value_date=value_date,
        collection_account_identifier="CH00GARANTALEDGER",
        payer_name="Ledger Investor",
        payer_account_identifier="CH11INVESTOR",
        bank_reference=f"BANK-{idempotency_key}",
        payment_reference=f"INV-{investor.pk}",
        evidence_reference=f"statement:{idempotency_key}",
        notes="Matched manually.",
        idempotency_key=idempotency_key,
    )


def _journal_command(
    admin_user: Model,
    *,
    amount_minor: int = 100_00,
    idempotency_key: str = "journal-1",
    value_date: date = date(2026, 1, 1),
    received_at: datetime | None = None,
) -> PostJournalEntryCommand:
    currency = Currency.objects.get(code="CHF")
    collection_cash = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
    )
    investor_liability = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id="investor-1",
    )
    return PostJournalEntryCommand(
        actor=admin_user,
        event_type="journal_race_test",
        direction=LedgerDirection.IN,
        currency="CHF",
        gross_amount_minor=amount_minor,
        net_amount_minor=amount_minor,
        booking_date=value_date,
        value_date=value_date,
        effective_at=_received_at(value_date),
        received_at=received_at or _received_at(value_date),
        source_type="test",
        source_id=idempotency_key,
        idempotency_key=idempotency_key,
        postings=[
            PostingCommand(collection_cash, LedgerPostingSide.DEBIT, amount_minor),
            PostingCommand(investor_liability, LedgerPostingSide.CREDIT, amount_minor),
        ],
    )


@pytest.mark.django_db
def test_post_journal_entry_requires_balanced_postings(admin_user: Model) -> None:
    currency = Currency.objects.get(code="CHF")
    collection_cash = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
    )
    investor_liability = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id="investor-1",
    )

    with pytest.raises(LedgerValidationError):
        post_journal_entry(
            PostJournalEntryCommand(
                actor=admin_user,
                event_type="test_unbalanced",
                direction=LedgerDirection.IN,
                currency="CHF",
                gross_amount_minor=100_00,
                net_amount_minor=100_00,
                booking_date=date(2026, 1, 1),
                value_date=date(2026, 1, 1),
                effective_at=_received_at(date(2026, 1, 1)),
                received_at=_received_at(date(2026, 1, 1)),
                source_type="test",
                source_id="unbalanced",
                idempotency_key="journal-unbalanced",
                postings=[
                    PostingCommand(collection_cash, LedgerPostingSide.DEBIT, 100_00),
                    PostingCommand(investor_liability, LedgerPostingSide.CREDIT, 99_00),
                ],
            )
        )


@pytest.mark.django_db
def test_post_journal_entry_rejects_same_account_on_both_sides(admin_user: Model) -> None:
    currency = Currency.objects.get(code="CHF")
    collection_cash = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
    )

    with pytest.raises(LedgerValidationError, match="both sides"):
        post_journal_entry(
            PostJournalEntryCommand(
                actor=admin_user,
                event_type="test_same_account",
                direction=LedgerDirection.INTERNAL,
                currency="CHF",
                gross_amount_minor=100_00,
                net_amount_minor=100_00,
                booking_date=date(2026, 1, 1),
                value_date=date(2026, 1, 1),
                effective_at=_received_at(date(2026, 1, 1)),
                received_at=_received_at(date(2026, 1, 1)),
                source_type="test",
                source_id="same-account",
                idempotency_key="journal-same-account",
                postings=[
                    PostingCommand(collection_cash, LedgerPostingSide.DEBIT, 100_00),
                    PostingCommand(collection_cash, LedgerPostingSide.CREDIT, 100_00),
                ],
            )
        )


@pytest.mark.django_db
def test_post_journal_entry_rejects_received_at_that_contradicts_value_date(
    admin_user: Model,
) -> None:
    with pytest.raises(LedgerValidationError, match="Received timestamp"):
        post_journal_entry(
            _journal_command(
                admin_user,
                idempotency_key="journal-bad-received-at",
                value_date=date(2026, 1, 2),
                received_at=_received_at(date(2026, 1, 1)),
            )
        )


@pytest.mark.django_db
def test_lender_deposit_posts_double_entry_and_creates_balance_lot(
    admin_user: Model,
    investor: Model,
) -> None:
    result = declare_lender_deposit(_deposit_command(admin_user, investor))
    postings = list(result.journal_entry.postings.select_related("account").order_by("side"))

    assert result.bank_operation.operation_type == "lender_deposit"
    assert result.bank_operation.status == "reconciled"
    assert result.journal_entry.direction == "in"
    assert result.journal_entry.gross_amount_minor == 100_00
    assert result.balance_lot.original_amount_minor == 100_00
    assert result.balance_lot.available_amount_minor == 100_00
    assert result.balance_lot.received_at == _received_at(date(2026, 1, 1))
    assert result.balance_lot.investment_deadline_at == _received_at(date(2026, 1, 31))
    assert result.balance_lot.withdrawal_deadline_at == _received_at(date(2026, 3, 2))
    assert [(posting.side, posting.amount_minor) for posting in postings] == [
        ("credit", 100_00),
        ("debit", 100_00),
    ]
    assert {posting.account.account_type for posting in postings} == {
        LedgerAccountType.COLLECTION_CASH,
        LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
    }
    assert AuditEvent.objects.filter(action="ledger.lender_deposit_declared").exists()
    assert DomainEvent.objects.filter(event_type="LenderDepositDeclared").exists()


@pytest.mark.django_db
def test_lender_deposit_is_idempotent(admin_user: Model, investor: Model) -> None:
    first = declare_lender_deposit(_deposit_command(admin_user, investor))
    second = declare_lender_deposit(_deposit_command(admin_user, investor))

    assert second.bank_operation.id == first.bank_operation.id
    assert BankOperation.objects.count() == 1
    assert LedgerJournalEntry.objects.count() == 1
    assert InvestorBalanceLot.objects.count() == 1


@pytest.mark.django_db
def test_lender_deposit_idempotency_key_rejects_different_payload(
    admin_user: Model,
    investor: Model,
) -> None:
    declare_lender_deposit(
        _deposit_command(admin_user, investor, idempotency_key="deposit-mismatch")
    )

    with pytest.raises(LedgerValidationError, match="different request"):
        declare_lender_deposit(
            _deposit_command(
                admin_user,
                investor,
                amount_minor=101_00,
                idempotency_key="deposit-mismatch",
            )
        )

    assert BankOperation.objects.filter(idempotency_key="deposit-mismatch").count() == 1
    assert InvestorBalanceLot.objects.count() == 1


@pytest.mark.django_db
def test_post_journal_entry_idempotency_key_rejects_different_payload(
    admin_user: Model,
) -> None:
    post_journal_entry(_journal_command(admin_user, idempotency_key="journal-mismatch"))

    with pytest.raises(LedgerValidationError, match="different request"):
        post_journal_entry(
            _journal_command(
                admin_user,
                amount_minor=101_00,
                idempotency_key="journal-mismatch",
            )
        )

    assert LedgerJournalEntry.objects.filter(idempotency_key="journal-mismatch").count() == 1


@pytest.mark.django_db
def test_lender_deposit_rejects_non_integer_money(
    admin_user: Model,
    investor: Model,
) -> None:
    with pytest.raises(LedgerValidationError, match="integer"):
        declare_lender_deposit(
            _deposit_command(
                admin_user,
                investor,
                amount_minor=cast(Any, 100.5),
                idempotency_key="deposit-float",
            )
        )


@pytest.mark.django_db
def test_lender_deposit_uses_bounded_derived_journal_idempotency_key(
    admin_user: Model,
    investor: Model,
) -> None:
    source_key = "x" * 160

    result = declare_lender_deposit(
        _deposit_command(admin_user, investor, idempotency_key=source_key)
    )

    assert result.bank_operation.idempotency_key == source_key
    assert result.journal_entry.idempotency_key.startswith("ledger:")
    assert len(result.journal_entry.idempotency_key) <= 160


@pytest.mark.django_db
def test_post_journal_entry_returns_existing_entry_after_idempotency_race(
    admin_user: Model,
) -> None:
    existing = post_journal_entry(_journal_command(admin_user, idempotency_key="journal-race"))

    with (
        mock.patch(
            "backend.apps.ledger.services._existing_journal_entry_for_idempotency",
            side_effect=[None, existing],
        ),
        mock.patch.object(
            LedgerJournalEntry.objects,
            "create",
            side_effect=IntegrityError("duplicate idempotency key"),
        ),
    ):
        result = post_journal_entry(_journal_command(admin_user, idempotency_key="journal-race"))

    assert result.id == existing.id
    assert LedgerJournalEntry.objects.filter(idempotency_key="journal-race").count() == 1


@pytest.mark.django_db
def test_lender_deposit_returns_existing_result_after_idempotency_race(
    admin_user: Model,
    investor: Model,
) -> None:
    existing = declare_lender_deposit(
        _deposit_command(admin_user, investor, idempotency_key="deposit-race")
    )

    with (
        mock.patch(
            "backend.apps.ledger.services._existing_lender_deposit_result",
            side_effect=[None, existing],
        ),
        mock.patch.object(
            BankOperation.objects,
            "create",
            side_effect=IntegrityError("duplicate idempotency key"),
        ),
    ):
        result = declare_lender_deposit(
            _deposit_command(admin_user, investor, idempotency_key="deposit-race")
        )

    assert result.bank_operation.id == existing.bank_operation.id
    assert result.journal_entry.id == existing.journal_entry.id
    assert result.balance_lot.id == existing.balance_lot.id
    assert BankOperation.objects.filter(idempotency_key="deposit-race").count() == 1


@pytest.mark.django_db
def test_balance_summary_classifies_30_and_60_day_ageing(
    admin_user: Model,
    investor: Model,
) -> None:
    declare_lender_deposit(_deposit_command(admin_user, investor))

    day_10 = summarize_investor_balance(
        investor_user_id=str(investor.pk),
        currency="CHF",
        as_of=_received_at(date(2026, 1, 11)),
    )
    day_31 = summarize_investor_balance(
        investor_user_id=str(investor.pk),
        currency="CHF",
        as_of=_received_at(date(2026, 2, 1)),
    )
    day_61 = summarize_investor_balance(
        investor_user_id=str(investor.pk),
        currency="CHF",
        as_of=_received_at(date(2026, 3, 3)),
    )

    assert day_10.investable_minor == 100_00
    assert day_10.withdraw_only_minor == 0
    assert day_31.investable_minor == 0
    assert day_31.withdraw_only_minor == 100_00
    assert day_61.withdraw_only_minor == 0
    assert day_61.overdue_minor == 100_00


@pytest.mark.django_db
def test_balance_summary_excludes_consumed_lots(
    admin_user: Model,
    investor: Model,
) -> None:
    result = declare_lender_deposit(_deposit_command(admin_user, investor))
    InvestorBalanceLot.objects.filter(id=result.balance_lot.id).update(
        status=BalanceLotStatus.CONSUMED,
        available_amount_minor=0,
        invested_amount_minor=100_00,
    )

    summary = summarize_investor_balance(
        investor_user_id=str(investor.pk),
        currency="CHF",
        as_of=_received_at(date(2026, 1, 11)),
    )

    assert summary.total_available_minor == 0
    assert summary.investable_minor == 0


@pytest.mark.django_db
def test_balance_lot_amount_conservation_is_db_enforced(
    admin_user: Model,
    investor: Model,
) -> None:
    result = declare_lender_deposit(_deposit_command(admin_user, investor))

    with pytest.raises(DatabaseError), transaction.atomic():
        InvestorBalanceLot.objects.filter(id=result.balance_lot.id).update(
            available_amount_minor=99_00,
        )


@pytest.mark.django_db
def test_terminal_balance_lot_status_requires_zero_available_amount(
    admin_user: Model,
    investor: Model,
) -> None:
    result = declare_lender_deposit(_deposit_command(admin_user, investor))

    with pytest.raises(DatabaseError), transaction.atomic():
        InvestorBalanceLot.objects.filter(id=result.balance_lot.id).update(
            status=BalanceLotStatus.CONSUMED,
        )


@pytest.mark.django_db
def test_investment_consumption_plan_uses_fifo_and_funding_deadline(
    admin_user: Model,
    investor: Model,
) -> None:
    first = declare_lender_deposit(
        _deposit_command(
            admin_user,
            investor,
            amount_minor=100_00,
            value_date=date(2026, 1, 1),
            idempotency_key="deposit-fifo-1",
        )
    )
    second = declare_lender_deposit(
        _deposit_command(
            admin_user,
            investor,
            amount_minor=100_00,
            value_date=date(2026, 1, 10),
            idempotency_key="deposit-fifo-2",
        )
    )

    plan = plan_investment_balance_consumption(
        investor_user_id=str(investor.pk),
        currency="CHF",
        amount_minor=150_00,
        loan_funding_deadline=date(2026, 1, 25),
        as_of=_received_at(date(2026, 1, 15)),
    )

    assert [(line.lot_id, line.amount_minor) for line in plan] == [
        (str(first.balance_lot.id), 100_00),
        (str(second.balance_lot.id), 50_00),
    ]
    with pytest.raises(LedgerValidationError):
        plan_investment_balance_consumption(
            investor_user_id=str(investor.pk),
            currency="CHF",
            amount_minor=150_00,
            loan_funding_deadline=date(2026, 2, 5),
            as_of=_received_at(date(2026, 1, 15)),
        )


@pytest.mark.django_db
def test_withdrawal_request_requires_financial_access(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    declare_lender_deposit(_deposit_command(admin_user, investor))
    client.force_login(cast(Any, investor))

    response = client.post(
        "/api/v1/ledger/withdrawal-requests/",
        data={
            "amount_minor": 50_00,
            "currency": "CHF",
            "destination_iban": "CH9300762011623852957",
            "destination_account_name": "Ledger Investor",
            "idempotency_key": "withdrawal-no-kyc",
        },
        content_type="application/json",
    )

    assert response.status_code == 403
    assert InvestorWithdrawalRequest.objects.count() == 0


@pytest.mark.django_db
def test_withdrawal_request_moves_balance_to_withdrawal_payable(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))

    withdrawal_request = request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=60_00,
            currency="CHF",
            destination_iban="CH9300762011623852957",
            destination_account_name="Ledger Investor",
            notes="User requested withdrawal.",
            idempotency_key="withdrawal-request-1",
        )
    )
    lot = InvestorBalanceLot.objects.get(investor_user_id=investor.pk)
    assert withdrawal_request.request_journal_entry is not None
    postings = list(
        withdrawal_request.request_journal_entry.postings.select_related("account").order_by("side")
    )
    summary = summarize_investor_balance(
        investor_user_id=str(investor.pk),
        currency="CHF",
        as_of=_received_at(date(2026, 1, 11)),
    )
    snapshot = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 1, 1),
            bank_stated_balance_minor=100_00,
        )
    )

    assert withdrawal_request.status == InvestorWithdrawalRequestStatus.REQUESTED
    assert withdrawal_request.amount_minor == 60_00
    assert withdrawal_request.destination_iban == "CH9300762011623852957"
    assert withdrawal_request.lot_allocations[0]["amount_minor"] == 60_00
    assert lot.available_amount_minor == 40_00
    assert lot.withdrawn_amount_minor == 60_00
    assert lot.status == BalanceLotStatus.AVAILABLE
    assert [(posting.side, posting.amount_minor) for posting in postings] == [
        ("credit", 60_00),
        ("debit", 60_00),
    ]
    assert {posting.account.account_type for posting in postings} == {
        LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        LedgerAccountType.WITHDRAWAL_PAYABLE,
    }
    assert summary.total_available_minor == 40_00
    assert snapshot.reconciliation_difference_minor == 0
    assert snapshot.metadata["withdrawal_payable_minor"] == 60_00
    assert snapshot.metadata["collection_cash_ledger_balance_minor"] == 100_00
    assert DomainEvent.objects.filter(
        event_type="InvestorWithdrawalRequested",
        aggregate_id=str(withdrawal_request.id),
    ).exists()


@pytest.mark.django_db
def test_withdrawal_request_idempotency_rejects_different_payload(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=60_00,
            currency="CHF",
            destination_iban="CH9300762011623852957",
            idempotency_key="withdrawal-mismatch",
        )
    )

    with pytest.raises(LedgerValidationError, match="different request"):
        request_investor_withdrawal(
            RequestInvestorWithdrawalCommand(
                actor=investor,
                amount_minor=61_00,
                currency="CHF",
                destination_iban="CH9300762011623852957",
                idempotency_key="withdrawal-mismatch",
            )
        )

    assert InvestorWithdrawalRequest.objects.count() == 1


@pytest.mark.django_db
def test_admin_finalizes_withdrawal_and_reconciliation_reflects_cash_out(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    withdrawal_request = request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=60_00,
            currency="CHF",
            destination_iban="CH9300762011623852957",
            destination_account_name="Ledger Investor",
            idempotency_key="withdrawal-finalize",
        )
    )

    result = finalize_investor_withdrawal(
        FinalizeInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(withdrawal_request.id),
            booking_date=date(2026, 1, 2),
            value_date=date(2026, 1, 2),
            collection_account_identifier="CH00GARANTALEDGER",
            bank_reference="BANK-WITHDRAWAL-1",
            payment_reference="WD-1",
            evidence_reference="statement:withdrawal-1",
            admin_notes="Paid manually.",
            idempotency_key="bank-withdrawal-1",
        )
    )
    refreshed = InvestorWithdrawalRequest.objects.get(id=withdrawal_request.id)
    postings = list(result.journal_entry.postings.select_related("account").order_by("side"))
    snapshot = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 1, 2),
            bank_stated_balance_minor=40_00,
        )
    )
    idempotent = finalize_investor_withdrawal(
        FinalizeInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(withdrawal_request.id),
            booking_date=date(2026, 1, 2),
            value_date=date(2026, 1, 2),
            collection_account_identifier="CH00GARANTALEDGER",
            bank_reference="BANK-WITHDRAWAL-1",
            payment_reference="WD-1",
            evidence_reference="statement:withdrawal-1",
            admin_notes="Paid manually.",
            idempotency_key="bank-withdrawal-1",
        )
    )

    assert refreshed.status == InvestorWithdrawalRequestStatus.FINALIZED
    assert refreshed.bank_operation_id == result.bank_operation.id
    assert refreshed.finalization_journal_entry_id == result.journal_entry.id
    assert result.bank_operation.operation_type == "lender_withdrawal"
    assert result.bank_operation.status == "reconciled"
    assert [(posting.side, posting.amount_minor) for posting in postings] == [
        ("credit", 60_00),
        ("debit", 60_00),
    ]
    assert {posting.account.account_type for posting in postings} == {
        LedgerAccountType.COLLECTION_CASH,
        LedgerAccountType.WITHDRAWAL_PAYABLE,
    }
    assert snapshot.reconciliation_difference_minor == 0
    assert snapshot.metadata["withdrawal_payable_minor"] == 0
    assert snapshot.metadata["collection_cash_ledger_balance_minor"] == 40_00
    assert idempotent.bank_operation.id == result.bank_operation.id
    assert BankOperation.objects.filter(operation_type="lender_withdrawal").count() == 1
    assert DomainEvent.objects.filter(
        event_type="InvestorWithdrawalFinalized",
        aggregate_id=str(withdrawal_request.id),
    ).exists()


@pytest.mark.django_db
def test_admin_cancels_requested_withdrawal_and_restores_balance(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    withdrawal_request = request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=60_00,
            currency="CHF",
            destination_iban="CH9300762011623852957",
            destination_account_name="Ledger Investor",
            idempotency_key="withdrawal-cancel",
        )
    )

    result = cancel_investor_withdrawal(
        CancelInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(withdrawal_request.id),
            reason="Incorrect destination IBAN before bank payout.",
            idempotency_key="cancel-withdrawal-1",
        )
    )
    refreshed = InvestorWithdrawalRequest.objects.get(id=withdrawal_request.id)
    lot = InvestorBalanceLot.objects.get(investor_user_id=investor.pk)
    postings = list(result.journal_entry.postings.select_related("account").order_by("side"))
    summary = summarize_investor_balance(
        investor_user_id=str(investor.pk),
        currency="CHF",
        as_of=_received_at(date(2026, 1, 11)),
    )
    snapshot = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 1, 2),
            bank_stated_balance_minor=100_00,
        )
    )
    idempotent = cancel_investor_withdrawal(
        CancelInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(withdrawal_request.id),
            reason="Incorrect destination IBAN before bank payout.",
            idempotency_key="cancel-withdrawal-1",
        )
    )

    assert refreshed.status == InvestorWithdrawalRequestStatus.CANCELLED
    assert refreshed.cancellation_journal_entry_id == result.journal_entry.id
    assert refreshed.cancelled_by_admin_id == admin_user.pk
    assert refreshed.cancellation_reason == "Incorrect destination IBAN before bank payout."
    assert lot.available_amount_minor == 100_00
    assert lot.withdrawn_amount_minor == 0
    assert lot.status == BalanceLotStatus.AVAILABLE
    assert [(posting.side, posting.amount_minor) for posting in postings] == [
        ("credit", 60_00),
        ("debit", 60_00),
    ]
    assert {posting.account.account_type for posting in postings} == {
        LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        LedgerAccountType.WITHDRAWAL_PAYABLE,
    }
    assert result.journal_entry.reversal_of_id == withdrawal_request.request_journal_entry_id
    assert summary.total_available_minor == 100_00
    assert snapshot.reconciliation_difference_minor == 0
    assert snapshot.metadata["withdrawal_payable_minor"] == 0
    assert idempotent.journal_entry.id == result.journal_entry.id
    assert (
        LedgerJournalEntry.objects.filter(event_type="investor_withdrawal_cancelled").count() == 1
    )
    assert DomainEvent.objects.filter(
        event_type="InvestorWithdrawalCancelled",
        aggregate_id=str(withdrawal_request.id),
    ).exists()


@pytest.mark.django_db
def test_withdrawal_cancellation_restores_penalty_mode_lot_status(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    deposit = declare_lender_deposit(_deposit_command(admin_user, investor))
    InvestorBalanceLot.objects.filter(id=deposit.balance_lot.id).update(
        status=BalanceLotStatus.PENALTY_MODE.value,
    )
    withdrawal_request = request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=100_00,
            currency="CHF",
            destination_iban="CH9300762011623852957",
            idempotency_key="withdrawal-cancel-penalty-mode",
        )
    )

    cancel_investor_withdrawal(
        CancelInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(withdrawal_request.id),
            reason="Bank payout not yet executed.",
            idempotency_key="cancel-withdrawal-penalty-mode",
        )
    )

    lot = InvestorBalanceLot.objects.get(id=deposit.balance_lot.id)
    assert lot.status == BalanceLotStatus.PENALTY_MODE
    assert lot.available_amount_minor == 100_00
    assert lot.withdrawn_amount_minor == 0


@pytest.mark.django_db
def test_finalized_withdrawal_cannot_be_cancelled(admin_user: Model, investor: Model) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    withdrawal_request = request_investor_withdrawal(
        RequestInvestorWithdrawalCommand(
            actor=investor,
            amount_minor=60_00,
            currency="CHF",
            destination_iban="CH9300762011623852957",
            idempotency_key="withdrawal-finalized-no-cancel",
        )
    )
    finalize_investor_withdrawal(
        FinalizeInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(withdrawal_request.id),
            booking_date=date(2026, 1, 2),
            value_date=date(2026, 1, 2),
            collection_account_identifier="CH00GARANTALEDGER",
            idempotency_key="bank-withdrawal-no-cancel",
        )
    )

    with pytest.raises(LedgerValidationError, match="Only requested withdrawals"):
        cancel_investor_withdrawal(
            CancelInvestorWithdrawalCommand(
                actor=admin_user,
                withdrawal_request_id=str(withdrawal_request.id),
                reason="Too late.",
                idempotency_key="cancel-finalized-withdrawal",
            )
        )


@pytest.mark.django_db
def test_withdrawal_request_and_finalization_api(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    client.force_login(cast(Any, investor))

    request_response = client.post(
        "/api/v1/ledger/withdrawal-requests/",
        data={
            "amount_minor": 70_00,
            "currency": "CHF",
            "destination_iban": "CH9300762011623852957",
            "destination_account_name": "Ledger Investor",
            "idempotency_key": "withdrawal-api",
        },
        content_type="application/json",
    )
    withdrawal_request_id = request_response.json()["withdrawal_request"]["id"]

    client.force_login(cast(Any, admin_user))
    finalize_response = client.post(
        f"/api/v1/ledger/admin/withdrawal-requests/{withdrawal_request_id}/finalize/",
        data={
            "booking_date": "2026-01-02",
            "value_date": "2026-01-02",
            "collection_account_identifier": "CH00GARANTALEDGER",
            "bank_reference": "BANK-WITHDRAWAL-API",
            "payment_reference": "WD-API",
            "evidence_reference": "statement:withdrawal-api",
            "idempotency_key": "bank-withdrawal-api",
        },
        content_type="application/json",
    )

    assert request_response.status_code == 201
    assert request_response.json()["balance_summary"]["total_available_minor"] == 30_00
    assert finalize_response.status_code == 200
    assert finalize_response.json()["withdrawal_request"]["status"] == "finalized"
    assert finalize_response.json()["bank_operation"]["operation_type"] == "lender_withdrawal"


@pytest.mark.django_db
def test_withdrawal_cancellation_api(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    declare_lender_deposit(_deposit_command(admin_user, investor))
    client.force_login(cast(Any, investor))
    request_response = client.post(
        "/api/v1/ledger/withdrawal-requests/",
        data={
            "amount_minor": 70_00,
            "currency": "CHF",
            "destination_iban": "CH9300762011623852957",
            "destination_account_name": "Ledger Investor",
            "idempotency_key": "withdrawal-cancel-api",
        },
        content_type="application/json",
    )
    withdrawal_request_id = request_response.json()["withdrawal_request"]["id"]

    client.force_login(cast(Any, admin_user))
    cancel_response = client.post(
        f"/api/v1/ledger/admin/withdrawal-requests/{withdrawal_request_id}/cancel/",
        data={
            "reason": "Cancelled before bank payout.",
            "idempotency_key": "cancel-withdrawal-api",
        },
        content_type="application/json",
    )

    assert request_response.status_code == 201
    assert cancel_response.status_code == 200
    assert cancel_response.json()["withdrawal_request"]["status"] == "cancelled"
    assert cancel_response.json()["withdrawal_request"]["cancellation_reason"] == (
        "Cancelled before bank payout."
    )
    assert cancel_response.json()["journal_entry"]["event_type"] == "investor_withdrawal_cancelled"


@pytest.mark.django_db
def test_reconciliation_snapshot_compares_bank_to_investor_liability(
    admin_user: Model,
    investor: Model,
) -> None:
    declare_lender_deposit(_deposit_command(admin_user, investor))

    balanced = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 1, 1),
            bank_stated_balance_minor=100_00,
        )
    )
    broken = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 1, 2),
            bank_stated_balance_minor=90_00,
        )
    )

    assert balanced.investor_balance_liability_minor == 100_00
    assert balanced.reconciliation_difference_minor == 0
    assert balanced.metadata["bank_to_collection_cash_difference_minor"] == 0
    assert balanced.metadata["investor_balance_integrity_breaks"] == []
    assert broken.reconciliation_difference_minor == -10_00
    assert broken.metadata["bank_to_collection_cash_difference_minor"] == -10_00
    assert DomainEvent.objects.filter(
        event_type="LedgerReconciliationBreakDetected",
        aggregate_id=str(broken.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="LedgerCashLedgerMismatchDetected",
        aggregate_id=str(broken.id),
    ).exists()


@pytest.mark.django_db
def test_reconciliation_snapshot_flags_wrong_direction_payable_balance(
    admin_user: Model,
) -> None:
    currency = Currency.objects.get(code="CHF")
    withdrawal_payable = get_or_create_ledger_account(
        account_type=LedgerAccountType.WITHDRAWAL_PAYABLE,
        currency=currency,
        owner_type="investor",
        owner_id="investor-sign-test",
    )
    collection_cash = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
    )
    post_journal_entry(
        PostJournalEntryCommand(
            actor=admin_user,
            event_type="test_wrong_direction_payable",
            direction=LedgerDirection.OUT,
            currency="CHF",
            gross_amount_minor=10_00,
            net_amount_minor=10_00,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            effective_at=_received_at(date(2026, 1, 1)),
            received_at=_received_at(date(2026, 1, 1)),
            source_type="test",
            source_id="wrong-direction-payable",
            idempotency_key="journal-wrong-direction-payable",
            postings=[
                PostingCommand(withdrawal_payable, LedgerPostingSide.DEBIT, 10_00),
                PostingCommand(collection_cash, LedgerPostingSide.CREDIT, 10_00),
            ],
        )
    )

    snapshot = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 1, 1),
            bank_stated_balance_minor=0,
        )
    )

    assert snapshot.metadata["withdrawal_payable_minor"] == -10_00
    assert snapshot.metadata["account_sign_anomalies"] == [
        {
            "account_type": LedgerAccountType.WITHDRAWAL_PAYABLE,
            "credit_balance_minor": -10_00,
        }
    ]


@pytest.mark.django_db
def test_reconciliation_snapshot_flags_investor_lot_posting_drift(
    admin_user: Model,
    investor: Model,
) -> None:
    user_model: Any = get_user_model()
    other_investor = cast(
        Model,
        user_model.objects.create_user(
            email="ledger-investor-two@example.test",
            full_name="Ledger Investor Two",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )
    result = declare_lender_deposit(_deposit_command(admin_user, investor))
    InvestorBalanceLot.objects.filter(id=result.balance_lot.id).update(
        investor_user_id=other_investor.pk,
    )

    snapshot = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 1, 1),
            bank_stated_balance_minor=100_00,
        )
    )

    assert snapshot.reconciliation_difference_minor == 0
    assert snapshot.metadata["bank_to_collection_cash_difference_minor"] == 0
    breaks = snapshot.metadata["investor_balance_integrity_breaks"]
    assert {item["investor_user_id"] for item in breaks} == {
        str(investor.pk),
        str(other_investor.pk),
    }
    assert DomainEvent.objects.filter(
        event_type="LedgerInvestorBalanceIntegrityBreakDetected",
        aggregate_id=str(snapshot.id),
    ).exists()


@pytest.mark.django_db
def test_lender_deposit_admin_api_and_balance_summary(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    client.force_login(cast(Any, admin_user))

    deposit_response = client.post(
        "/api/v1/ledger/admin/lender-deposits/",
        data={
            "investor_user_id": str(investor.pk),
            "amount_minor": 250_00,
            "currency": "CHF",
            "booking_date": "2026-01-03",
            "value_date": "2026-01-03",
            "collection_account_identifier": "CH00GARANTALEDGER",
            "payer_name": "Ledger Investor",
            "payer_account_identifier": "CH11INVESTOR",
            "bank_reference": "BANK-API",
            "payment_reference": f"INV-{investor.pk}",
            "evidence_reference": "statement:api",
            "idempotency_key": "deposit-api",
        },
        content_type="application/json",
    )
    summary_response = client.get(
        "/api/v1/ledger/admin/investor-balance-summary/",
        data={"investor_user_id": str(investor.pk), "currency": "CHF"},
    )

    assert deposit_response.status_code == 201
    assert deposit_response.json()["balance_lot"]["available_amount_minor"] == 250_00
    assert summary_response.status_code == 200
    assert summary_response.json()["total_available_minor"] == 250_00


@pytest.mark.django_db
def test_non_admin_cannot_use_lender_deposit_api(
    client: Client,
    investor: Model,
) -> None:
    client.force_login(cast(Any, investor))

    response = client.post(
        "/api/v1/ledger/admin/lender-deposits/",
        data={},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert BankOperation.objects.count() == 0


@pytest.mark.django_db
def test_ledger_append_only_records_have_app_and_db_guards(
    admin_user: Model,
    investor: Model,
) -> None:
    result = declare_lender_deposit(_deposit_command(admin_user, investor))
    snapshot = create_reconciliation_snapshot(
        CreateReconciliationSnapshotCommand(
            actor=admin_user,
            currency="CHF",
            as_of_date=date(2026, 1, 1),
            bank_stated_balance_minor=100_00,
        )
    )
    guarded_records = [
        (result.bank_operation, BankOperation, "ledger_bankoperation"),
        (result.journal_entry, LedgerJournalEntry, "ledger_ledgerjournalentry"),
        (result.journal_entry.postings.first(), LedgerPosting, "ledger_ledgerposting"),
        (snapshot, ReconciliationSnapshot, "ledger_reconciliationsnapshot"),
    ]

    for record, model, table in guarded_records:
        assert record is not None
        record_id = record.pk
        db_record_id = record_id.hex
        with pytest.raises(AppendOnlyViolation):
            record.save()
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).update(id=record_id)
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).delete()

        with pytest.raises(DatabaseError) as update_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {table} SET id = %s WHERE id = %s",
                    [db_record_id, db_record_id],
                )
        assert "append-only" in str(update_error.value)

        with pytest.raises(DatabaseError) as delete_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE id = %s", [db_record_id])
        assert "append-only" in str(delete_error.value)
