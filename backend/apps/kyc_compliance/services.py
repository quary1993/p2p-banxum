from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

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
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
)
from backend.apps.platform_core.domain.access import (
    user_can_access_financial_features as platform_user_can_access_financial_features,
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

class KycComplianceError(ValueError):
    pass


class KycWebhookSignatureError(KycComplianceError):
    pass


class KycWebhookMatchError(KycComplianceError):
    pass


class KycManualReviewError(KycComplianceError):
    pass


class DiditApiError(KycComplianceError):
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
class DiditHostedSession:
    provider_session_id: str
    verification_url: str
    provider_status: str
    provider_payload: dict[str, Any]


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


def _provider_environment() -> str:
    return str(settings.DIDIT_ENVIRONMENT)


def _didit_session_provider() -> str:
    return str(settings.DIDIT_SESSION_PROVIDER).strip().lower()


def _didit_api_base_url() -> str:
    return str(settings.DIDIT_API_BASE_URL).strip().rstrip("/")


def _workflow_id(override: str | None = None) -> str:
    return override or str(settings.DIDIT_WORKFLOW_ID)


def _validate_api_session_config(workflow_id: str) -> None:
    if not str(settings.DIDIT_API_KEY).strip():
        raise DiditApiError("DIDIT_API_KEY is required when Didit API session mode is enabled.")
    if not workflow_id or workflow_id == "didit-natural-person-lender-v1":
        raise DiditApiError("A real DIDIT_WORKFLOW_ID is required for Didit API session mode.")
    if not _didit_api_base_url():
        raise DiditApiError("DIDIT_API_BASE_URL is required for Didit API session mode.")


def _user_contact_details(user: Model) -> dict[str, Any]:
    contact_details: dict[str, Any] = {}
    email = str(getattr(user, "email", "")).strip()
    phone = str(getattr(user, "phone_number", "")).strip()
    if email:
        contact_details["email"] = email
        contact_details["email_lang"] = str(settings.DIDIT_LANGUAGE)
        contact_details["send_notification_emails"] = False
    if phone:
        contact_details["phone"] = phone
    return contact_details


def _user_expected_details(user: Model) -> dict[str, Any]:
    full_name = str(getattr(user, "full_name", "")).strip()
    if not full_name:
        return {}
    parts = full_name.split()
    if len(parts) == 1:
        return {"first_name": parts[0]}
    return {"first_name": parts[0], "last_name": " ".join(parts[1:])}


def _didit_session_request_payload(
    *,
    user: Model,
    workflow_id: str,
    vendor_data: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "workflow_id": workflow_id,
        "vendor_data": vendor_data,
        "metadata": {
            "platform": str(settings.PLATFORM_BRAND_NAME),
            "operator": str(settings.LEGAL_OPERATOR_NAME),
            "subject_reference": vendor_data,
            "user_id": str(user.pk),
        },
        "language": str(settings.DIDIT_LANGUAGE),
    }
    callback_url = str(settings.DIDIT_CALLBACK_URL).strip()
    if callback_url:
        payload["callback"] = callback_url
        payload["callback_method"] = str(settings.DIDIT_CALLBACK_METHOD)
    contact_details = _user_contact_details(user)
    if contact_details:
        payload["contact_details"] = contact_details
    expected_details = _user_expected_details(user)
    if expected_details:
        payload["expected_details"] = expected_details
    return payload


def _safe_didit_session_payload(response_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "api",
        "session_kind": response_payload.get("session_kind", ""),
        "session_number": response_payload.get("session_number"),
        "workflow_id": response_payload.get("workflow_id", ""),
        "workflow_version": response_payload.get("workflow_version"),
        "status": response_payload.get("status", ""),
        "vendor_data": response_payload.get("vendor_data", ""),
        "metadata": response_payload.get("metadata", {}),
        "session_token_present": bool(response_payload.get("session_token")),
    }


def _safe_json_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _payload_value(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value)
    return ""


def _decision_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = payload.get("decision")
    if isinstance(decision, dict):
        return decision
    return {}


def _payload_vendor_data(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("vendor_data", "vendorData", "subject_reference"):
            value = metadata.get(key)
            if value is not None:
                return str(value)
    return _payload_value(payload, "vendor_data", "vendorData")


def _nested_payload_value(payload: dict[str, Any], *keys: str) -> str:
    decision = _decision_payload(payload)
    for key in keys:
        value = payload.get(key)
        if value is None:
            value = decision.get(key)
        if value is not None:
            return str(value)
    return ""


def _first_decision_item_value(
    payload: dict[str, Any],
    collection_key: str,
    *keys: str,
) -> str:
    collection = payload.get(collection_key)
    if not isinstance(collection, list):
        collection = _decision_payload(payload).get(collection_key)
    if not isinstance(collection, list):
        return ""
    for item in collection:
        if not isinstance(item, dict):
            continue
        for key in keys:
            value = item.get(key)
            if value is not None:
                return str(value)
    return ""


def _iter_text_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[str] = []
        for key, item in value.items():
            values.append(str(key))
            values.extend(_iter_text_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_iter_text_values(item))
        return values
    if isinstance(value, str):
        return [value]
    return []


def _payload_flags(payload: dict[str, Any]) -> list[str]:
    value = payload.get("detected_flags", payload.get("flags", []))
    flags: set[str] = set()
    if isinstance(value, list):
        flags.update(str(item) for item in value)
    if isinstance(value, str) and value:
        flags.update(item.strip() for item in value.split(",") if item.strip())

    decision = _decision_payload(payload)
    for collection_key in ("aml_screenings", "reviews", "id_verifications"):
        collection = payload.get(collection_key)
        if not isinstance(collection, list):
            collection = decision.get(collection_key)
        if not isinstance(collection, list):
            continue
        for item in collection:
            text = " ".join(_iter_text_values(item)).lower() if isinstance(item, dict) else ""
            if "sanction" in text:
                flags.add("sanctions")
            if "pep" in text:
                flags.add("pep")
            if "adverse" in text and "media" in text:
                flags.add("adverse_media")
            if "fraud" in text:
                flags.add("identity_fraud")
    return sorted(flags)


def provider_event_command_from_payload(
    payload: dict[str, Any],
    *,
    provider_event_id_fallback: str = "",
) -> ProviderKycEventCommand:
    provider_event_id = (
        _payload_value(payload, "provider_event_id", "event_id", "id")
        or provider_event_id_fallback
    )
    provider_session_id = _payload_value(
        payload,
        "provider_session_id",
        "session_id",
        "sessionId",
    )
    if not provider_event_id:
        raise KycWebhookMatchError("Didit webhook is missing a provider event ID.")
    return ProviderKycEventCommand(
        provider_event_id=provider_event_id,
        provider_event_type=(
            _payload_value(payload, "provider_event_type", "event_type", "webhook_type", "type")
            or "verification.updated"
        ),
        provider_status=_nested_payload_value(
            payload,
            "provider_status",
            "status",
            "verification_status",
        ),
        provider_session_id=provider_session_id,
        vendor_data=_payload_vendor_data(payload),
        verification_id=_payload_value(payload, "verification_id", "verificationId", "session_id"),
        report_id=_payload_value(payload, "report_id", "reportId", "pdf_report_id"),
        aml_screening_id=(
            _payload_value(payload, "aml_screening_id", "amlScreeningId")
            or _first_decision_item_value(
                payload,
                "aml_screenings",
                "id",
                "screening_id",
                "node_id",
            )
        ),
        provider_subject_id=_payload_value(
            payload,
            "provider_subject_id",
            "subject_id",
            "vendor_user_id",
            "vendor_business_id",
            "user_id",
        ),
        risk_classification=_nested_payload_value(
            payload,
            "risk_classification",
            "risk",
            "risk_level",
            "severity",
        ),
        detected_flags=_payload_flags(payload),
        raw_payload=payload,
    )


def _create_didit_api_session(
    *,
    user: Model,
    workflow_id: str,
    vendor_data: str,
) -> DiditHostedSession:
    _validate_api_session_config(workflow_id)
    body = json.dumps(
        _didit_session_request_payload(
            user=user,
            workflow_id=workflow_id,
            vendor_data=vendor_data,
        )
    ).encode("utf-8")
    request = Request(
        f"{_didit_api_base_url()}/v3/session/",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": str(settings.DIDIT_API_KEY),
        },
        method="POST",
    )
    try:
        with urlopen(  # noqa: S310 - Didit base URL is environment-configured and validated.
            request,
            timeout=int(settings.DIDIT_API_TIMEOUT_SECONDS),
        ) as response:
            response_body = response.read()
    except HTTPError as exc:
        safe_body = exc.read(2048).decode("utf-8", errors="replace")
        raise DiditApiError(
            f"Didit session creation failed with HTTP {exc.code}: {safe_body}"
        ) from exc
    except URLError as exc:
        raise DiditApiError(f"Didit session creation failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise DiditApiError("Didit session creation timed out.") from exc

    try:
        payload = json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise DiditApiError("Didit session creation returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise DiditApiError("Didit session creation returned an unexpected payload.")

    provider_session_id = str(payload.get("session_id", "")).strip()
    verification_url = str(payload.get("url", "")).strip()
    if not provider_session_id or not verification_url:
        raise DiditApiError("Didit session creation did not return session_id and url.")
    return DiditHostedSession(
        provider_session_id=provider_session_id,
        verification_url=verification_url,
        provider_status=str(payload.get("status", "Not Started")),
        provider_payload=_safe_didit_session_payload(payload),
    )


def _retrieve_didit_session_decision(session: KycProviderSession) -> dict[str, Any]:
    _validate_api_session_config(session.workflow_id or _workflow_id())
    provider_session_id = str(session.provider_session_id).strip()
    if not provider_session_id:
        raise DiditApiError("Didit status polling requires a provider session ID.")
    request = Request(
        f"{_didit_api_base_url()}/v3/session/{quote(provider_session_id, safe='')}/decision/",
        headers={
            "Accept": "application/json",
            "x-api-key": str(settings.DIDIT_API_KEY),
        },
        method="GET",
    )
    try:
        with urlopen(  # noqa: S310 - Didit base URL is environment-configured and validated.
            request,
            timeout=int(settings.DIDIT_API_TIMEOUT_SECONDS),
        ) as response:
            response_body = response.read()
    except HTTPError as exc:
        safe_body = exc.read(2048).decode("utf-8", errors="replace")
        raise DiditApiError(
            f"Didit session decision retrieval failed with HTTP {exc.code}: {safe_body}"
        ) from exc
    except URLError as exc:
        raise DiditApiError(f"Didit session decision retrieval failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise DiditApiError("Didit session decision retrieval timed out.") from exc

    try:
        payload = json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise DiditApiError("Didit session decision retrieval returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise DiditApiError("Didit session decision retrieval returned an unexpected payload.")
    return payload


def _can_poll_didit_session(case: KycVerificationCase, session: KycProviderSession) -> bool:
    if case.status not in {KycStatus.NOT_STARTED, KycStatus.PENDING}:
        return False
    payload = session.provider_payload if isinstance(session.provider_payload, dict) else {}
    provider_mode = str(payload.get("mode", "")).strip().lower()
    return provider_mode == "api" or _didit_session_provider() in {"api", "didit", "live"}


def _decision_poll_payload(
    *,
    session: KycProviderSession,
    payload: dict[str, Any],
) -> dict[str, Any]:
    enriched_payload = dict(payload)
    enriched_payload.setdefault("provider_event_type", "verification.polled")
    enriched_payload.setdefault("session_id", session.provider_session_id)
    enriched_payload.setdefault("provider_session_id", session.provider_session_id)
    enriched_payload.setdefault("vendor_data", session.vendor_data)
    return enriched_payload


def _record_decision_poll(
    *,
    session: KycProviderSession,
    payload: dict[str, Any],
    normalized_status: KycStatus,
) -> None:
    provider_payload = dict(session.provider_payload or {})
    provider_payload.update(
        {
            "last_decision_poll_at": timezone.now().isoformat(),
            "last_decision_payload_hash": _safe_json_hash(payload),
            "last_polled_status": normalized_status,
        }
    )
    session.provider_payload = provider_payload
    session.save(update_fields=["provider_payload", "updated_at"])


def refresh_user_kyc_status_from_provider(
    user: Model,
) -> tuple[KycVerificationCase | None, KycProviderSession | None]:
    case = KycVerificationCase.objects.filter(user_id=user.pk).first()
    if case is None:
        return None, None
    session = KycProviderSession.objects.filter(case=case).order_by("-created_at").first()
    if session is None or not _can_poll_didit_session(case, session):
        return case, session

    payload = _decision_poll_payload(
        session=session,
        payload=_retrieve_didit_session_decision(session),
    )
    command = provider_event_command_from_payload(
        payload,
        provider_event_id_fallback=f"didit-poll:{_safe_json_hash(payload)[:48]}",
    )
    normalized_status = normalize_didit_status(
        provider_status=command.provider_status,
        detected_flags=command.detected_flags,
        risk_classification=command.risk_classification,
    )
    _record_decision_poll(session=session, payload=payload, normalized_status=normalized_status)

    if normalized_status == KycStatus.PENDING and case.status == KycStatus.PENDING:
        return case, session

    result = process_didit_event(command)
    result.case.refresh_from_db()
    refreshed_session = (
        KycProviderSession.objects.filter(id=session.id).first()
        if session.id is not None
        else session
    )
    return result.case, refreshed_session


def _create_mock_didit_session(
    *,
    user: Model,
    workflow_id: str,
    vendor_data: str,
) -> DiditHostedSession:
    provider_session_id = f"didit_mock_{uuid.uuid4()}"
    return DiditHostedSession(
        provider_session_id=provider_session_id,
        verification_url=(
            f"{settings.DIDIT_MOCK_VERIFICATION_BASE_URL.rstrip('/')}/{provider_session_id}"
        ),
        provider_status="pending",
        provider_payload={
            "mode": "mock",
            "user_id": str(user.pk),
            "email_present": bool(getattr(user, "email", "")),
        },
    )


def _create_provider_session(
    *,
    user: Model,
    workflow_id: str,
    vendor_data: str,
) -> DiditHostedSession:
    provider = _didit_session_provider()
    if provider in {"api", "didit", "live"}:
        return _create_didit_api_session(
            user=user,
            workflow_id=workflow_id,
            vendor_data=vendor_data,
        )
    if provider == "mock":
        return _create_mock_didit_session(
            user=user,
            workflow_id=workflow_id,
            vendor_data=vendor_data,
        )
    raise DiditApiError(f"Unsupported DIDIT_SESSION_PROVIDER: {provider}")


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

    workflow_id = _workflow_id(command.workflow_id)
    vendor_data = vendor_data_for_user(command.user)
    hosted_session = _create_provider_session(
        user=command.user,
        workflow_id=workflow_id,
        vendor_data=vendor_data,
    )

    existing_provider_session = KycProviderSession.objects.filter(
        provider_session_id=hosted_session.provider_session_id
    ).first()
    if existing_provider_session is not None:
        return KycSessionResult(case=case, session=existing_provider_session)

    now = timezone.now()
    session = KycProviderSession.objects.create(
        case=case,
        provider_environment=_provider_environment(),
        workflow_id=workflow_id,
        provider_session_id=hosted_session.provider_session_id,
        verification_url=hosted_session.verification_url,
        vendor_data=vendor_data,
        expires_at=now + command.ttl,
        provider_payload=hosted_session.provider_payload,
    )
    case.status = KycStatus.PENDING
    case.provider_environment = session.provider_environment
    case.workflow_id = workflow_id
    case.vendor_data = vendor_data
    case.provider_session_id = hosted_session.provider_session_id
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
            metadata={
                "provider": "didit",
                "provider_session_id": hosted_session.provider_session_id,
                "provider_mode": hosted_session.provider_payload.get("mode", ""),
                "provider_status": hosted_session.provider_status,
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="KycSessionCreated",
            aggregate_type="KycVerificationCase",
            aggregate_id=str(case.id),
            payload={
                "user_id": user_id,
                "provider_session_id": hosted_session.provider_session_id,
                "provider_mode": hosted_session.provider_payload.get("mode", ""),
            },
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
        "awaiting_user",
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
        "resubmitted",
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
        with transaction.atomic():
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
    if not is_admin_actor(command.actor):
        raise KycManualReviewError("Only an active admin can record KYC manual review decisions.")
    if not command.note.strip() and not command.evidence_summary.strip():
        raise KycManualReviewError("A note or evidence summary is required.")

    case = KycVerificationCase.objects.select_for_update().filter(id=command.case_id).first()
    if case is None:
        raise KycManualReviewError("KYC case does not exist.")

    previous_status = KycStatus(case.status)
    if command.decision == KycManualReviewDecisionType.APPROVE:
        if previous_status in NON_OVERRIDABLE_APPROVAL_STATUSES:
            raise KycManualReviewError("This KYC status cannot be manually approved.")
        if previous_status not in MANUAL_REVIEW_STATUSES:
            raise KycManualReviewError("Only review-routed KYC statuses can be manually approved.")

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
        _activate_user_after_kyc_approval(case, actor_ref_for_user(command.actor))

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
            actor=actor_ref_for_user(command.actor),
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
    return platform_user_can_access_financial_features(user)


def _shorten_whole_floats(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _shorten_whole_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_shorten_whole_floats(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _timestamp_is_fresh(timestamp: str) -> bool:
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        return False
    return abs(int(time.time()) - timestamp_int) <= 300


def _compare_digest(signature: str, digest: str) -> bool:
    return hmac.compare_digest(signature, digest) or hmac.compare_digest(
        signature,
        f"sha256={digest}",
    )


def _verify_didit_signature_v2(
    *,
    payload: dict[str, Any],
    signature: str,
    timestamp: str,
    secret: str,
) -> bool:
    if not signature or not timestamp or not _timestamp_is_fresh(timestamp):
        return False
    canonical = json.dumps(
        _shorten_whole_floats(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return _compare_digest(signature, digest)


def _verify_didit_signature_simple(
    *,
    payload: dict[str, Any],
    signature: str,
    timestamp: str,
    secret: str,
) -> bool:
    if not signature or not timestamp or not _timestamp_is_fresh(timestamp):
        return False
    canonical = ":".join(
        [
            str(payload.get("timestamp", "")),
            str(payload.get("session_id", "")),
            str(payload.get("status", "")),
            str(payload.get("webhook_type", "")),
        ]
    )
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return _compare_digest(signature, digest)


def _verify_didit_raw_signature(*, raw_body: bytes, signature: str, secret: str) -> bool:
    if not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return _compare_digest(signature, digest)


def verify_didit_webhook_signature(
    *,
    raw_body: bytes,
    signature: str = "",
    payload: dict[str, Any] | None = None,
    signature_v2: str = "",
    signature_simple: str = "",
    timestamp: str = "",
) -> bool:
    secret = str(settings.DIDIT_WEBHOOK_SECRET)
    signature_required = (
        bool(settings.DIDIT_WEBHOOK_REQUIRE_SIGNATURE)
        or str(settings.ENVIRONMENT).lower() != "local"
    )
    if not signature_required:
        return True
    if not secret:
        return False
    if payload is not None and _verify_didit_signature_v2(
        payload=payload,
        signature=signature_v2,
        timestamp=timestamp,
        secret=secret,
    ):
        return True
    if _verify_didit_raw_signature(raw_body=raw_body, signature=signature, secret=secret):
        return True
    return bool(
        payload is not None
        and _verify_didit_signature_simple(
            payload=payload,
            signature=signature_simple,
            timestamp=timestamp,
            secret=secret,
        )
    )
