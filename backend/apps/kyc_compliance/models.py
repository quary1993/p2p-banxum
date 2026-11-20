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


class KycManualReviewDecisionType(models.TextChoices):
    APPROVE = "approve", "Approve"
    DECLINE = "decline", "Decline"
    REQUEST_REVERIFICATION = "request_reverification", "Request re-verification"
    REOPEN = "reopen", "Reopen manual review"


class KycManualReviewReason(models.TextChoices):
    PEP_REVIEW = "pep_review", "PEP review"
    HIGH_RISK_REVIEW = "high_risk_review", "High-risk review"
    ADVERSE_MEDIA_REVIEW = "adverse_media_review", "Adverse-media review"
    SANCTIONS_REVIEW = "sanctions_review", "Sanctions review"
    PROVIDER_DECLINE_REVIEW = "provider_decline_review", "Provider decline review"
    INCONCLUSIVE_PROVIDER_RESULT = "inconclusive_provider_result", "Inconclusive provider result"
    DOCUMENT_OR_IDENTITY_ISSUE = "document_or_identity_issue", "Document or identity issue"
    REVERIFICATION_REQUIRED = "reverification_required", "Re-verification required"
    OFF_PLATFORM_REVIEW = "off_platform_review", "Off-platform review"
    ADMIN_CORRECTION = "admin_correction", "Admin correction"
    OTHER = "other", "Other"


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
    # 18.3 (U33-DEC-26, Vlad E-08): verified personal data from the Didit decision, when Didit
    # provides it. Shown read-only to the investor; only the team changes it.
    verified_address = models.TextField(blank=True)
    verified_birth_date = models.DateField(null=True, blank=True)
    verified_nationality = models.CharField(max_length=3, blank=True)
    # Audit S3-6 (U33-DEC-05): the legal name on the identity document, from the Didit decision.
    # The registration name (User.full_name) is typed by the investor and is not this evidence.
    verified_full_name = models.CharField(max_length=255, blank=True)

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


class KycSessionPurpose(models.TextChoices):
    KYC = "kyc", "Identity verification"
    # Audit S4-4: a new identity check for an assisted account recovery. Its results are
    # evidence for that recovery only; they never change the KYC case.
    ACCOUNT_RECOVERY = "account_recovery", "Account recovery identity check"


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
    # Set when an admin KYC decision is recorded: results that arrive later for this session
    # are kept as evidence but can no longer change the case.
    superseded_at = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(
        max_length=32, choices=KycSessionPurpose.choices, default=KycSessionPurpose.KYC
    )
    # For an account-recovery check: the id of the recovery case that asked for it.
    recovery_reference = models.CharField(max_length=64, blank=True)

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


class KycManualReviewDecision(AppendOnlyModel, TimestampedModel):
    case = models.ForeignKey(
        KycVerificationCase,
        on_delete=models.PROTECT,
        related_name="manual_review_decisions",
    )
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    decision = models.CharField(max_length=64, choices=KycManualReviewDecisionType.choices)
    reason_code = models.CharField(
        max_length=64,
        choices=KycManualReviewReason.choices,
        default=KycManualReviewReason.OTHER,
    )
    previous_status = models.CharField(max_length=64, choices=KycStatus.choices)
    new_status = models.CharField(max_length=64, choices=KycStatus.choices)
    note = models.TextField(blank=True)
    evidence_summary = models.TextField(blank=True)
    decided_at = models.DateTimeField()

    class Meta:
        ordering = ["-decided_at", "-id"]
        indexes = [
            models.Index(fields=["case", "decided_at"]),
            models.Index(fields=["actor_user_id", "decided_at"]),
            models.Index(fields=["decision"]),
            models.Index(fields=["new_status"]),
        ]


# 18.10 (Q12, U33-DEC-27): self-declarations, compliance reviews and re-verification dates.


class InvestorDeclaration(AppendOnlyModel, TimestampedModel):
    """One submitted declaration; a new submission is a new version (never edited)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="declarations"
    )
    version = models.PositiveIntegerField()
    subject_type = models.CharField(max_length=16, default="person")
    beneficial_owner_is_self = models.BooleanField()
    beneficial_owner_name = models.CharField(max_length=255, blank=True)
    sources_of_funds = models.JSONField(default=list)
    savings_origin = models.CharField(max_length=500, blank=True)
    source_other_text = models.CharField(max_length=500, blank=True)
    pep_status = models.CharField(max_length=16)
    pep_person = models.CharField(max_length=255, blank=True)
    pep_relation = models.CharField(max_length=255, blank=True)
    pep_function = models.CharField(max_length=255, blank=True)
    pep_country = models.CharField(max_length=64, blank=True)
    yearly_volume_band = models.CharField(max_length=16)
    company_details = models.JSONField(default=dict, blank=True)
    review_triggers = models.JSONField(default=list, blank=True)
    submitted_at = models.DateTimeField()

    class Meta:
        ordering = ["-submitted_at", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["user", "version"], name="kyc_declaration_version")
        ]
        indexes = [models.Index(fields=["user", "submitted_at"])]


class ComplianceReviewStatus(models.TextChoices):
    OPEN = "open", "Open"
    MORE_INFORMATION = "more_information", "More information requested"
    CLOSED = "closed", "Closed"


class ComplianceReview(TimestampedModel):
    """A compliance analysis of an investor (not a refusal). A necessary open review blocks new
    investments, reservations and resale purchases."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="compliance_reviews"
    )
    declaration = models.ForeignKey(
        InvestorDeclaration, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    triggers = models.JSONField(default=list, blank=True)
    necessary = models.BooleanField(default=True)
    status = models.CharField(
        max_length=24, choices=ComplianceReviewStatus.choices, default=ComplianceReviewStatus.OPEN
    )
    opened_reason = models.CharField(max_length=500, blank=True)
    opened_by_user_id = models.UUIDField(null=True, blank=True)
    assigned_to_user_id = models.UUIDField(null=True, blank=True)
    investor_message = models.TextField(blank=True)
    outcome_note = models.TextField(blank=True)
    closed_by_user_id = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"]), models.Index(fields=["status"])]


class InvestorReverification(TimestampedModel):
    """The re-verification date set by compliance for one investor (the current one is the open
    row; a completed or replaced date is closed and kept)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reverifications"
    )
    due_date = models.DateField()
    reason = models.CharField(max_length=500, blank=True)
    set_by_user_id = models.UUIDField()
    notices_sent = models.JSONField(default=list, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by_user_id = models.UUIDField(null=True, blank=True)
    replaced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "completed_at", "replaced_at"])]
