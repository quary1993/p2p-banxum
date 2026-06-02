from __future__ import annotations

from django.contrib import admin

from backend.apps.entities.models import BorrowerDocument, BorrowerEntity, BorrowerEntityEvent


@admin.register(BorrowerEntity)
class BorrowerEntityAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "legal_name",
        "year_founded",
        "entity_type",
        "kyb_status",
        "compliance_hold",
        "country",
    )
    list_filter = ("entity_type", "kyb_status", "compliance_hold", "country")
    search_fields = ("legal_name", "registration_number", "country")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BorrowerDocument)
class BorrowerDocumentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("borrower", "document_type", "display_name", "investor_visible", "created_at")
    list_filter = ("document_type", "investor_visible")
    search_fields = ("borrower__legal_name", "display_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BorrowerEntityEvent)
class BorrowerEntityEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("borrower", "event_type", "actor_user_id", "occurred_at")
    list_filter = ("event_type", "actor_account_type")
    search_fields = ("borrower__legal_name", "actor_user_id", "note")
    readonly_fields = (
        "id",
        "borrower",
        "event_type",
        "actor_user_id",
        "actor_account_type",
        "previous_kyb_status",
        "new_kyb_status",
        "note",
        "evidence_summary",
        "metadata",
        "occurred_at",
    )

    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False
