from __future__ import annotations

from dataclasses import asdict
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from backend.apps.fx.models import FxExchange, FxExternalSettlement, FxQuote
from backend.apps.fx.services import FxDeltaReport, FxRealizedSettlementReport


class FxQuoteSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    investor_user_id = serializers.UUIDField()
    source_currency = serializers.CharField(source="source_currency.code")
    target_currency = serializers.CharField(source="target_currency.code")
    source_amount_minor = serializers.IntegerField()
    provider = serializers.CharField()
    provider_quote_id = serializers.CharField()
    rate = serializers.DecimalField(max_digits=24, decimal_places=12)
    previous_day_average_rate = serializers.DecimalField(
        max_digits=24,
        decimal_places=12,
        allow_null=True,
    )
    platform_fee_bps = serializers.IntegerField()
    gross_target_amount_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    target_amount_minor = serializers.IntegerField()
    limit_chf_equivalent_minor = serializers.IntegerField()
    issued_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    provider_rate_timestamp = serializers.DateTimeField()
    sanity_check_passed = serializers.BooleanField()
    sanity_metadata = serializers.JSONField()
    status = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_status(self, quote: FxQuote) -> str:
        if quote.exchanges.exists():
            return "executed"
        if timezone.now() > quote.expires_at:
            return "expired"
        return "issued"


class FxExchangeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    quote_id = serializers.UUIDField()
    investor_user_id = serializers.UUIDField()
    source_currency = serializers.CharField(source="source_currency.code")
    target_currency = serializers.CharField(source="target_currency.code")
    source_amount_minor = serializers.IntegerField()
    rate = serializers.DecimalField(max_digits=24, decimal_places=12)
    platform_fee_bps = serializers.IntegerField()
    gross_target_amount_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    target_amount_minor = serializers.IntegerField()
    limit_chf_equivalent_minor = serializers.IntegerField()
    status = serializers.CharField()
    source_journal_entry_id = serializers.UUIDField()
    target_journal_entry_id = serializers.UUIDField()
    target_balance_lot_id = serializers.UUIDField()
    source_lot_allocations = serializers.JSONField()
    executed_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class FxExternalSettlementSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    sold_currency = serializers.CharField(source="sold_currency.code")
    bought_currency = serializers.CharField(source="bought_currency.code")
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    expected_sold_amount_minor = serializers.IntegerField()
    expected_bought_amount_minor = serializers.IntegerField()
    expected_fee_minor = serializers.IntegerField()
    sold_amount_minor = serializers.IntegerField()
    bought_amount_minor = serializers.IntegerField()
    sold_currency_residual_minor = serializers.IntegerField()
    bought_currency_residual_minor = serializers.IntegerField()
    actual_rate = serializers.DecimalField(max_digits=24, decimal_places=12)
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField()
    bank_reference = serializers.CharField()
    payment_reference = serializers.CharField()
    evidence_reference = serializers.CharField()
    notes = serializers.CharField()
    status = serializers.CharField()
    sold_bank_operation_id = serializers.UUIDField()
    bought_bank_operation_id = serializers.UUIDField()
    sold_journal_entry_id = serializers.UUIDField()
    bought_journal_entry_id = serializers.UUIDField()
    declared_by_admin_id = serializers.UUIDField()
    declared_at = serializers.DateTimeField()
    metadata = serializers.JSONField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class FxQuoteIssueRequestSerializer(serializers.Serializer[Any]):
    source_currency = serializers.CharField(max_length=3)
    target_currency = serializers.CharField(max_length=3)
    source_amount_minor = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.CharField(max_length=160)


class FxQuoteExecuteRequestSerializer(serializers.Serializer[Any]):
    idempotency_key = serializers.CharField(max_length=160)
    sensitive_action_code_id = serializers.UUIDField()
    sensitive_action_code = serializers.CharField(max_length=32, trim_whitespace=True)


class FxDeltaReportQuerySerializer(serializers.Serializer[Any]):
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class FxExternalSettlementDeclareRequestSerializer(serializers.Serializer[Any]):
    sold_currency = serializers.CharField(max_length=3)
    bought_currency = serializers.CharField(max_length=3)
    sold_amount_minor = serializers.IntegerField(min_value=1)
    bought_amount_minor = serializers.IntegerField(min_value=1)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField(max_length=128)
    bank_reference = serializers.CharField(max_length=160, allow_blank=True, required=False)
    payment_reference = serializers.CharField(max_length=160, allow_blank=True, required=False)
    evidence_reference = serializers.CharField(max_length=255, allow_blank=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False)
    idempotency_key = serializers.CharField(max_length=160)


class FxDeltaReportSerializer(serializers.Serializer[Any]):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    exchange_count = serializers.IntegerField()
    source_sold_by_currency_minor = serializers.JSONField()
    gross_target_bought_by_currency_minor = serializers.JSONField()
    target_credited_by_currency_minor = serializers.JSONField()
    fees_by_currency_minor = serializers.JSONField()
    net_external_settlement_by_currency_minor = serializers.JSONField()


class FxRealizedSettlementReportSerializer(serializers.Serializer[Any]):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    settlement_count = serializers.IntegerField()
    expected_sold_by_currency_minor = serializers.JSONField()
    actual_sold_by_currency_minor = serializers.JSONField()
    expected_bought_by_currency_minor = serializers.JSONField()
    actual_bought_by_currency_minor = serializers.JSONField()
    fees_by_currency_minor = serializers.JSONField()
    residual_by_currency_minor = serializers.JSONField()


def serialize_fx_quote(quote: FxQuote) -> dict[str, Any]:
    return dict(FxQuoteSerializer(quote).data)


def serialize_fx_exchange(exchange: FxExchange) -> dict[str, Any]:
    return dict(FxExchangeSerializer(exchange).data)


def serialize_fx_external_settlement(settlement: FxExternalSettlement) -> dict[str, Any]:
    return dict(FxExternalSettlementSerializer(settlement).data)


def serialize_fx_delta_report(report: FxDeltaReport) -> dict[str, Any]:
    return dict(asdict(report))


def serialize_fx_realized_settlement_report(report: FxRealizedSettlementReport) -> dict[str, Any]:
    return dict(asdict(report))
