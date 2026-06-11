from __future__ import annotations

from django.contrib import admin

from backend.apps.documents.models import (
    DocumentAcceptanceEvidence,
    DocumentEvent,
    DocumentRenderedArtifact,
    DocumentTemplate,
    DocumentTemplateVersion,
)


class ReadOnlyDocumentEvidenceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("category", "template_key", "language", "name", "current_published_version")
    list_filter = ("category", "language")
    search_fields = ("template_key", "name", "description")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DocumentTemplateVersion)
class DocumentTemplateVersionAdmin(ReadOnlyDocumentEvidenceAdmin):
    list_display = ("template", "version_number", "status", "title", "content_hash")
    list_filter = ("status", "template__category", "template__language")
    search_fields = ("template__template_key", "title", "body", "content_hash")
    readonly_fields = tuple(field.name for field in DocumentTemplateVersion._meta.fields)


@admin.register(DocumentAcceptanceEvidence)
class DocumentAcceptanceEvidenceAdmin(ReadOnlyDocumentEvidenceAdmin):
    list_display = (
        "user_id",
        "category",
        "context_type",
        "context_id",
        "template_version_number",
        "accepted_at",
    )
    list_filter = ("category", "context_type", "accepted_at")
    search_fields = ("user_id", "context_id", "template_hash", "idempotency_key")
    readonly_fields = tuple(field.name for field in DocumentAcceptanceEvidence._meta.fields)


@admin.register(DocumentEvent)
class DocumentEventAdmin(ReadOnlyDocumentEvidenceAdmin):
    list_display = ("event_type", "category", "actor_user_id", "occurred_at")
    list_filter = ("event_type", "category", "actor_account_type")
    search_fields = ("actor_user_id", "note")
    readonly_fields = tuple(field.name for field in DocumentEvent._meta.fields)


@admin.register(DocumentRenderedArtifact)
class DocumentRenderedArtifactAdmin(ReadOnlyDocumentEvidenceAdmin):
    list_display = (
        "acceptance",
        "output_format",
        "purpose",
        "filename",
        "content_sha256",
        "rendered_at",
    )
    list_filter = ("output_format", "purpose", "rendered_at")
    search_fields = ("user_id", "actor_user_id", "filename", "content_sha256")
    readonly_fields = tuple(field.name for field in DocumentRenderedArtifact._meta.fields)
