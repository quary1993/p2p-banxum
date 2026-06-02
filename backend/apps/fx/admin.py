from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from backend.apps.fx.models import FxEvent, FxExchange, FxQuote


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


@admin.register(FxEvent)
class FxEventAdmin(ReadOnlyFxAdmin):
    list_display = ("id", "event_type", "actor_user_id", "occurred_at")
    list_filter = ("event_type",)
    search_fields = ("id", "actor_user_id", "quote__id", "exchange__id")
