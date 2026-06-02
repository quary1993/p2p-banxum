from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel
from backend.apps.platform_core.models.files import StoredFile


class BorrowerEntityType(models.TextChoices):
    SWISS_COMPANY = "swiss_company", "Swiss company"
    NON_SWISS_COMPANY = "non_swiss_company", "Non-Swiss company"
    REAL_ESTATE_PROJECT_COMPANY = "real_estate_project_company", "Real estate project company"
    SPECIAL_PURPOSE_VEHICLE = "special_purpose_vehicle", "Special purpose vehicle"
    OTHER = "other", "Other"


class BorrowerKybStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    DECLINED = "declined", "Declined"
    MANUAL_REVIEW = "manual_review", "Manual review"
    EXPIRED = "expired", "Expired"
    REVERIFICATION_REQUIRED = "reverification_required", "Re-verification required"


class BorrowerDocumentType(models.TextChoices):
    PRESENTATION = "presentation", "Borrower presentation"
    FINANCIALS = "financials", "Financial PDF"
    KYB_EVIDENCE = "kyb_evidence", "KYB/AML evidence"
    GENERIC = "generic", "Generic borrower document"
    OTHER = "other", "Other"


class BorrowerEntityEventType(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    KYB_STATUS_CHANGED = "kyb_status_changed", "KYB status changed"
    DOCUMENT_ADDED = "document_added", "Document added"


class BorrowerEntity(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_name = models.CharField(max_length=255)
    year_founded = models.PositiveSmallIntegerField()
    entity_type = models.CharField(
        max_length=64,
        choices=BorrowerEntityType.choices,
        default=BorrowerEntityType.SWISS_COMPANY,
    )
    kyb_status = models.CharField(
        max_length=32,
        choices=BorrowerKybStatus.choices,
        default=BorrowerKybStatus.PENDING,
    )
    compliance_hold = models.BooleanField(default=False)
    country = models.CharField(max_length=64, blank=True)
    registration_number = models.CharField(max_length=128, blank=True)
    registered_address = models.TextField(blank=True)
    operating_address = models.TextField(blank=True)
    industry_activity = models.TextField(blank=True)
    ownership_structure = models.TextField(blank=True)
    beneficial_owners = models.JSONField(default=list, blank=True)
    directors_officers = models.JSONField(default=list, blank=True)
    authorized_signatories = models.JSONField(default=list, blank=True)
    bank_account_details = models.JSONField(default=dict, blank=True)
    financials_currency = models.CharField(max_length=3, blank=True)
    assets_minor = models.BigIntegerField(null=True, blank=True)
    liabilities_minor = models.BigIntegerField(null=True, blank=True)
    revenue_last_year_minor = models.BigIntegerField(null=True, blank=True)
    profit_last_year_minor = models.BigIntegerField(null=True, blank=True)
    created_by_admin_id = models.UUIDField()
    updated_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["legal_name", "id"]
        indexes = [
            models.Index(fields=["legal_name"]),
            models.Index(fields=["kyb_status", "compliance_hold"]),
            models.Index(fields=["country"]),
            models.Index(fields=["entity_type"]),
        ]

    @property
    def can_transact(self) -> bool:
        return self.kyb_status == BorrowerKybStatus.APPROVED and not self.compliance_hold

    def __str__(self) -> str:
        return self.legal_name


class BorrowerDocument(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(
        BorrowerEntity,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    document_type = models.CharField(max_length=64, choices=BorrowerDocumentType.choices)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    stored_file = models.ForeignKey(
        StoredFile,
        on_delete=models.PROTECT,
        related_name="borrower_documents",
    )
    investor_visible = models.BooleanField(default=False)
    created_by_admin_id = models.UUIDField()
    created_by_account_type = models.CharField(max_length=64)

    class Meta:
        ordering = ["document_type", "display_name", "id"]
        indexes = [
            models.Index(fields=["borrower", "document_type"]),
            models.Index(fields=["borrower", "investor_visible"]),
        ]


class BorrowerEntityEvent(AppendOnlyModel):
    borrower = models.ForeignKey(
        BorrowerEntity,
        on_delete=models.PROTECT,
        related_name="events",
    )
    event_type = models.CharField(max_length=32, choices=BorrowerEntityEventType.choices)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    previous_kyb_status = models.CharField(max_length=32, blank=True)
    new_kyb_status = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    evidence_summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["borrower", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]
