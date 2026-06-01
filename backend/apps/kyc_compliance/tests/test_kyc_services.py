from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.kyc_compliance.checks import check_didit_webhook_signature_config
from backend.apps.kyc_compliance.models import (
    KycProviderEvent,
    KycProviderSession,
    KycStatus,
    KycVerificationCase,
)
from backend.apps.kyc_compliance.services import (
    CreateKycSessionCommand,
    ProviderKycEventCommand,
    create_kyc_session,
    process_didit_event,
    user_can_access_financial_features,
    verify_didit_webhook_signature,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation


def create_lender(email: str = "investor@example.test") -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name="Investor",
            account_type="natural_person_lender",
            status="pending_kyc",
            phone_number="+41790000000",
        ),
    )


def mark_phone_verified(user: Model) -> None:
    user_with_phone = cast(Any, user)
    user_with_phone.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])


@pytest.mark.django_db
def test_create_kyc_session_records_case_session_and_events(settings: Any) -> None:
    user = create_lender()

    result = create_kyc_session(CreateKycSessionCommand(user=user))

    assert result.session is not None
    assert result.case.status == KycStatus.PENDING
    assert result.case.user_id == user.pk
    assert result.case.vendor_data == f"user:{user.pk}"
    assert result.session.provider_session_id.startswith("didit_mock_")
    assert result.session.verification_url.startswith(settings.DIDIT_MOCK_VERIFICATION_BASE_URL)
    assert AuditEvent.objects.filter(
        action="kyc.session_created",
        target_id=str(result.case.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="KycSessionCreated",
        aggregate_id=str(result.case.id),
    ).exists()


@pytest.mark.django_db
def test_create_kyc_session_reuses_active_pending_session() -> None:
    user = create_lender()

    first = create_kyc_session(CreateKycSessionCommand(user=user))
    second = create_kyc_session(CreateKycSessionCommand(user=user))

    assert first.session is not None
    assert second.session is not None
    assert second.session.id == first.session.id
    assert KycProviderSession.objects.count() == 1


@pytest.mark.django_db
def test_approved_didit_event_enables_financial_gate_after_phone_verified() -> None:
    user = create_lender()
    mark_phone_verified(user)
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None

    event_result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id="didit-event-approved",
            provider_event_type="verification.completed",
            provider_status="approved",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            verification_id="verification-1",
            report_id="report-1",
            aml_screening_id="aml-1",
            provider_subject_id="subject-1",
            risk_classification="low",
            raw_payload={"id": "didit-event-approved", "status": "approved"},
        )
    )

    assert event_result.case.status == KycStatus.APPROVED
    assert event_result.case.decision_at is not None
    assert event_result.case.manual_review_required is False
    assert user_can_access_financial_features(user) is True
    assert DomainEvent.objects.filter(
        event_type="KycStatusChanged",
        aggregate_id=str(event_result.case.id),
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("flags", "risk", "expected_status"),
    [
        (["sanctions"], "low", KycStatus.SANCTIONS_HIT),
        (["pep"], "low", KycStatus.PEP_HIT),
        (["adverse_media"], "low", KycStatus.ADVERSE_MEDIA_HIT),
        ([], "high", KycStatus.HIGH_RISK),
    ],
)
def test_didit_risk_flags_block_financial_gate(
    flags: list[str],
    risk: str,
    expected_status: KycStatus,
) -> None:
    user = create_lender(email=f"{expected_status}@example.test")
    mark_phone_verified(user)
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None

    result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id=f"didit-event-{expected_status}",
            provider_event_type="verification.completed",
            provider_status="approved",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            risk_classification=risk,
            detected_flags=flags,
            raw_payload={"id": f"didit-event-{expected_status}"},
        )
    )

    assert result.case.status == expected_status
    assert user_can_access_financial_features(user) is False
    if expected_status in {KycStatus.PEP_HIT, KycStatus.ADVERSE_MEDIA_HIT, KycStatus.HIGH_RISK}:
        assert result.case.manual_review_required is True


