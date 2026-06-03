from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from backend.apps.fx.models import (
    FxEvent,
    FxExchange,
    FxExternalSettlement,
    FxExternalSettlementExchange,
    FxQuote,
)


class ReadOnlyFxAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(FxQuote)
class FxQuoteAdmin(ReadOnlyFxAdmin):
    list_display = (
        "id",
        "investor_user_id",
        "source_currency",
        "target_currency",
        "source_amount_minor",
        "target_amount_minor",
        "fee_minor",
        "issued_at",
        "expires_at",
    )
    list_filter = ("source_currency", "target_currency", "provider", "sanity_check_passed")
    search_fields = ("id", "investor_user_id", "provider_quote_id", "idempotency_key")


@admin.register(FxExchange)
class FxExchangeAdmin(ReadOnlyFxAdmin):
    list_display = (
        "id",
        "investor_user_id",
        "source_currency",
        "target_currency",
        "source_amount_minor",
        "target_amount_minor",
        "fee_minor",
        "executed_at",
    )
    list_filter = ("source_currency", "target_currency", "status")
    search_fields = ("id", "investor_user_id", "quote__id", "idempotency_key")


@admin.register(FxExternalSettlement)
class FxExternalSettlementAdmin(ReadOnlyFxAdmin):
    list_display = (
        "id",
        "sold_currency",
        "bought_currency",
        "sold_amount_minor",
        "bought_amount_minor",
        "sold_currency_residual_minor",
        "bought_currency_residual_minor",
        "value_date",
        "declared_at",
    )
    list_filter = ("sold_currency", "bought_currency", "status", "value_date")
    search_fields = ("id", "bank_reference", "payment_reference", "idempotency_key")


@admin.register(FxExternalSettlementExchange)
class FxExternalSettlementExchangeAdmin(ReadOnlyFxAdmin):
    list_display = (
        "id",
        "external_settlement",
        "exchange",
        "source_amount_minor",
        "gross_target_amount_minor",
        "fee_minor",
        "settled_at",
    )
    search_fields = ("id", "external_settlement__id", "exchange__id")


@admin.register(FxEvent)
class FxEventAdmin(ReadOnlyFxAdmin):
    list_display = ("id", "event_type", "actor_user_id", "occurred_at")
    list_filter = ("event_type",)
    search_fields = (
        "id",
        "actor_user_id",
        "quote__id",
        "exchange__id",
        "external_settlement__id",
    )
