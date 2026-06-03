from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from backend.apps.secondary_market.models import (
    SecondaryMarketListing,
    SecondaryMarketListingEvent,
    SecondaryMarketPurchase,
)


class ReadOnlySecondaryMarketAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(SecondaryMarketListing)
class SecondaryMarketListingAdmin(ReadOnlySecondaryMarketAdmin):
    list_display = (
        "id",
        "status",
        "publication_type",
        "seller_user_id",
        "loan",
        "current_principal_minor",
        "price_bps",
        "transfer_price_minor",
        "currency",
        "listed_at",
    )
    list_filter = ("status", "publication_type", "currency", "loan_status_at_listing")
    search_fields = ("id", "seller_user_id", "holding__id", "loan__id", "idempotency_key")
    readonly_fields = tuple(field.name for field in SecondaryMarketListing._meta.fields)


@admin.register(SecondaryMarketListingEvent)
class SecondaryMarketListingEventAdmin(ReadOnlySecondaryMarketAdmin):
    list_display = (
        "id",
        "listing",
        "event_type",
        "actor_user_id",
        "previous_status",
        "new_status",
        "occurred_at",
    )
    list_filter = ("event_type",)
    search_fields = ("id", "listing__id", "holding_id", "loan_id", "seller_user_id")
    readonly_fields = tuple(field.name for field in SecondaryMarketListingEvent._meta.fields)


@admin.register(SecondaryMarketPurchase)
class SecondaryMarketPurchaseAdmin(ReadOnlySecondaryMarketAdmin):
    list_display = (
        "id",
        "listing",
        "loan",
        "buyer_user_id",
        "seller_user_id",
        "current_principal_minor",
        "transfer_price_minor",
        "buyer_total_cost_minor",
        "currency",
        "purchased_at",
    )
    list_filter = ("currency", "loan_status_at_purchase", "risk_acknowledgement_accepted")
    search_fields = ("id", "listing__id", "loan__id", "buyer_user_id", "seller_user_id")
    readonly_fields = tuple(field.name for field in SecondaryMarketPurchase._meta.fields)
