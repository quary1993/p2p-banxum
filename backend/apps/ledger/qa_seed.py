"""IP of Webby-Soft SRL. Synthetic balances for the explicit offline QA rebuild only."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import transaction

from backend.apps.ledger.models import (
    BalanceLotSourceType,
    InvestorBalanceLot,
    LedgerAccountType,
    LedgerDirection,
    LedgerPostingSide,
)
from backend.apps.ledger.services import (
    PostingCommand,
    PostJournalEntryCommand,
    _enabled_currency,
    _lender_account_for_id,
    _lot_deadlines,
    get_or_create_ledger_account,
    post_journal_entry,
)
from backend.apps.platform_core.domain.access import is_superadmin_actor
from backend.apps.platform_core.domain.time import business_date, now_utc


@transaction.atomic
def create_qa_opening_balance(
    *, actor: Any, investor_user_id: str, currency_code: str, reset_id: UUID
) -> InvestorBalanceLot:
    if not settings.QA_DATA_RESET_ALLOWED or not is_superadmin_actor(actor):
        raise ValueError("QA opening balances require the offline reset and an active superadmin.")
    investor = _lender_account_for_id(investor_user_id)
    currency = _enabled_currency(currency_code)
    key = f"qa-reset:{reset_id}:{investor.pk}:{currency.code}"
    existing = InvestorBalanceLot.objects.filter(source_id=key).first()
    if existing is not None:
        return existing
    if InvestorBalanceLot.objects.filter(investor_user_id=investor.pk, currency=currency).exists():
        raise ValueError("QA opening balances require an empty investor balance ledger.")
    amount = 50_000_000
    received = now_utc()
    day = business_date(received)
    cash = get_or_create_ledger_account(
        account_type=LedgerAccountType.COLLECTION_CASH,
        currency=currency,
        name=f"{currency.code} collection cash",
    )
    liability = get_or_create_ledger_account(
        account_type=LedgerAccountType.INVESTOR_BALANCE_LIABILITY,
        currency=currency,
        owner_type="investor",
        owner_id=str(investor.pk),
        name=f"{currency.code} investor balance liability {investor.pk}",
    )
    entry = post_journal_entry(
        PostJournalEntryCommand(
            actor=actor,
            event_type="qa_opening_balance",
            direction=LedgerDirection.IN,
            currency=currency.code,
            gross_amount_minor=amount,
            net_amount_minor=amount,
            booking_date=day,
            value_date=day,
            effective_at=received,
            received_at=received,
            source_type="qa_dataset_reset",
            source_id=str(reset_id),
            idempotency_key=key,
            lender_user_id=str(investor.pk),
            evidence_reference=f"QA RESET {reset_id}",
            metadata={"synthetic": True, "reset_id": str(reset_id), "not_a_bank_transfer": True},
            postings=[
                PostingCommand(
                    account=cash,
                    side=LedgerPostingSide.DEBIT,
                    amount_minor=amount,
                    memo="Synthetic QA opening cash; no bank transfer",
                ),
                PostingCommand(
                    account=liability,
                    side=LedgerPostingSide.CREDIT,
                    amount_minor=amount,
                    memo="Synthetic QA investor opening balance",
                ),
            ],
        )
    )
    investment_deadline, withdrawal_deadline = _lot_deadlines(received)
    return InvestorBalanceLot.objects.create(
        investor_user_id=investor.pk,
        currency=currency,
        source_journal_entry=entry,
        source_type=BalanceLotSourceType.CORRECTION,
        source_id=key,
        received_at=received,
        investment_deadline_at=investment_deadline,
        withdrawal_deadline_at=withdrawal_deadline,
        original_amount_minor=amount,
        available_amount_minor=amount,
        lineage=[{"source_type": "qa_dataset_reset", "source_id": str(reset_id)}],
    )
