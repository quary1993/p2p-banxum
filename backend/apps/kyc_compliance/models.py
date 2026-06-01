from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class KycSubjectType(models.TextChoices):
    USER = "user", "User"
    LEGAL_ENTITY_LENDER = "legal_entity_lender", "Legal-entity lender"
    BORROWER = "borrower", "Borrower"


class KycStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    DECLINED = "declined", "Declined"
    MANUAL_REVIEW = "manual_review", "Manual review"
    HIGH_RISK = "high_risk", "High risk"
    SANCTIONS_HIT = "sanctions_hit", "Sanctions hit"
    PEP_HIT = "pep_hit", "PEP hit"
    ADVERSE_MEDIA_HIT = "adverse_media_hit", "Adverse media hit"
    EXPIRED = "expired", "Expired"
    REVERIFICATION_REQUIRED = "reverification_required", "Re-verification required"


BLOCKING_KYC_STATUSES = frozenset(
    {
        KycStatus.NOT_STARTED,
        KycStatus.PENDING,
        KycStatus.DECLINED,
        KycStatus.MANUAL_REVIEW,
        KycStatus.HIGH_RISK,
        KycStatus.SANCTIONS_HIT,
        KycStatus.PEP_HIT,
        KycStatus.ADVERSE_MEDIA_HIT,
        KycStatus.EXPIRED,
        KycStatus.REVERIFICATION_REQUIRED,
    }
)


class KycVerificationCase(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_type = models.CharField(
        max_length=64,
        choices=KycSubjectType.choices,
        default=KycSubjectType.USER,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="kyc_verification_case",
    )
    subject_reference = models.CharField(max_length=128)
    provider = models.CharField(max_length=32, default="didit")
    provider_environment = models.CharField(max_length=32)
    workflow_id = models.CharField(max_length=128, blank=True)
    vendor_data = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=64,
        choices=KycStatus.choices,
        default=KycStatus.NOT_STARTED,
    )
    risk_classification = models.CharField(max_length=64, blank=True)
    detected_flags = models.JSONField(default=list, blank=True)
    provider_session_id = models.CharField(max_length=128, blank=True)
    provider_verification_id = models.CharField(max_length=128, blank=True)
    provider_report_id = models.CharField(max_length=128, blank=True)
    aml_screening_id = models.CharField(max_length=128, blank=True)
    provider_subject_id = models.CharField(max_length=128, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    manual_review_required = models.BooleanField(default=False)
    blocking_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["subject_type", "subject_reference"]),
            models.Index(fields=["status"]),
            models.Index(fields=["provider_session_id"]),
        ]

    @property
    def is_approved(self) -> bool:
        return self.status == KycStatus.APPROVED


class KycProviderSession(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        KycVerificationCase,
        on_delete=models.PROTECT,
        related_name="provider_sessions",
    )
    provider = models.CharField(max_length=32, default="didit")
    provider_environment = models.CharField(max_length=32)
    workflow_id = models.CharField(max_length=128, blank=True)
    provider_session_id = models.CharField(max_length=128, unique=True)
    verification_url = models.URLField(max_length=500)
    vendor_data = models.CharField(max_length=255)
    status = models.CharField(
        max_length=64,
        choices=KycStatus.choices,
        default=KycStatus.PENDING,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["case", "status", "expires_at"]),
            models.Index(fields=["provider_session_id"]),
        ]


class KycProviderEvent(AppendOnlyModel, TimestampedModel):
    case = models.ForeignKey(
        KycVerificationCase,
        on_delete=models.PROTECT,
        related_name="provider_events",
    )
    session = models.ForeignKey(
        KycProviderSession,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="provider_events",
    )
    provider = models.CharField(max_length=32, default="didit")
    provider_environment = models.CharField(max_length=32)
    provider_event_id = models.CharField(max_length=128, unique=True)
    provider_event_type = models.CharField(max_length=128)
    provider_status = models.CharField(max_length=128, blank=True)
    normalized_status = models.CharField(max_length=64, choices=KycStatus.choices)
    provider_session_id = models.CharField(max_length=128, blank=True)
    vendor_data = models.CharField(max_length=255, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField()

    class Meta:
        ordering = ["-processed_at", "-id"]
        indexes = [
            models.Index(fields=["case", "processed_at"]),
            models.Index(fields=["provider_session_id"]),
            models.Index(fields=["normalized_status"]),
        ]
