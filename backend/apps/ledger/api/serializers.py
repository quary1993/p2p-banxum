from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.ledger.models import (
    BankOperation,
    BankOperationStatus,
    BankOperationType,
    InvestorBalanceLot,
    InvestorWithdrawalRequest,
    LedgerJournalEntry,
    ReconciliationSnapshot,
)
from backend.apps.ledger.services import BalanceSummary


class BankOperationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    operation_type = serializers.CharField()
    status = serializers.CharField()
    amount_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField()
    payer_name = serializers.CharField()
    payer_account_identifier = serializers.CharField()
    payee_name = serializers.CharField()
    payee_account_identifier = serializers.CharField()
    bank_reference = serializers.CharField()
    payment_reference = serializers.CharField()
    linked_object_type = serializers.CharField()
    linked_object_id = serializers.CharField()
    evidence_reference = serializers.CharField()
    confirmed_by_admin_id = serializers.UUIDField()
    confirmed_at = serializers.DateTimeField()
    notes = serializers.CharField()
    metadata = serializers.JSONField()
    idempotency_key = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class LedgerJournalEntrySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    event_type = serializers.CharField()
    direction = serializers.CharField()
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    effective_at = serializers.DateTimeField()
    received_at = serializers.DateTimeField()
    currency = serializers.CharField(source="currency.code")
    gross_amount_minor = serializers.IntegerField()
    net_amount_minor = serializers.IntegerField()
    source_type = serializers.CharField()
    source_id = serializers.CharField()
    lender_user_id = serializers.UUIDField(allow_null=True)
    borrower_id = serializers.UUIDField(allow_null=True)
    loan_id = serializers.UUIDField(allow_null=True)
    bank_operation_id = serializers.UUIDField(allow_null=True)
    bank_reference = serializers.CharField()
    evidence_reference = serializers.CharField()
    actor_type = serializers.CharField()
    actor_id = serializers.CharField()
    tax_metadata = serializers.JSONField()
    metadata = serializers.JSONField()
    reversal_of_id = serializers.UUIDField(allow_null=True)
    idempotency_key = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class InvestorBalanceLotSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    investor_user_id = serializers.UUIDField()
    currency = serializers.CharField(source="currency.code")
    source_journal_entry_id = serializers.UUIDField()
    source_type = serializers.CharField()
    source_id = serializers.CharField()
    status = serializers.CharField()
    received_at = serializers.DateTimeField()
    investment_deadline_at = serializers.DateTimeField()
    withdrawal_deadline_at = serializers.DateTimeField()
    original_amount_minor = serializers.IntegerField()
    available_amount_minor = serializers.IntegerField()
    invested_amount_minor = serializers.IntegerField()
    withdrawn_amount_minor = serializers.IntegerField()
    penalized_amount_minor = serializers.IntegerField()
    lineage = serializers.JSONField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class InvestorWithdrawalRequestSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    investor_user_id = serializers.UUIDField()
    status = serializers.CharField()
    amount_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    destination_iban = serializers.CharField()
    destination_account_name = serializers.CharField()
    requested_by_user_id = serializers.UUIDField()
    requested_at = serializers.DateTimeField()
    request_journal_entry_id = serializers.UUIDField(allow_null=True)
    is_forced = serializers.BooleanField()
    lot_allocations = serializers.JSONField()
    bank_operation_id = serializers.UUIDField(allow_null=True)
    finalization_journal_entry_id = serializers.UUIDField(allow_null=True)
    finalized_by_admin_id = serializers.UUIDField(allow_null=True)
    finalized_at = serializers.DateTimeField(allow_null=True)
    bank_reference = serializers.CharField()
    payment_reference = serializers.CharField()
    evidence_reference = serializers.CharField()
    notes = serializers.CharField()
    admin_notes = serializers.CharField()
    metadata = serializers.JSONField()
    idempotency_key = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class LenderDepositDeclareRequestSerializer(serializers.Serializer[Any]):
    investor_user_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=1)
    currency = serializers.CharField(max_length=3)
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField(max_length=128)
    payer_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    payer_account_identifier = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )
    bank_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class LenderDepositDeclareResponseSerializer(serializers.Serializer[Any]):
    bank_operation = BankOperationSerializer()
    journal_entry = LedgerJournalEntrySerializer()
    balance_lot = InvestorBalanceLotSerializer()


