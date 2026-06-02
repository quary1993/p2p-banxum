from __future__ import annotations

from django.contrib import admin

from backend.apps.loans.models import Loan, LoanEvent, LoanInstallment


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "title",
        "borrower",
        "status",
        "principal_minor",
        "currency",
        "interest_rate_bps",
        "term_months",
        "funding_deadline",
    )
    list_filter = ("status", "currency", "purpose", "repayment_type", "risk_rating")
    search_fields = ("title", "borrower__legal_name")
    readonly_fields = ("id", "created_at", "updated_at", "published_at")


@admin.register(LoanInstallment)
class LoanInstallmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "loan",
        "schedule_version",
        "installment_number",
        "due_date",
        "principal_minor",
        "interest_minor",
        "total_minor",
        "admin_overridden",
    )
    list_filter = ("schedule_version", "admin_overridden", "due_date")
    search_fields = ("loan__title",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(LoanEvent)
class LoanEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("loan", "event_type", "actor_user_id", "occurred_at")
    list_filter = ("event_type", "actor_account_type")
    search_fields = ("loan__title", "actor_user_id", "note")
    readonly_fields = (
        "id",
        "loan",
        "event_type",
        "actor_user_id",
        "actor_account_type",
        "previous_status",
        "new_status",
        "note",
        "metadata",
        "occurred_at",
    )

    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False
