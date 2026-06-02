from __future__ import annotations

from django.contrib import admin

from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    InvestorRepaymentDistributionLine,
)


class ReadOnlyServicingAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def has_add_permission(self, request):  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(BorrowerRepaymentEvent)
class BorrowerRepaymentEventAdmin(ReadOnlyServicingAdmin):
    list_display = (
        "id",
        "loan",
        "installment",
        "event_type",
        "amount_minor",
        "currency",
        "value_date",
        "created_by_admin_id",
    )
    list_filter = ("event_type", "currency", "value_date")
    search_fields = ("id", "loan__title", "bank_operation__bank_reference")
    readonly_fields = tuple(field.name for field in BorrowerRepaymentEvent._meta.fields)


@admin.register(InvestorRepaymentDistributionLine)
class InvestorRepaymentDistributionLineAdmin(ReadOnlyServicingAdmin):
    list_display = (
        "id",
        "repayment_event",
        "holding",
        "investor_user_id",
        "amount_minor",
        "principal_minor",
        "interest_minor",
        "currency",
    )
    list_filter = ("currency",)
    search_fields = ("id", "investor_user_id", "repayment_event__id")
    readonly_fields = tuple(field.name for field in InvestorRepaymentDistributionLine._meta.fields)
