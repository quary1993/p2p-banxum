"""Didit webhook replay protection (audit 2026-10-09, A-53 / SECCODE-09).

The freshness check used the unsigned X-Timestamp header, the raw-body signature had
no time check at all, and the "simple" signature (timestamp, session id, status,
webhook type only) let unsigned fields such as the event id, user mapping and
screening flags through.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.kyc_compliance.models import KycProviderEvent, KycStatus, KycVerificationCase
from backend.apps.kyc_compliance.services import (
    CreateKycSessionCommand,
    create_kyc_session,
    verify_didit_webhook,
)

SECRET = "test-secret"
THIRTY_DAYS = 30 * 24 * 60 * 60


@pytest.fixture(autouse=True)
def signed_webhooks(settings: Any) -> None:
    settings.DIDIT_WEBHOOK_SECRET = SECRET
    settings.DIDIT_WEBHOOK_REQUIRE_SIGNATURE = True


def _lender() -> Model:
    user_model: Any = get_user_model()
    user = user_model.objects.create_user(
        email="investor@example.test",
        full_name="Investor",
        account_type="natural_person_lender",
        status="pending_kyc",
        phone_number="+41790000000",
    )
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])
    return cast(Model, user)


def _session_id(user: Model) -> str:
    result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert result.session is not None
    return str(result.session.provider_session_id)


def _hmac(message: bytes) -> str:
    return hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()


def _v2(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _hmac(canonical.encode("utf-8"))


def _simple(payload: dict[str, Any]) -> str:
    keys = ("timestamp", "session_id", "status", "webhook_type")
    return _hmac(":".join(str(payload.get(key, "")) for key in keys).encode("utf-8"))


def _post(client: Client, payload: dict[str, Any], **headers: Any) -> Any:
    return client.post(
        "/api/v1/kyc/webhooks/didit/",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        content_type="application/json",
        **headers,
    )


def test_old_simple_signature_with_a_fresh_header_is_refused() -> None:
    old = int(time.time()) - THIRTY_DAYS
    payload = {
        "timestamp": old,
        "session_id": "s1",
        "status": "Approved",
        "webhook_type": "status.updated",
        "event_id": "new-event-id",
    }

    assert (
        verify_didit_webhook(
            raw_body=b"",
            payload=payload,
            signature_simple=_simple(payload),
            timestamp=str(int(time.time())),
        )
        is None
    )


def test_raw_signature_without_a_signed_timestamp_is_refused() -> None:
    payload = {"event_id": "e1", "session_id": "s1", "status": "Approved"}
    body = json.dumps(payload).encode("utf-8")

    assert verify_didit_webhook(raw_body=body, payload=payload, signature=_hmac(body)) is None


def test_raw_signature_with_an_old_signed_timestamp_is_refused() -> None:
    payload = {"event_id": "e1", "status": "Approved", "timestamp": int(time.time()) - 3600}
    body = json.dumps(payload).encode("utf-8")

    assert verify_didit_webhook(raw_body=body, payload=payload, signature=_hmac(body)) is None


def test_fresh_signed_timestamp_is_accepted_whatever_the_header_says() -> None:
    payload = {"event_id": "e1", "status": "Approved", "timestamp": int(time.time())}

    verification = verify_didit_webhook(
        raw_body=b"",
        payload=payload,
        signature_v2=_v2(payload),
        timestamp=str(int(time.time()) - THIRTY_DAYS),
    )

    assert verification is not None
    assert verification.method == "v2"


@pytest.mark.django_db
def test_replayed_v2_webhook_with_an_old_payload_is_refused(client: Client) -> None:
    user = _lender()
    payload = {
        "event_id": "approved-once",
        "webhook_type": "status.updated",
        "timestamp": int(time.time()) - 600,
        "session_id": _session_id(user),
        "status": "Approved",
        "vendor_data": f"user:{user.pk}",
    }

    response = _post(
        client,
        payload,
        HTTP_X_SIGNATURE_V2=_v2(payload),
        HTTP_X_TIMESTAMP=str(int(time.time())),
    )

    assert response.status_code == 403
    assert not KycProviderEvent.objects.exists()
    assert KycVerificationCase.objects.get(user_id=user.pk).status == KycStatus.PENDING


@pytest.mark.django_db
def test_simple_signature_trusts_only_the_signed_fields(client: Client) -> None:
    user = _lender()
    session_id = _session_id(user)
    payload = {
        "timestamp": int(time.time()),
        "session_id": session_id,
        "status": "Approved",
        "webhook_type": "status.updated",
        # None of these are covered by the simple signature.
        "event_id": "attacker-chosen-id",
        "vendor_data": "user:00000000-0000-0000-0000-000000000000",
        "detected_flags": [],
        "risk": "low",
    }

    first = _post(client, payload, HTTP_X_SIGNATURE_SIMPLE=_simple(payload))
    payload["event_id"] = "another-attacker-id"
    replay = _post(client, payload, HTTP_X_SIGNATURE_SIMPLE=_simple(payload))

    assert first.status_code == 202
    # An approval that is only partly signed waits for an admin.
    assert first.json()["status"] == KycStatus.MANUAL_REVIEW
    case = KycVerificationCase.objects.get(user_id=user.pk)
    assert case.status == KycStatus.MANUAL_REVIEW
    assert case.manual_review_required is True
    assert get_user_model().objects.get(pk=user.pk).status == "pending_kyc"
    event = KycProviderEvent.objects.get()
    assert event.provider_event_id.startswith("didit-simple:")
    assert event.vendor_data == ""
    assert event.raw_payload["signature_method"] == "simple"
    # The same signed fields with a new unsigned event id are the same event.
    assert replay.status_code == 202
    assert replay.json()["idempotent"] is True
    assert KycProviderEvent.objects.count() == 1


@pytest.mark.django_db
def test_fully_signed_fresh_approval_still_activates(client: Client) -> None:
    user = _lender()
    payload = {
        "event_id": "approved-fresh",
        "webhook_type": "status.updated",
        "timestamp": int(time.time()),
        "session_id": _session_id(user),
        "status": "Approved",
        "vendor_data": f"user:{user.pk}",
    }

    response = _post(client, payload, HTTP_X_SIGNATURE_V2=_v2(payload))

    assert response.status_code == 202
    assert response.json()["status"] == KycStatus.APPROVED
    assert get_user_model().objects.get(pk=user.pk).status == "active"


@pytest.mark.django_db
def test_partly_signed_approval_does_not_disturb_an_approved_case(client: Client) -> None:
    user = _lender()
    session_id = _session_id(user)
    signed = {
        "event_id": "approved-fully-signed",
        "webhook_type": "status.updated",
        "timestamp": int(time.time()),
        "session_id": session_id,
        "status": "Approved",
        "vendor_data": f"user:{user.pk}",
    }
    approved = _post(client, signed, HTTP_X_SIGNATURE_V2=_v2(signed))
    assert approved.json()["status"] == KycStatus.APPROVED
    partial = {
        "timestamp": int(time.time()) + 1,
        "session_id": session_id,
        "status": "Approved",
        "webhook_type": "status.updated",
    }

    response = _post(client, partial, HTTP_X_SIGNATURE_SIMPLE=_simple(partial))

    assert response.status_code == 202
    assert KycVerificationCase.objects.get(user_id=user.pk).status == KycStatus.APPROVED
    assert get_user_model().objects.get(pk=user.pk).status == "active"
