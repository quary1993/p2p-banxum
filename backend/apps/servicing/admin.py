from __future__ import annotations

from django.contrib import admin

from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    InvestorLossRecognitionLine,
    InvestorRecoveryDistributionLine,
    InvestorRepaymentDistributionLine,
    LoanRecoveryEvent,
    LoanRiskNote,
    LoanWriteOffEvent,
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


@admin.register(LoanRecoveryEvent)
class LoanRecoveryEventAdmin(ReadOnlyServicingAdmin):
    list_display = (
        "id",
        "loan",
        "currency",
        "gross_recovered_minor",
        "net_received_minor",
        "net_available_for_distribution_minor",
        "recovery_fee_minor",
        "created_by_admin_id",
        "value_date",
    )
    list_filter = ("currency", "recovery_fee_applied", "value_date")
    search_fields = ("id", "loan__title", "borrower_id", "bank_operation__bank_reference")
    readonly_fields = tuple(field.name for field in LoanRecoveryEvent._meta.fields)


@admin.register(InvestorRecoveryDistributionLine)
class InvestorRecoveryDistributionLineAdmin(ReadOnlyServicingAdmin):
    list_display = (
        "id",
        "recovery_event",
        "holding",
        "investor_user_id",
        "amount_minor",
        "principal_minor",
        "contractual_interest_minor",
        "default_interest_minor",
        "currency",
    )
    list_filter = ("currency",)
    search_fields = ("id", "investor_user_id", "recovery_event__id")
    readonly_fields = tuple(field.name for field in InvestorRecoveryDistributionLine._meta.fields)


@admin.register(LoanRiskNote)
class LoanRiskNoteAdmin(ReadOnlyServicingAdmin):
    list_display = (
        "id",
        "loan",
        "visibility",
        "note_type",
        "title",
        "created_by_admin_id",
        "occurred_at",
    )
    list_filter = ("visibility", "note_type")
    search_fields = ("id", "loan__title", "borrower_id", "title", "body")
    readonly_fields = tuple(field.name for field in LoanRiskNote._meta.fields)


@admin.register(LoanWriteOffEvent)
class LoanWriteOffEventAdmin(ReadOnlyServicingAdmin):
    list_display = (
        "id",
        "loan",
        "currency",
        "total_written_off_minor",
        "previous_loan_status",
        "new_loan_status",
        "created_by_admin_id",
        "written_off_at",
    )
    list_filter = ("currency", "previous_loan_status", "new_loan_status")
    search_fields = ("id", "loan__title", "borrower_id", "reason", "evidence_reference")
    readonly_fields = tuple(field.name for field in LoanWriteOffEvent._meta.fields)


@admin.register(InvestorLossRecognitionLine)
class InvestorLossRecognitionLineAdmin(ReadOnlyServicingAdmin):
    list_display = (
        "write_off_event",
        "investor_user_id",
        "currency",
        "principal_loss_minor",
        "total_loss_minor",
        "occurred_at",
    )
    list_filter = ("currency", "occurred_at")
    search_fields = ("id", "investor_user_id", "write_off_event__id")
    readonly_fields = tuple(field.name for field in InvestorLossRecognitionLine._meta.fields)
