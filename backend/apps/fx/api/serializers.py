from __future__ import annotations

from dataclasses import asdict
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from backend.apps.fx.models import FxExchange, FxQuote
from backend.apps.fx.services import FxDeltaReport


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


class FxQuoteIssueRequestSerializer(serializers.Serializer[Any]):
    source_currency = serializers.CharField(max_length=3)
    target_currency = serializers.CharField(max_length=3)
    source_amount_minor = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.CharField(max_length=160)


class FxQuoteExecuteRequestSerializer(serializers.Serializer[Any]):
    idempotency_key = serializers.CharField(max_length=160)


class FxDeltaReportQuerySerializer(serializers.Serializer[Any]):
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class FxDeltaReportSerializer(serializers.Serializer[Any]):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    exchange_count = serializers.IntegerField()
    source_sold_by_currency_minor = serializers.JSONField()
    gross_target_bought_by_currency_minor = serializers.JSONField()
    target_credited_by_currency_minor = serializers.JSONField()
    fees_by_currency_minor = serializers.JSONField()
    net_external_settlement_by_currency_minor = serializers.JSONField()


def serialize_fx_quote(quote: FxQuote) -> dict[str, Any]:
    return dict(FxQuoteSerializer(quote).data)


def serialize_fx_exchange(exchange: FxExchange) -> dict[str, Any]:
    return dict(FxExchangeSerializer(exchange).data)


def serialize_fx_delta_report(report: FxDeltaReport) -> dict[str, Any]:
    return dict(asdict(report))
