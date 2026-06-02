from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client

from backend.apps.ledger.models import (
    BankOperation,
    InvestorBalanceLot,
    LedgerAccountType,
    LedgerDirection,
    LedgerJournalEntry,
    LedgerPosting,
    LedgerPostingSide,
    ReconciliationSnapshot,
)
from backend.apps.ledger.services import (
    CreateReconciliationSnapshotCommand,
    DeclareLenderDepositCommand,
    LedgerValidationError,
    PostingCommand,
    PostJournalEntryCommand,
    create_reconciliation_snapshot,
    declare_lender_deposit,
    get_or_create_ledger_account,
    plan_investment_balance_consumption,
    post_journal_entry,
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
    assert broken.reconciliation_difference_minor == -10_00
    assert DomainEvent.objects.filter(
        event_type="LedgerReconciliationBreakDetected",
        aggregate_id=str(broken.id),
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
        with pytest.raises(AppendOnlyViolation):
            record.save()
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).update(id=record_id)
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).delete()

        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"UPDATE {table} SET id = %s WHERE id = %s", [record_id, record_id])

        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE id = %s", [record_id])
