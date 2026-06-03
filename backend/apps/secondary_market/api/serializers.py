from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.secondary_market.models import SecondaryMarketListing


class SecondaryMarketListingSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    holding_id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    seller_user_id = serializers.UUIDField()
    status = serializers.CharField()
    publication_type = serializers.CharField()
    current_principal_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    price_bps = serializers.IntegerField()
    transfer_price_minor = serializers.IntegerField()
    discount_premium_bps = serializers.IntegerField()
    accrued_interest_minor = serializers.IntegerField()
    accrued_interest_from_date = serializers.DateField(allow_null=True)
    accrued_interest_to_date = serializers.DateField()
    maker_fee_bps = serializers.IntegerField()
    taker_fee_bps = serializers.IntegerField()
    minimum_maker_fee_minor = serializers.IntegerField()
    minimum_taker_fee_minor = serializers.IntegerField()
    maker_fee_minor = serializers.IntegerField()
    taker_fee_minor = serializers.IntegerField()
    seller_net_proceeds_minor = serializers.IntegerField()
    buyer_total_cost_minor = serializers.IntegerField()
    loan_status_at_listing = serializers.CharField()
    days_past_due = serializers.IntegerField()
    last_payment_date = serializers.DateField(allow_null=True)
    risk_acknowledgement_required = serializers.BooleanField()
    document_acceptance_id = serializers.UUIDField()
    public_disclosure_note = serializers.CharField()
    listed_at = serializers.DateTimeField(allow_null=True)
    approved_by_admin_id = serializers.UUIDField(allow_null=True)
    approved_at = serializers.DateTimeField(allow_null=True)
    approval_reason = serializers.CharField()
    rejected_by_admin_id = serializers.UUIDField(allow_null=True)
    rejected_at = serializers.DateTimeField(allow_null=True)
    rejection_reason = serializers.CharField()
    removed_by_admin_id = serializers.UUIDField(allow_null=True)
    removed_at = serializers.DateTimeField(allow_null=True)
    removal_reason = serializers.CharField()
    created_by_user_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class SecondaryMarketListingCreateRequestSerializer(serializers.Serializer[Any]):
    holding_id = serializers.UUIDField()
    price_bps = serializers.IntegerField(min_value=1, max_value=1_000_000)
    document_acceptance_id = serializers.UUIDField()
    idempotency_key = serializers.CharField(max_length=160)
    notes = serializers.CharField(required=False, allow_blank=True)


class SecondaryMarketListingApproveRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    disclosure_note = serializers.CharField()
    idempotency_key = serializers.CharField(max_length=160)


class SecondaryMarketListingRejectRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    idempotency_key = serializers.CharField(max_length=160)


class SecondaryMarketListingRemoveRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    idempotency_key = serializers.CharField(max_length=160)


class SecondaryMarketListingListQuerySerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


def serialize_secondary_listing(listing: SecondaryMarketListing) -> dict[str, Any]:
    return dict(SecondaryMarketListingSerializer(listing).data)