class InvestorBalanceSummaryQuerySerializer(serializers.Serializer[Any]):
    investor_user_id = serializers.UUIDField()
    currency = serializers.CharField(max_length=3)


class InvestorBalanceSummarySerializer(serializers.Serializer[Any]):
    investor_user_id = serializers.UUIDField()
    currency = serializers.CharField()
    total_available_minor = serializers.IntegerField()
    investable_minor = serializers.IntegerField()
    withdraw_only_minor = serializers.IntegerField()
    overdue_minor = serializers.IntegerField()
    frozen_minor = serializers.IntegerField()
    penalty_mode_minor = serializers.IntegerField()


class InvestorWithdrawalRequestCreateRequestSerializer(serializers.Serializer[Any]):
    amount_minor = serializers.IntegerField(min_value=1)
    currency = serializers.CharField(max_length=3)
    destination_iban = serializers.CharField(max_length=128)
    destination_account_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class InvestorWithdrawalRequestCreateResponseSerializer(serializers.Serializer[Any]):
    withdrawal_request = InvestorWithdrawalRequestSerializer()
    balance_summary = InvestorBalanceSummarySerializer()


class InvestorWithdrawalFinalizeRequestSerializer(serializers.Serializer[Any]):
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField(max_length=128)
    bank_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class InvestorWithdrawalFinalizeResponseSerializer(serializers.Serializer[Any]):
    withdrawal_request = InvestorWithdrawalRequestSerializer()
    bank_operation = BankOperationSerializer()
    journal_entry = LedgerJournalEntrySerializer()


class ReconciliationSnapshotCreateRequestSerializer(serializers.Serializer[Any]):
    currency = serializers.CharField(max_length=3)
    as_of_date = serializers.DateField()
    bank_stated_balance_minor = serializers.IntegerField(min_value=0)
    pending_exception_balance_minor = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)


class ReconciliationSnapshotSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    currency = serializers.CharField(source="currency.code")
    as_of_date = serializers.DateField()
    bank_stated_balance_minor = serializers.IntegerField()
    investor_balance_liability_minor = serializers.IntegerField()
    garanta_accrued_revenue_minor = serializers.IntegerField()
    suspense_unmatched_cash_minor = serializers.IntegerField()
    pending_exception_balance_minor = serializers.IntegerField()
    reconciliation_difference_minor = serializers.IntegerField()
    created_by_admin_id = serializers.UUIDField()
    notes = serializers.CharField()
    metadata = serializers.JSONField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


def serialize_bank_operation(bank_operation: BankOperation) -> dict[str, Any]:
    return dict(BankOperationSerializer(bank_operation).data)


def serialize_journal_entry(journal_entry: LedgerJournalEntry) -> dict[str, Any]:
    return dict(LedgerJournalEntrySerializer(journal_entry).data)


def serialize_balance_lot(balance_lot: InvestorBalanceLot) -> dict[str, Any]:
    return dict(InvestorBalanceLotSerializer(balance_lot).data)


def serialize_withdrawal_request(
    withdrawal_request: InvestorWithdrawalRequest,
) -> dict[str, Any]:
    return dict(InvestorWithdrawalRequestSerializer(withdrawal_request).data)


def serialize_balance_summary(summary: BalanceSummary) -> dict[str, Any]:
    return dict(InvestorBalanceSummarySerializer(summary).data)


def serialize_reconciliation_snapshot(snapshot: ReconciliationSnapshot) -> dict[str, Any]:
    return dict(ReconciliationSnapshotSerializer(snapshot).data)


LAUNCH_BANK_OPERATION_TYPES = BankOperationType.choices
LAUNCH_BANK_OPERATION_STATUSES = BankOperationStatus.choices
