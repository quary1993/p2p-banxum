from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    InvestorRepaymentDistributionLine,
    LoanRiskNote,
    LoanRiskNoteType,
    LoanRiskNoteVisibility,
    LoanWriteOffEvent,
)


class BorrowerRepaymentRecordRequestSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=1)
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField(max_length=128)
    payer_name = serializers.CharField(max_length=255)
    payer_account_identifier = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
    )
    bank_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=160)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    warning_acknowledged = serializers.BooleanField(required=False, default=False)
    idempotency_key = serializers.CharField(max_length=160)


class BorrowerRepaymentEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    installment_id = serializers.UUIDField()
    event_type = serializers.CharField()
    amount_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    received_at = serializers.DateTimeField()
    expected_due_minor = serializers.IntegerField()
    interest_applied_minor = serializers.IntegerField()
    principal_applied_minor = serializers.IntegerField()
    future_principal_applied_minor = serializers.IntegerField()
    fees_applied_minor = serializers.IntegerField()
    penalties_applied_minor = serializers.IntegerField()
    remaining_installment_interest_minor = serializers.IntegerField()
    remaining_installment_principal_minor = serializers.IntegerField()
    warning_acknowledged = serializers.BooleanField()
    bank_operation_id = serializers.UUIDField()
    journal_entry_id = serializers.UUIDField()
    created_by_admin_id = serializers.UUIDField()
    notes = serializers.CharField()
    metadata = serializers.JSONField()
    idempotency_key = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class InvestorRepaymentDistributionLineSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    repayment_event_id = serializers.UUIDField()
    holding_id = serializers.UUIDField()
    investor_user_id = serializers.UUIDField()
    currency = serializers.CharField(source="currency.code")
    balance_lot_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    current_principal_before_minor = serializers.IntegerField()
    current_principal_after_minor = serializers.IntegerField()
    metadata = serializers.JSONField()
    occurred_at = serializers.DateTimeField()


class BorrowerRepaymentRecordResponseSerializer(serializers.Serializer[Any]):
    repayment_event = BorrowerRepaymentEventSerializer()
    distribution_lines = InvestorRepaymentDistributionLineSerializer(many=True)


class LoanServicingStatusScanRequestSerializer(serializers.Serializer[Any]):
    as_of_date = serializers.DateField()
    loan_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )


class LoanServicingStatusChangeSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    previous_status = serializers.CharField()
    new_status = serializers.CharField()
    days_past_due = serializers.IntegerField()
    outstanding_minor = serializers.IntegerField()
    triggering_installment_id = serializers.CharField(allow_blank=True)
    triggering_due_date = serializers.DateField(allow_null=True)


class LoanServicingStatusScanResponseSerializer(serializers.Serializer[Any]):
    as_of_date = serializers.DateField()
    changes = LoanServicingStatusChangeSerializer(many=True)


class LoanRiskNoteCreateRequestSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    visibility = serializers.ChoiceField(choices=LoanRiskNoteVisibility.choices)
    note_type = serializers.ChoiceField(choices=LoanRiskNoteType.choices)
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    body = serializers.CharField()
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    metadata = serializers.JSONField(required=False)
    idempotency_key = serializers.CharField(max_length=160)


class LoanRiskNoteListQuerySerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    include_internal = serializers.BooleanField(required=False, default=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


class PublicLoanRiskNoteListQuerySerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


class LoanRiskNoteSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    borrower_id = serializers.UUIDField()
    visibility = serializers.CharField()
    note_type = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    evidence_reference = serializers.CharField()
    created_by_admin_id = serializers.UUIDField()
    occurred_at = serializers.DateTimeField()
    metadata = serializers.JSONField()
    idempotency_key = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class PublicLoanRiskNoteSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    visibility = serializers.CharField()
    note_type = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    occurred_at = serializers.DateTimeField()


class LoanWriteOffRecordRequestSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    written_off_principal_minor = serializers.IntegerField(min_value=0)
    written_off_contractual_interest_minor = serializers.IntegerField(
        required=False,
        min_value=0,
        default=0,
    )
    written_off_default_interest_minor = serializers.IntegerField(
        required=False,
        min_value=0,
        default=0,
    )
    written_off_fees_minor = serializers.IntegerField(required=False, min_value=0, default=0)
    written_off_penalties_minor = serializers.IntegerField(required=False, min_value=0, default=0)
    reason = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)
    evidence_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    metadata = serializers.JSONField(required=False)
    idempotency_key = serializers.CharField(max_length=160)


class LoanWriteOffEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    borrower_id = serializers.UUIDField()
    currency = serializers.CharField(source="currency.code")
    written_off_principal_minor = serializers.IntegerField()
    written_off_contractual_interest_minor = serializers.IntegerField()
    written_off_default_interest_minor = serializers.IntegerField()
    written_off_fees_minor = serializers.IntegerField()
    written_off_penalties_minor = serializers.IntegerField()
    total_written_off_minor = serializers.IntegerField()
    previous_loan_status = serializers.CharField()
    new_loan_status = serializers.CharField()
    reason = serializers.CharField()
    notes = serializers.CharField()
    evidence_reference = serializers.CharField()
    written_off_at = serializers.DateTimeField()
    created_by_admin_id = serializers.UUIDField()
    metadata = serializers.JSONField()
    idempotency_key = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


def serialize_borrower_repayment_event(
    repayment_event: BorrowerRepaymentEvent,
) -> dict[str, Any]:
    return dict(BorrowerRepaymentEventSerializer(repayment_event).data)


def serialize_distribution_line(
    distribution_line: InvestorRepaymentDistributionLine,
) -> dict[str, Any]:
    return dict(InvestorRepaymentDistributionLineSerializer(distribution_line).data)


def serialize_status_change(change: Any) -> dict[str, Any]:
    return {
        "loan_id": change.loan_id,
        "previous_status": change.previous_status,
        "new_status": change.new_status,
        "days_past_due": change.days_past_due,
        "outstanding_minor": change.outstanding_minor,
        "triggering_installment_id": change.triggering_installment_id,
        "triggering_due_date": change.triggering_due_date,
    }


def serialize_risk_note(note: LoanRiskNote) -> dict[str, Any]:
    return dict(LoanRiskNoteSerializer(note).data)


def serialize_public_risk_note(note: LoanRiskNote) -> dict[str, Any]:
    return dict(PublicLoanRiskNoteSerializer(note).data)


def serialize_write_off_event(write_off: LoanWriteOffEvent) -> dict[str, Any]:
    return dict(LoanWriteOffEventSerializer(write_off).data)
