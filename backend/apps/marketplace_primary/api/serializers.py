from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.marketplace_primary.models import PrimaryInvestmentOrder


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
    metadata = serializers.JSONField()
    idempotency_key = serializers.CharField()
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


class PrimaryInvestmentOrderReleaseRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    idempotency_key = serializers.CharField(max_length=160)


class PublicMarketplaceLoanListQuerySerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


def serialize_primary_order(order: PrimaryInvestmentOrder) -> dict[str, Any]:
    return dict(PrimaryInvestmentOrderSerializer(order).data)
