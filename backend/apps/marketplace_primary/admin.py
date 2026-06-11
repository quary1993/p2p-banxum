from __future__ import annotations

from django.contrib import admin

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryInvestmentOrderEvent,
    PrimaryLoanCancellation,
    PrimaryLoanClose,
)


class ReadOnlyPrimaryMarketplaceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(PrimaryInvestmentOrder)
class PrimaryInvestmentOrderAdmin(ReadOnlyPrimaryMarketplaceAdmin):
    list_display = (
        "id",
        "loan_id",
        "investor_user_id",
        "status",
        "requested_amount_minor",
        "allocated_amount_minor",
        "currency",
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = ("id", "loan_id", "investor_user_id", "idempotency_key")
    readonly_fields = tuple(field.name for field in PrimaryInvestmentOrder._meta.fields)


@admin.register(PrimaryInvestmentOrderEvent)
class PrimaryInvestmentOrderEventAdmin(ReadOnlyPrimaryMarketplaceAdmin):
    list_display = ("id", "order_id", "loan_id", "event_type", "actor_user_id", "occurred_at")
    list_filter = ("event_type",)
    search_fields = ("id", "order_id", "loan_id", "actor_user_id")
    readonly_fields = tuple(field.name for field in PrimaryInvestmentOrderEvent._meta.fields)


@admin.register(PrimaryLoanClose)
class PrimaryLoanCloseAdmin(ReadOnlyPrimaryMarketplaceAdmin):
    list_display = (
        "id",
        "loan_id",
        "close_type",
        "accepted_principal_minor",
        "currency",
        "borrower_success_fee_minor",
        "borrower_disbursement_payable_minor",
        "closed_at",
    )
    list_filter = ("close_type", "currency", "closed_at")
    search_fields = ("id", "loan_id", "idempotency_key")
    readonly_fields = tuple(field.name for field in PrimaryLoanClose._meta.fields)


@admin.register(PrimaryLoanCancellation)
class PrimaryLoanCancellationAdmin(ReadOnlyPrimaryMarketplaceAdmin):
    list_display = (
        "id",
        "loan_id",
        "currency",
        "released_order_count",
        "closed_not_invested_order_count",
        "released_principal_minor",
        "cancelled_at",
    )
    list_filter = ("currency", "cancelled_at")
    search_fields = ("id", "loan_id", "idempotency_key")
    readonly_fields = tuple(field.name for field in PrimaryLoanCancellation._meta.fields)
