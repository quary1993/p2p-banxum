from __future__ import annotations

from django.contrib import admin

from backend.apps.holdings.models import InvestorLoanHolding, InvestorLoanHoldingEvent


class ReadOnlyHoldingsAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(InvestorLoanHolding)
class InvestorLoanHoldingAdmin(ReadOnlyHoldingsAdmin):
    list_display = (
        "id",
        "loan_id",
        "investor_user_id",
        "status",
        "original_principal_minor",
        "current_principal_minor",
        "currency",
        "source_type",
    )
    list_filter = ("status", "currency", "source_type")
    search_fields = ("id", "loan_id", "investor_user_id", "source_id", "idempotency_key")
    readonly_fields = tuple(field.name for field in InvestorLoanHolding._meta.fields)


@admin.register(InvestorLoanHoldingEvent)
class InvestorLoanHoldingEventAdmin(ReadOnlyHoldingsAdmin):
    list_display = (
        "id",
        "holding_id",
        "loan_id",
        "investor_user_id",
        "event_type",
        "occurred_at",
    )
    list_filter = ("event_type",)
    search_fields = ("id", "holding_id", "loan_id", "investor_user_id")
    readonly_fields = tuple(field.name for field in InvestorLoanHoldingEvent._meta.fields)
