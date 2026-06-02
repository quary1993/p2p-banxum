from __future__ import annotations

from dataclasses import asdict
from typing import Any

from rest_framework import serializers

from backend.apps.ledger.models import (
    BankOperation,
    BankOperationStatus,
    BankOperationType,
    InvestorBalanceLot,
    InvestorPayoutInstruction,
    InvestorWithdrawalRequest,
    LedgerJournalEntry,
    ReconciliationSnapshot,
)
from backend.apps.ledger.services import (
    BalanceAgeingScanResult,
    BalanceSummary,
)


def _dataclass_payload(value: Any) -> dict[str, Any]:
    return dict(asdict(value))


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
    cancellation_journal_entry_id = serializers.UUIDField(allow_null=True)
    finalized_by_admin_id = serializers.UUIDField(allow_null=True)
    finalized_at = serializers.DateTimeField(allow_null=True)
    cancelled_by_admin_id = serializers.UUIDField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    bank_reference = serializers.CharField()
    payment_reference = serializers.CharField()
    evidence_reference = serializers.CharField()
    notes = serializers.CharField()
    admin_notes = serializers.CharField()
    cancellation_reason = serializers.CharField()
    metadata = serializers.JSONField()
    idempotency_key = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class InvestorPayoutInstructionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    investor_user_id = serializers.UUIDField()
    currency = serializers.CharField(source="currency.code")
    status = serializers.CharField()
    destination_iban = serializers.CharField()
    destination_account_name = serializers.CharField()
    is_verified_usable = serializers.BooleanField()
    verified_by_admin_id = serializers.UUIDField(allow_null=True)
    verified_at = serializers.DateTimeField(allow_null=True)
    created_by_admin_id = serializers.UUIDField()
    notes = serializers.CharField()
    metadata = serializers.JSONField()
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


class InvestorPayoutInstructionRegisterRequestSerializer(serializers.Serializer[Any]):
    investor_user_id = serializers.UUIDField()
    currency = serializers.CharField(max_length=3)
    destination_iban = serializers.CharField(max_length=128)
    destination_account_name = serializers.CharField(max_length=255)
    is_verified_usable = serializers.BooleanField(required=False, default=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)


class InvestorPayoutInstructionRegisterResponseSerializer(serializers.Serializer[Any]):
    payout_instruction = InvestorPayoutInstructionSerializer()


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


class BorrowerDisbursementFinalizeRequestSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    borrower_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=1)
    currency = serializers.CharField(max_length=3)
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField(max_length=128)
    payee_name = serializers.CharField(max_length=255)
    payee_account_identifier = serializers.CharField(max_length=128)
    bank_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class BorrowerDisbursementFinalizeResponseSerializer(serializers.Serializer[Any]):
    bank_operation = BankOperationSerializer()
    journal_entry = LedgerJournalEntrySerializer()


class InvestorWithdrawalCancelRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class InvestorWithdrawalCancelResponseSerializer(serializers.Serializer[Any]):
    withdrawal_request = InvestorWithdrawalRequestSerializer()
    journal_entry = LedgerJournalEntrySerializer()


class BalanceAgeingScanRequestSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField(required=False)
    currency = serializers.CharField(required=False, max_length=3)
    dry_run = serializers.BooleanField(required=False, default=False)


class BalanceAgeingReminderDueSerializer(serializers.Serializer[Any]):
    lot_id = serializers.CharField()
    investor_user_id = serializers.CharField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    day = serializers.IntegerField()
    withdrawal_deadline_at = serializers.DateTimeField()


class BalanceAgeingForcedWithdrawalCandidateSerializer(serializers.Serializer[Any]):
    investor_user_id = serializers.CharField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    lot_ids = serializers.ListField(child=serializers.CharField())
    payout_instruction_id = serializers.CharField()


class BalanceAgeingPenaltyModeTransitionSerializer(serializers.Serializer[Any]):
    lot_id = serializers.CharField()
    investor_user_id = serializers.CharField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    days_overdue = serializers.IntegerField()


class BalanceAgeingScanResponseSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField()
    reminders_due = BalanceAgeingReminderDueSerializer(many=True)
    forced_withdrawal_candidates = BalanceAgeingForcedWithdrawalCandidateSerializer(many=True)
    forced_withdrawal_requests = InvestorWithdrawalRequestSerializer(many=True)
    penalty_mode_transitions = BalanceAgeingPenaltyModeTransitionSerializer(many=True)
    skipped_lot_ids = serializers.ListField(child=serializers.CharField())


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


def serialize_payout_instruction(
    payout_instruction: InvestorPayoutInstruction,
) -> dict[str, Any]:
    return dict(InvestorPayoutInstructionSerializer(payout_instruction).data)


def serialize_balance_summary(summary: BalanceSummary) -> dict[str, Any]:
    return dict(InvestorBalanceSummarySerializer(summary).data)


def serialize_balance_ageing_scan_result(result: BalanceAgeingScanResult) -> dict[str, Any]:
    payload = {
        "as_of": result.as_of,
        "reminders_due": [_dataclass_payload(reminder) for reminder in result.reminders_due],
        "forced_withdrawal_candidates": [
            _dataclass_payload(candidate) for candidate in result.forced_withdrawal_candidates
        ],
        "forced_withdrawal_requests": result.forced_withdrawal_requests,
        "penalty_mode_transitions": [
            _dataclass_payload(transition) for transition in result.penalty_mode_transitions
        ],
        "skipped_lot_ids": result.skipped_lot_ids,
    }
    return dict(BalanceAgeingScanResponseSerializer(payload).data)


def serialize_reconciliation_snapshot(snapshot: ReconciliationSnapshot) -> dict[str, Any]:
    return dict(ReconciliationSnapshotSerializer(snapshot).data)


LAUNCH_BANK_OPERATION_TYPES = BankOperationType.choices
LAUNCH_BANK_OPERATION_STATUSES = BankOperationStatus.choices
