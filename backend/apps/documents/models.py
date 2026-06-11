from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class DocumentCategory(models.TextChoices):
    REGISTRATION = "registration", "Registration terms"
    PRIMARY_MARKET_INVESTMENT = "primary_market_investment", "Primary-market investment"
    SECONDARY_MARKET_PURCHASE = "secondary_market_purchase", "Secondary-market purchase"
    SECONDARY_MARKET_LISTING = "secondary_market_listing", "Secondary-market listing"


class DocumentTemplateVersionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"


class DocumentEventType(models.TextChoices):
    TEMPLATE_CREATED = "template_created", "Template created"
    VERSION_CREATED = "version_created", "Version created"
    VERSION_PUBLISHED = "version_published", "Version published"
    ACCEPTED = "accepted", "Accepted"
    ARTIFACT_RENDERED = "artifact_rendered", "Artifact rendered"


class DocumentArtifactOutputFormat(models.TextChoices):
    PDF = "pdf", "PDF"
    CSV = "csv", "CSV"


class DocumentArtifactPurpose(models.TextChoices):
    INVESTOR_DOWNLOAD = "investor_download", "Investor download"
    ADMIN_DOWNLOAD = "admin_download", "Admin download"
    EMAIL_DELIVERY = "email_delivery", "Email delivery"
    EVIDENCE_EXPORT = "evidence_export", "Evidence export"


class DocumentTemplate(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=64, choices=DocumentCategory.choices)
    template_key = models.CharField(max_length=128, default="default")
    language = models.CharField(max_length=8, default="en")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    current_published_version = models.ForeignKey(
        "documents.DocumentTemplateVersion",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    created_by_superadmin_id = models.UUIDField()
    updated_by_superadmin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["category", "template_key", "language"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "template_key", "language"],
                name="unique_document_template_identity",
            ),
        ]
        indexes = [
            models.Index(fields=["category", "template_key", "language"]),
        ]

    def __str__(self) -> str:
        return f"{self.category}:{self.template_key}:{self.language}"


class DocumentTemplateVersion(AppendOnlyModel, TimestampedModel):
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=32,
        choices=DocumentTemplateVersionStatus.choices,
        default=DocumentTemplateVersionStatus.DRAFT,
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    checkbox_labels = models.JSONField(default=list, blank=True)
    variable_schema = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64)
    created_by_superadmin_id = models.UUIDField()
    source_version_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    legal_review_reference = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["template", "version_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version_number"],
                name="unique_document_template_version_number",
            ),
        ]
        indexes = [
            models.Index(fields=["template", "status"]),
            models.Index(fields=["content_hash"]),
            models.Index(fields=["created_at"]),
        ]


class DocumentAcceptanceEvidence(AppendOnlyModel, TimestampedModel):
    user_id = models.UUIDField()
    category = models.CharField(max_length=64, choices=DocumentCategory.choices)
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.PROTECT,
        related_name="acceptances",
    )
    template_version = models.ForeignKey(
        DocumentTemplateVersion,
        on_delete=models.PROTECT,
        related_name="acceptances",
    )
    template_version_number = models.PositiveIntegerField()
    template_hash = models.CharField(max_length=64)
    context_type = models.CharField(max_length=64)
    context_id = models.CharField(max_length=128)
    accepted_checkbox_labels = models.JSONField(default=list, blank=True)
    data_snapshot = models.JSONField(default=dict, blank=True)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-accepted_at", "-id"]
        indexes = [
            models.Index(fields=["user_id", "category", "accepted_at"]),
            models.Index(fields=["context_type", "context_id"]),
            models.Index(fields=["template_version"]),
        ]


class DocumentRenderedArtifact(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    acceptance = models.ForeignKey(
        DocumentAcceptanceEvidence,
        on_delete=models.PROTECT,
        related_name="rendered_artifacts",
    )
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.PROTECT,
        related_name="rendered_artifacts",
    )
    template_version = models.ForeignKey(
        DocumentTemplateVersion,
        on_delete=models.PROTECT,
        related_name="rendered_artifacts",
    )
    user_id = models.UUIDField()
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    output_format = models.CharField(max_length=16, choices=DocumentArtifactOutputFormat.choices)
    purpose = models.CharField(
        max_length=64,
        choices=DocumentArtifactPurpose.choices,
        default=DocumentArtifactPurpose.INVESTOR_DOWNLOAD,
    )
    content_type = models.CharField(max_length=128)
    content_encoding = models.CharField(max_length=32)
    filename = models.CharField(max_length=255)
    content_sha256 = models.CharField(max_length=64)
    manifest = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    rendered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-rendered_at", "-id"]
        indexes = [
            models.Index(
                fields=["acceptance", "rendered_at"],
                name="documents_d_accept_2469d9_idx",
            ),
            models.Index(
                fields=["user_id", "rendered_at"],
                name="documents_d_user_id_4467dd_idx",
            ),
            models.Index(
                fields=["content_sha256"],
                name="documents_d_content_413215_idx",
            ),
            models.Index(
                fields=["purpose", "rendered_at"],
                name="documents_d_purpose_82a1f2_idx",
            ),
        ]


class DocumentEvent(AppendOnlyModel):
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
    )
    template_version = models.ForeignKey(
        DocumentTemplateVersion,
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
    )
    category = models.CharField(max_length=64, choices=DocumentCategory.choices, blank=True)
    event_type = models.CharField(max_length=64, choices=DocumentEventType.choices)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["template", "occurred_at"]),
            models.Index(fields=["template_version", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]