@pytest.mark.django_db
def test_didit_event_processing_is_idempotent() -> None:
    user = create_lender()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None
    command = ProviderKycEventCommand(
        provider_event_id="didit-event-idempotent",
        provider_event_type="verification.processing",
        provider_status="processing",
        provider_session_id=session_result.session.provider_session_id,
        vendor_data=f"user:{user.pk}",
        raw_payload={"id": "didit-event-idempotent", "status": "processing"},
    )

    first = process_didit_event(command)
    second = process_didit_event(command)

    assert first.idempotent is False
    assert second.idempotent is True
    assert second.event.id == first.event.id
    assert KycProviderEvent.objects.count() == 1


@pytest.mark.django_db
def test_provider_events_are_append_only() -> None:
    user = create_lender()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None
    result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id="didit-event-append-only",
            provider_event_type="verification.processing",
            provider_status="processing",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            raw_payload={"id": "didit-event-append-only"},
        )
    )

    result.event.provider_status = "approved"
    with pytest.raises(AppendOnlyViolation):
        result.event.save()
    with pytest.raises(AppendOnlyViolation):
        KycProviderEvent.objects.filter(id=result.event.id).update(provider_status="approved")
    with pytest.raises(AppendOnlyViolation):
        KycProviderEvent.objects.filter(id=result.event.id).delete()


@pytest.mark.django_db
def test_kyc_status_and_session_api_flow(client: Client) -> None:
    user = create_lender()
    client.force_login(cast(Any, user))

    initial_status = client.get("/api/v1/kyc/status/")
    session_response = client.post(
        "/api/v1/kyc/session/",
        data={},
        content_type="application/json",
    )

    assert initial_status.status_code == 200
    assert initial_status.json()["status"] == KycStatus.NOT_STARTED
    assert initial_status.json()["financial_access_allowed"] is False
    assert session_response.status_code == 202
    assert session_response.json()["status"] == KycStatus.PENDING
    assert session_response.json()["provider_session_id"].startswith("didit_mock_")
    assert KycVerificationCase.objects.filter(user_id=user.pk, status=KycStatus.PENDING).exists()


@pytest.mark.django_db
def test_didit_webhook_requires_valid_signature_when_configured(
    client: Client,
    settings: Any,
) -> None:
    settings.DIDIT_WEBHOOK_SECRET = "test-secret"
    settings.DIDIT_WEBHOOK_REQUIRE_SIGNATURE = True
    user = create_lender()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None
    payload = {
        "id": "didit-webhook-approved",
        "type": "verification.completed",
        "status": "approved",
        "session_id": session_result.session.provider_session_id,
        "vendor_data": f"user:{user.pk}",
        "risk": "low",
    }
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

    invalid = client.post(
        "/api/v1/kyc/webhooks/didit/",
        data=body,
        content_type="application/json",
        HTTP_X_DIDIT_SIGNATURE="bad-signature",
    )
    valid = client.post(
        "/api/v1/kyc/webhooks/didit/",
        data=body,
        content_type="application/json",
        HTTP_X_DIDIT_SIGNATURE=signature,
    )

    assert invalid.status_code == 403
    assert valid.status_code == 202
    assert valid.json()["status"] == KycStatus.APPROVED


def test_didit_webhook_signature_is_required_outside_local_even_if_env_disables_it(
    settings: Any,
) -> None:
    settings.ENVIRONMENT = "production"
    settings.DIDIT_WEBHOOK_REQUIRE_SIGNATURE = False
    settings.DIDIT_WEBHOOK_SECRET = ""

    assert verify_didit_webhook_signature(raw_body=b"{}", signature="") is False


def test_didit_webhook_signature_uses_secret_outside_local_even_if_env_disables_it(
    settings: Any,
) -> None:
    settings.ENVIRONMENT = "staging"
    settings.DIDIT_WEBHOOK_REQUIRE_SIGNATURE = False
    settings.DIDIT_WEBHOOK_SECRET = "test-secret"
    body = b'{"id":"event"}'
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

    assert verify_didit_webhook_signature(raw_body=body, signature="") is False
    assert verify_didit_webhook_signature(raw_body=body, signature=signature) is True


def test_didit_webhook_signature_system_check_flags_non_local_unsafe_config(
    settings: Any,
) -> None:
    settings.ENVIRONMENT = "production"
    settings.DIDIT_WEBHOOK_REQUIRE_SIGNATURE = False
    settings.DIDIT_WEBHOOK_SECRET = ""

    errors = check_didit_webhook_signature_config(None)

    assert {error.id for error in errors} == {"kyc_compliance.E001", "kyc_compliance.E002"}
