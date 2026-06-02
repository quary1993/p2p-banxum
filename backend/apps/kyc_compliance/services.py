from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.utils import timezone

from backend.apps.kyc_compliance.models import (
    KycManualReviewDecision,
    KycManualReviewDecisionType,
    KycManualReviewReason,
    KycProviderEvent,
    KycProviderSession,
    KycStatus,
    KycVerificationCase,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    record_domain_event,
)

TERMINAL_DECISION_STATUSES = frozenset(
    {
        KycStatus.APPROVED,
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

MANUAL_REVIEW_STATUSES = frozenset(
    {
        KycStatus.MANUAL_REVIEW,
        KycStatus.HIGH_RISK,
        KycStatus.PEP_HIT,
        KycStatus.ADVERSE_MEDIA_HIT,
    }
)

ADMIN_REVIEW_REQUIRED_STATUSES = frozenset(
    {
        KycStatus.DECLINED,
        KycStatus.MANUAL_REVIEW,
        KycStatus.HIGH_RISK,
        KycStatus.SANCTIONS_HIT,
        KycStatus.PEP_HIT,
        KycStatus.ADVERSE_MEDIA_HIT,
        KycStatus.REVERIFICATION_REQUIRED,
    }
)

NON_OVERRIDABLE_APPROVAL_STATUSES = frozenset(
    {
        KycStatus.SANCTIONS_HIT,
        KycStatus.DECLINED,
    }
)

BLOCKING_ACCOUNT_STATUSES = frozenset({"restricted", "locked", "closed"})


class KycComplianceError(ValueError):
    pass


class KycWebhookSignatureError(KycComplianceError):
    pass


class KycWebhookMatchError(KycComplianceError):
    pass


class KycManualReviewError(KycComplianceError):
    pass


@dataclass(frozen=True, slots=True)
class CreateKycSessionCommand:
    user: Model
    workflow_id: str | None = None
    ttl: timedelta = timedelta(minutes=30)
    force_new: bool = False


@dataclass(frozen=True, slots=True)
class KycSessionResult:
    case: KycVerificationCase
    session: KycProviderSession | None = None
    already_approved: bool = False


@dataclass(frozen=True, slots=True)
class ProviderKycEventCommand:
    provider_event_id: str
    provider_event_type: str
    provider_status: str
    provider_session_id: str = ""
    vendor_data: str = ""
    verification_id: str = ""
    report_id: str = ""
    aml_screening_id: str = ""
    provider_subject_id: str = ""
    risk_classification: str = ""
    detected_flags: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderKycEventResult:
    event: KycProviderEvent
    case: KycVerificationCase
    idempotent: bool = False


@dataclass(frozen=True, slots=True)
class ManualReviewDecisionCommand:
    actor: Model
    case_id: str
    decision: KycManualReviewDecisionType
    reason_code: KycManualReviewReason
    note: str = ""
    evidence_summary: str = ""


def user_subject_reference(user: Model) -> str:
    return f"user:{user.pk}"


def vendor_data_for_user(user: Model) -> str:
    return user_subject_reference(user)


def _user_actor(user_id: str) -> ActorRef:
    return ActorRef("investor", user_id)


def _actor_for_admin(user: Model) -> ActorRef:
    account_type = str(getattr(user, "account_type", ""))
    if account_type == "superadmin":
        return ActorRef("superadmin", str(user.pk))
    return ActorRef("admin", str(user.pk))


def _is_admin_actor(user: Model) -> bool:
    account_type = str(getattr(user, "account_type", ""))
    status = str(getattr(user, "status", ""))
    return (
        bool(getattr(user, "is_active", False))
        and bool(getattr(user, "is_staff", False))
        and account_type in {"admin", "superadmin"}
        and status not in BLOCKING_ACCOUNT_STATUSES
    )


def _provider_environment() -> str:
    return str(settings.DIDIT_ENVIRONMENT)


def _workflow_id(override: str | None = None) -> str:
    return override or str(settings.DIDIT_WORKFLOW_ID)


def get_or_create_user_kyc_case(user: Model) -> KycVerificationCase:
    subject_reference = user_subject_reference(user)
    case, _created = KycVerificationCase.objects.get_or_create(
        user_id=user.pk,
        defaults={
            "subject_reference": subject_reference,
            "provider_environment": _provider_environment(),
            "workflow_id": _workflow_id(),
            "vendor_data": subject_reference,
        },
    )
    return case


def latest_active_session(case: KycVerificationCase) -> KycProviderSession | None:
    now = timezone.now()
    return (
        KycProviderSession.objects.filter(
            case=case,
            status=KycStatus.PENDING,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )


@transaction.atomic
def create_kyc_session(command: CreateKycSessionCommand) -> KycSessionResult:
    case = get_or_create_user_kyc_case(command.user)
    if case.status == KycStatus.APPROVED and not command.force_new:
        return KycSessionResult(case=case, already_approved=True)

    if not command.force_new:
        existing = latest_active_session(case)
        if existing is not None:
            return KycSessionResult(case=case, session=existing)

    now = timezone.now()
    provider_session_id = f"didit_mock_{uuid.uuid4()}"
    workflow_id = _workflow_id(command.workflow_id)
    verification_url = (
        f"{settings.DIDIT_MOCK_VERIFICATION_BASE_URL.rstrip('/')}/{provider_session_id}"
    )
    vendor_data = vendor_data_for_user(command.user)
    session = KycProviderSession.objects.create(
        case=case,
        provider_environment=_provider_environment(),
        workflow_id=workflow_id,
        provider_session_id=provider_session_id,
        verification_url=verification_url,
        vendor_data=vendor_data,
        expires_at=now + command.ttl,
        provider_payload={
            "mode": "mock",
            "user_id": str(command.user.pk),
            "email_present": bool(getattr(command.user, "email", "")),
        },
    )
    case.status = KycStatus.PENDING
    case.provider_environment = session.provider_environment
    case.workflow_id = workflow_id
    case.vendor_data = vendor_data
    case.provider_session_id = provider_session_id
    case.manual_review_required = False
    case.blocking_reason = ""
    case.save(
        update_fields=[
            "status",
            "provider_environment",
            "workflow_id",
            "vendor_data",
            "provider_session_id",
            "manual_review_required",
            "blocking_reason",
            "updated_at",
        ]
    )
    user_id = str(command.user.pk)
    record_audit_event(
        AuditCommand(
            actor=_user_actor(user_id),
            action="kyc.session_created",
            target_type="KycVerificationCase",
            target_id=str(case.id),
            metadata={"provider": "didit", "provider_session_id": provider_session_id},
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="KycSessionCreated",
            aggregate_type="KycVerificationCase",
            aggregate_id=str(case.id),
            payload={"user_id": user_id, "provider_session_id": provider_session_id},
            idempotency_key=f"kyc:{case.id}:session:{session.id}:created",
        )
    )
    return KycSessionResult(case=case, session=session)


def normalize_didit_status(
    *,
    provider_status: str,
    detected_flags: list[str] | None = None,
    risk_classification: str = "",
) -> KycStatus:
    status = provider_status.strip().lower().replace("-", "_").replace(" ", "_")
    flags = {
        flag.strip().lower().replace("-", "_").replace(" ", "_")
        for flag in detected_flags or []
    }
    risk = risk_classification.strip().lower()

    if "sanctions" in flags or "sanctions_hit" in flags:
        return KycStatus.SANCTIONS_HIT
    if "identity_fraud" in flags or "document_fraud" in flags or "confirmed_fraud" in flags:
        return KycStatus.DECLINED
    if "pep" in flags or "pep_hit" in flags:
        return KycStatus.PEP_HIT
    if "adverse_media" in flags or "adverse_media_hit" in flags:
        return KycStatus.ADVERSE_MEDIA_HIT
    if risk in {"high", "high_risk"}:
        return KycStatus.HIGH_RISK

    if status in {
        "not_started",
        "created",
        "session_created",
        "in_progress",
        "queued",
        "processing",
        "pending",
    }:
        return KycStatus.PENDING
    if status in {"approved", "verified", "clear", "completed", "success"}:
        return KycStatus.APPROVED
    if status in {"declined", "rejected", "failed", "blocked"}:
        return KycStatus.DECLINED
    if status in {
        "review_required",
        "manual_review",
        "in_review",
        "inconclusive",
        "ambiguous",
        "unable_to_verify",
    }:
        return KycStatus.MANUAL_REVIEW
    if status in {"expired", "session_expired", "document_expired", "abandoned"}:
        return KycStatus.EXPIRED
    if status in {
        "kyc_expired",
        "reverification_required",
        "re_verification_required",
        "recheck_required",
    }:
        return KycStatus.REVERIFICATION_REQUIRED
    return KycStatus.MANUAL_REVIEW


def _extract_user_id_from_vendor_data(vendor_data: str) -> str:
    prefix = "user:"
    if vendor_data.startswith(prefix):
        return vendor_data[len(prefix) :]
    return ""


def _case_from_event_command(
    command: ProviderKycEventCommand,
) -> tuple[KycVerificationCase, KycProviderSession | None]:
    session = None
    if command.provider_session_id:
        session = KycProviderSession.objects.filter(
            provider_session_id=command.provider_session_id
        ).select_related("case").first()
    if session is not None:
        return session.case, session

    user_id = _extract_user_id_from_vendor_data(command.vendor_data)
    if not user_id:
        raise KycWebhookMatchError("Didit webhook cannot be matched to a platform user.")

    user_model = get_user_model()
    user = user_model.objects.filter(pk=user_id).first()
    if user is None:
        raise KycWebhookMatchError("Didit webhook references an unknown platform user.")
    case = get_or_create_user_kyc_case(user)
    return case, None


def _activate_user_after_kyc_approval(case: KycVerificationCase, actor: ActorRef) -> None:
    user = case.user
    if user is None:
        return
    if str(getattr(user, "status", "")) != "pending_kyc":
        return
    user.status = "active"
    user.save(update_fields=["status"])
    record_audit_event(
        AuditCommand(
            actor=actor,
            action="account.activated_after_kyc",
            target_type="User",
            target_id=str(user.pk),
            metadata={"kyc_case_id": str(case.id)},
        )
    )


@transaction.atomic
def process_didit_event(command: ProviderKycEventCommand) -> ProviderKycEventResult:
    existing = KycProviderEvent.objects.filter(
        provider_event_id=command.provider_event_id
    ).select_related("case").first()
    if existing is not None:
        return ProviderKycEventResult(event=existing, case=existing.case, idempotent=True)

    case, session = _case_from_event_command(command)
    normalized_status = normalize_didit_status(
        provider_status=command.provider_status,
        detected_flags=command.detected_flags,
        risk_classification=command.risk_classification,
    )
    now = timezone.now()
    try:
        event = KycProviderEvent.objects.create(
            case=case,
            session=session,
            provider_environment=_provider_environment(),
            provider_event_id=command.provider_event_id,
            provider_event_type=command.provider_event_type,
            provider_status=command.provider_status,
            normalized_status=normalized_status,
            provider_session_id=command.provider_session_id,
            vendor_data=command.vendor_data,
            raw_payload=command.raw_payload,
            processed_at=now,
        )
    except IntegrityError:
        existing = KycProviderEvent.objects.get(provider_event_id=command.provider_event_id)
        return ProviderKycEventResult(event=existing, case=existing.case, idempotent=True)

    case.status = normalized_status
    case.risk_classification = command.risk_classification
    case.detected_flags = command.detected_flags
    case.provider_verification_id = command.verification_id
    case.provider_report_id = command.report_id
    case.aml_screening_id = command.aml_screening_id
    case.provider_subject_id = command.provider_subject_id
    case.manual_review_required = normalized_status in ADMIN_REVIEW_REQUIRED_STATUSES
    case.blocking_reason = "" if normalized_status == KycStatus.APPROVED else normalized_status
    if command.provider_session_id:
        case.provider_session_id = command.provider_session_id
    if normalized_status in TERMINAL_DECISION_STATUSES:
        case.decision_at = now
    case.save(
        update_fields=[
            "status",
            "risk_classification",
            "detected_flags",
            "provider_verification_id",
            "provider_report_id",
            "aml_screening_id",
            "provider_subject_id",
            "manual_review_required",
            "blocking_reason",
            "provider_session_id",
            "decision_at",
            "updated_at",
        ]
    )
    if session is not None:
        session.status = normalized_status
        session.save(update_fields=["status", "updated_at"])
    if normalized_status == KycStatus.APPROVED:
        _activate_user_after_kyc_approval(case, ActorRef.system())

    record_audit_event(
        AuditCommand(
            actor=ActorRef.system(),
            action="kyc.didit_event_processed",
            target_type="KycVerificationCase",
            target_id=str(case.id),
            metadata={
                "provider_event_id": command.provider_event_id,
                "provider_status": command.provider_status,
                "normalized_status": normalized_status,
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="KycStatusChanged",
            aggregate_type="KycVerificationCase",
            aggregate_id=str(case.id),
            payload={"status": normalized_status, "provider_event_id": command.provider_event_id},
            idempotency_key=f"kyc:{case.id}:provider-event:{command.provider_event_id}:status",
        )
    )
    return ProviderKycEventResult(event=event, case=case)


@transaction.atomic
def record_manual_review_decision(
    command: ManualReviewDecisionCommand,
) -> KycManualReviewDecision:
    if not _is_admin_actor(command.actor):
        raise KycManualReviewError("Only an active admin can record KYC manual review decisions.")
    if not command.note.strip() and not command.evidence_summary.strip():
        raise KycManualReviewError("A note or evidence summary is required.")

    case = KycVerificationCase.objects.select_for_update().filter(id=command.case_id).first()
    if case is None:
        raise KycManualReviewError("KYC case does not exist.")

    previous_status = KycStatus(case.status)
    if (
        command.decision == KycManualReviewDecisionType.APPROVE
        and previous_status in NON_OVERRIDABLE_APPROVAL_STATUSES
    ):
        raise KycManualReviewError("This KYC status cannot be manually approved.")

    new_status = _manual_review_target_status(command.decision)
    now = timezone.now()
    case.status = new_status
    case.manual_review_required = new_status == KycStatus.MANUAL_REVIEW
    case.blocking_reason = "" if new_status == KycStatus.APPROVED else command.reason_code
    if new_status in TERMINAL_DECISION_STATUSES:
        case.decision_at = now
    case.save(
        update_fields=[
            "status",
            "manual_review_required",
            "blocking_reason",
            "decision_at",
            "updated_at",
        ]
    )
    if new_status == KycStatus.APPROVED:
        _activate_user_after_kyc_approval(case, _actor_for_admin(command.actor))

    decision = KycManualReviewDecision.objects.create(
        case=case,
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        decision=command.decision,
        reason_code=command.reason_code,
        previous_status=previous_status,
        new_status=new_status,
        note=command.note.strip(),
        evidence_summary=command.evidence_summary.strip(),
        decided_at=now,
    )
    record_audit_event(
        AuditCommand(
            actor=_actor_for_admin(command.actor),
            action="kyc.manual_review_decision_recorded",
            target_type="KycVerificationCase",
            target_id=str(case.id),
            metadata={
                "decision_id": str(decision.id),
                "decision": command.decision,
                "previous_status": previous_status,
                "new_status": new_status,
                "reason_code": command.reason_code,
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="KycManualReviewDecisionRecorded",
            aggregate_type="KycVerificationCase",
            aggregate_id=str(case.id),
            payload={
                "decision_id": str(decision.id),
                "decision": command.decision,
                "previous_status": previous_status,
                "new_status": new_status,
                "reason_code": command.reason_code,
            },
            idempotency_key=f"kyc:{case.id}:manual-review:{decision.id}",
        )
    )
    return cast(KycManualReviewDecision, decision)


def _manual_review_target_status(decision: KycManualReviewDecisionType) -> KycStatus:
    if decision == KycManualReviewDecisionType.APPROVE:
        return KycStatus.APPROVED
    if decision == KycManualReviewDecisionType.DECLINE:
        return KycStatus.DECLINED
    if decision == KycManualReviewDecisionType.REQUEST_REVERIFICATION:
        return KycStatus.REVERIFICATION_REQUIRED
    if decision == KycManualReviewDecisionType.REOPEN:
        return KycStatus.MANUAL_REVIEW
    raise KycManualReviewError("Unsupported manual review decision.")


def user_kyc_status(user: Model) -> KycStatus:
    case = KycVerificationCase.objects.filter(user_id=user.pk).first()
    if case is None:
        return KycStatus.NOT_STARTED
    return KycStatus(case.status)


def user_can_access_financial_features(user: Model) -> bool:
    if not bool(getattr(user, "is_active", False)):
        return False
    if str(getattr(user, "status", "")) in BLOCKING_ACCOUNT_STATUSES:
        return False
    if getattr(user, "phone_verified_at", None) is None:
        return False
    return user_kyc_status(user) == KycStatus.APPROVED


def verify_didit_webhook_signature(*, raw_body: bytes, signature: str) -> bool:
    secret = str(settings.DIDIT_WEBHOOK_SECRET)
    signature_required = (
        bool(settings.DIDIT_WEBHOOK_REQUIRE_SIGNATURE)
        or str(settings.ENVIRONMENT).lower() != "local"
    )
    if not signature_required:
        return True
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, digest) or hmac.compare_digest(
        signature,
        f"sha256={digest}",
    )
