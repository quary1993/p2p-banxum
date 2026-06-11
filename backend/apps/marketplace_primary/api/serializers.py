from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryLoanCancellation,
    PrimaryLoanClose,
)


class MarketplaceLoanPreviewSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    title = serializers.CharField()
    purpose = serializers.CharField()
    collateral_type = serializers.CharField()
    interest_rate_bps = serializers.IntegerField()
    term_months = serializers.IntegerField()
    risk_rating = serializers.CharField()
    funding_deadline = serializers.DateField()
    status = serializers.CharField()
    currency = serializers.CharField()
    principal_minor = serializers.IntegerField()
    committed_principal_minor = serializers.IntegerField()
    remaining_capacity_minor = serializers.IntegerField()


class MarketplaceLoanDetailSerializer(MarketplaceLoanPreviewSerializer):
    borrower_id = serializers.UUIDField()
    investor_summary = serializers.CharField()
    purpose_description = serializers.CharField()
    collateral_value_minor = serializers.IntegerField()
    collateral_description = serializers.CharField()
    ltv_bps = serializers.IntegerField(allow_null=True)
    ltv_warnings = serializers.ListField(child=serializers.CharField())
    repayment_type = serializers.CharField()
    first_payment_date = serializers.DateField()
    schedule_version = serializers.IntegerField()


class PrimaryInvestmentOrderSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    investor_user_id = serializers.UUIDField()
    status = serializers.CharField()
    requested_amount_minor = serializers.IntegerField()
    allocated_amount_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    document_acceptance_id = serializers.UUIDField(allow_null=True)
    reservation_journal_entry_id = serializers.UUIDField(allow_null=True)
    release_journal_entry_id = serializers.UUIDField(allow_null=True)
    lot_allocations = serializers.JSONField()
    created_by_user_id = serializers.UUIDField()
    allocated_at = serializers.DateTimeField(allow_null=True)
    released_at = serializers.DateTimeField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)
    closed_by_admin_id = serializers.UUIDField(allow_null=True)
    notes = serializers.CharField()
    admin_notes = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class PrimaryInvestmentOrderCreateRequestSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.CharField(max_length=160)
    notes = serializers.CharField(required=False, allow_blank=True)


class PrimaryInvestmentOrderAllocateRequestSerializer(serializers.Serializer[Any]):
    document_acceptance_id = serializers.UUIDField()
    idempotency_key = serializers.CharField(max_length=160)
    sensitive_action_code_id = serializers.UUIDField()
    sensitive_action_code = serializers.CharField(max_length=32, trim_whitespace=True)


class PrimaryInvestmentOrderReleaseRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    idempotency_key = serializers.CharField(max_length=160)


class PrimaryLoanCloseSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    close_type = serializers.CharField()
    accepted_principal_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    allocated_order_count = serializers.IntegerField()
    closed_not_invested_order_count = serializers.IntegerField()
    borrower_success_fee_bps = serializers.IntegerField()
    borrower_success_fee_minor = serializers.IntegerField()
    borrower_disbursement_payable_minor = serializers.IntegerField()
    funding_close_journal_entry_id = serializers.UUIDField()
    created_by_admin_id = serializers.UUIDField()
    closed_at = serializers.DateTimeField()
    reason = serializers.CharField()
    investor_message = serializers.CharField()
    created_at = serializers.DateTimeField()


class PrimaryLoanCloseRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    investor_message = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class PrimaryLoanCancellationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    currency = serializers.CharField(source="currency.code")
    released_order_count = serializers.IntegerField()
    closed_not_invested_order_count = serializers.IntegerField()
    released_principal_minor = serializers.IntegerField()
    created_by_admin_id = serializers.UUIDField()
    cancelled_at = serializers.DateTimeField()
    reason = serializers.CharField()
    investor_message = serializers.CharField()
    created_at = serializers.DateTimeField()


class PrimaryLoanCancellationRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    investor_message = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class PrimaryLoanExpiryScanRequestSerializer(serializers.Serializer[Any]):
    as_of_date = serializers.DateField(required=False)
    loan_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    investor_message = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160, required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=250)


class PrimaryLoanExpiryScanResponseSerializer(serializers.Serializer[Any]):
    as_of_date = serializers.DateField()
    scanned_count = serializers.IntegerField()
    cancelled_count = serializers.IntegerField()
    skipped_count = serializers.IntegerField()
    cancellations = PrimaryLoanCancellationSerializer(many=True)
    skipped = serializers.ListField(child=serializers.DictField())


class PublicMarketplaceLoanListQuerySerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


def serialize_primary_order(order: PrimaryInvestmentOrder) -> dict[str, Any]:
    return dict(PrimaryInvestmentOrderSerializer(order).data)


def serialize_primary_loan_close(close: PrimaryLoanClose) -> dict[str, Any]:
    return dict(PrimaryLoanCloseSerializer(close).data)


def serialize_primary_loan_cancellation(
    cancellation: PrimaryLoanCancellation,
) -> dict[str, Any]:
    return dict(PrimaryLoanCancellationSerializer(cancellation).data)


def serialize_primary_expiry_scan_result(result: dict[str, Any]) -> dict[str, Any]:
    as_of_date = result["as_of_date"]
    return {
        **result,
        "as_of_date": as_of_date.isoformat() if hasattr(as_of_date, "isoformat") else as_of_date,
        "cancellations": [
            serialize_primary_loan_cancellation(cancellation)
            for cancellation in result["cancellations"]
        ],
    }
