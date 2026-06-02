from __future__ import annotations

from django.contrib import admin

from backend.apps.ledger.models import (
    BankOperation,
    InvestorBalanceLot,
    LedgerAccount,
    LedgerJournalEntry,
    LedgerPosting,
    ReconciliationSnapshot,
)


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("code", "account_type", "currency", "owner_type", "owner_id", "is_active")
    list_filter = ("account_type", "currency", "is_active")
    search_fields = ("code", "name", "owner_id")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BankOperation)
class BankOperationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "operation_type",
        "status",
        "amount_minor",
        "currency",
        "value_date",
        "bank_reference",
        "confirmed_by_admin_id",
    )
    list_filter = ("operation_type", "status", "currency", "value_date")
    search_fields = ("bank_reference", "payment_reference", "linked_object_id")
    readonly_fields = tuple(field.name for field in BankOperation._meta.fields)

    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(LedgerJournalEntry)
class LedgerJournalEntryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "event_type",
        "direction",
        "gross_amount_minor",
        "currency",
        "booking_date",
        "source_type",
        "source_id",
    )
    list_filter = ("event_type", "direction", "currency", "booking_date")
    search_fields = ("source_id", "bank_reference", "idempotency_key")
    readonly_fields = tuple(field.name for field in LedgerJournalEntry._meta.fields)

    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(LedgerPosting)
class LedgerPostingAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("journal_entry", "account", "side", "amount_minor", "currency")
    list_filter = ("side", "currency", "account__account_type")
    search_fields = ("journal_entry__id", "account__code", "memo")
    readonly_fields = tuple(field.name for field in LedgerPosting._meta.fields)

    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(InvestorBalanceLot)
class InvestorBalanceLotAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "investor_user_id",
        "currency",
        "status",
        "available_amount_minor",
        "received_at",
        "investment_deadline_at",
        "withdrawal_deadline_at",
    )
    list_filter = ("status", "currency", "source_type")
    search_fields = ("investor_user_id", "source_id")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ReconciliationSnapshot)
class ReconciliationSnapshotAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "currency",
        "as_of_date",
        "bank_stated_balance_minor",
        "investor_balance_liability_minor",
        "reconciliation_difference_minor",
        "created_by_admin_id",
    )
    list_filter = ("currency", "as_of_date")
    search_fields = ("created_by_admin_id", "notes")
    readonly_fields = tuple(field.name for field in ReconciliationSnapshot._meta.fields)

    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False
