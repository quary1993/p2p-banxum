from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.test.utils import override_settings

from backend.apps.accounts_auth.checks import check_phone_verification_provider_config
from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    PhoneVerificationChallenge,
    PhoneVerificationStatus,
    User,
)
from backend.apps.accounts_auth.phone_providers import (
    PhoneVerificationCheckResult,
    PhoneVerificationStartResult,
    check_twilio_verify,
    start_twilio_verify,
)
from backend.apps.accounts_auth.services import (
    InvalidOrExpiredCodeError,
    PhoneAlreadyVerifiedError,
    PhoneVerificationConfirmCommand,
    PhoneVerificationRequestCommand,
    PhoneVerificationThrottleError,
    TooManyCodeAttemptsError,
    confirm_phone_verification,
    delivery_secret_for_phone_verification,
    request_phone_verification,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent, OutboxMessage


class _FakeTwilioResponse:
    status = 200

    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeTwilioResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        import json

        return json.dumps(self._payload).encode("utf-8")


class _FakeTwilioOpener:
    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self.calls = calls

    def open(self, request: Any, timeout: int) -> _FakeTwilioResponse:
        from urllib.parse import parse_qs

        body = parse_qs(request.data.decode("utf-8"))
        payload = {key: values[0] for key, values in body.items()}
        self.calls.append({"url": request.full_url, "timeout": timeout, "payload": payload})
        if request.full_url.endswith("/Verifications"):
            return _FakeTwilioResponse({"sid": "VE-started", "status": "pending"})
        return _FakeTwilioResponse({"sid": "VE-checked", "status": "approved"})


@pytest.fixture
def investor() -> User:
    return User.objects.create_user(
        email="investor@example.test",
        full_name="Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.PENDING_KYC,
        phone_number="+41790000000",
    )


@pytest.mark.django_db
def test_phone_verification_request_creates_challenge_and_sms_outbox(investor: User) -> None:
    result = request_phone_verification(PhoneVerificationRequestCommand(user=investor))

    assert result.raw_code.isdigit()
    assert len(result.raw_code) == 6
    assert result.challenge.status == PhoneVerificationStatus.PENDING
    assert result.challenge.phone_number == investor.phone_number
    outbox_message = OutboxMessage.objects.get(
        topic="sms.phone_verification_requested",
        idempotency_key=f"phone-verification:{result.challenge.id}",
    )
    assert "code" not in outbox_message.payload
    assert outbox_message.payload["delivery_secret_ref"] == str(result.challenge.id)
    assert outbox_message.payload["secret_redacted"] is True
    result.challenge.refresh_from_db()
    assert result.raw_code not in result.challenge.encrypted_code
    assert delivery_secret_for_phone_verification(result.challenge) == result.raw_code
    assert AuditEvent.objects.filter(
        action="auth.phone_verification_requested",
        target_id=str(investor.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="PhoneVerificationRequested",
        aggregate_id=str(investor.id),
    ).exists()


@pytest.mark.django_db
def test_phone_verification_confirm_sets_user_phone_verified(investor: User) -> None:
    result = request_phone_verification(PhoneVerificationRequestCommand(user=investor))

    challenge = confirm_phone_verification(
        PhoneVerificationConfirmCommand(
            user=investor,
            challenge_id=str(result.challenge.id),
            raw_code=result.raw_code,
        )
    )

    assert challenge.status == PhoneVerificationStatus.VERIFIED
    investor.refresh_from_db()
    assert investor.phone_verified_at is not None
    assert AuditEvent.objects.filter(
        action="auth.phone_verified",
        target_id=str(investor.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="PhoneVerified",
        aggregate_id=str(investor.id),
    ).exists()

    with pytest.raises(InvalidOrExpiredCodeError):
        confirm_phone_verification(
            PhoneVerificationConfirmCommand(
                user=investor,
                challenge_id=str(result.challenge.id),
                raw_code=result.raw_code,
            )
        )


@pytest.mark.django_db
def test_phone_verification_confirm_rejects_challenge_owned_by_another_user(
    investor: User,
) -> None:
    other_user = User.objects.create_user(
        email="other@example.test",
        full_name="Other Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.PENDING_KYC,
        phone_number="+41790000001",
    )
    result = request_phone_verification(PhoneVerificationRequestCommand(user=investor))

    with pytest.raises(InvalidOrExpiredCodeError):
        confirm_phone_verification(
            PhoneVerificationConfirmCommand(
                user=other_user,
                challenge_id=str(result.challenge.id),
                raw_code=result.raw_code,
            )
        )

    result.challenge.refresh_from_db()
    investor.refresh_from_db()
    other_user.refresh_from_db()
    assert result.challenge.status == PhoneVerificationStatus.PENDING
    assert result.challenge.attempts == 0
    assert investor.phone_verified_at is None
    assert other_user.phone_verified_at is None
    assert AuditEvent.objects.filter(
        action="auth.phone_verification_failed",
        target_id=str(other_user.id),
        metadata__reason="invalid_expired_or_superseded",
    ).exists()


@pytest.mark.django_db
def test_phone_verification_enforces_max_attempts(investor: User) -> None:
    result = request_phone_verification(
        PhoneVerificationRequestCommand(user=investor, max_attempts=2)
    )
    wrong_code = "000000" if result.raw_code != "000000" else "111111"
    other_wrong_code = "222222" if result.raw_code != "222222" else "333333"

    with pytest.raises(InvalidOrExpiredCodeError):
        confirm_phone_verification(
            PhoneVerificationConfirmCommand(
                user=investor,
                challenge_id=str(result.challenge.id),
                raw_code=wrong_code,
            )
        )
    assert AuditEvent.objects.filter(
        action="auth.phone_verification_failed",
        target_id=str(investor.id),
        metadata__reason="invalid_code",
    ).exists()

    with pytest.raises(TooManyCodeAttemptsError):
        confirm_phone_verification(
            PhoneVerificationConfirmCommand(
                user=investor,
                challenge_id=str(result.challenge.id),
                raw_code=other_wrong_code,
            )
        )

    result.challenge.refresh_from_db()
    assert result.challenge.status == PhoneVerificationStatus.FAILED


@pytest.mark.django_db
def test_expired_phone_verification_is_rejected(investor: User) -> None:
    result = request_phone_verification(
        PhoneVerificationRequestCommand(user=investor, ttl=timedelta(seconds=-1))
    )

    with pytest.raises(InvalidOrExpiredCodeError):
        confirm_phone_verification(
            PhoneVerificationConfirmCommand(
                user=investor,
                challenge_id=str(result.challenge.id),
                raw_code=result.raw_code,
            )
        )

    result.challenge.refresh_from_db()
    assert result.challenge.status == PhoneVerificationStatus.EXPIRED


@pytest.mark.django_db
def test_phone_verification_request_enforces_cooldown(investor: User) -> None:
    request_phone_verification(PhoneVerificationRequestCommand(user=investor))

    with pytest.raises(PhoneVerificationThrottleError) as exc:
        request_phone_verification(PhoneVerificationRequestCommand(user=investor))
    assert exc.value.retry_after_seconds is not None
    assert exc.value.retry_after_seconds >= 1


@pytest.mark.django_db
def test_phone_verification_reissue_supersedes_prior_active_challenge(
    investor: User,
    settings: Any,
) -> None:
    settings.AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS = 0
    first = request_phone_verification(PhoneVerificationRequestCommand(user=investor))
    second = request_phone_verification(PhoneVerificationRequestCommand(user=investor))

    first.challenge.refresh_from_db()
    assert first.challenge.status == PhoneVerificationStatus.SUPERSEDED
    assert first.challenge.superseded_at is not None

    with pytest.raises(InvalidOrExpiredCodeError):
        confirm_phone_verification(
            PhoneVerificationConfirmCommand(
                user=investor,
                challenge_id=str(first.challenge.id),
                raw_code=first.raw_code,
            )
        )

    confirmed = confirm_phone_verification(
        PhoneVerificationConfirmCommand(
            user=investor,
            challenge_id=str(second.challenge.id),
            raw_code=second.raw_code,
        )
    )
    assert confirmed.status == PhoneVerificationStatus.VERIFIED


@pytest.mark.django_db
@override_settings(PHONE_VERIFICATION_PROVIDER="twilio_verify")
def test_twilio_phone_verification_request_uses_provider(
    investor: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_start(phone_number: str) -> PhoneVerificationStartResult:
        assert phone_number == investor.phone_number
        return PhoneVerificationStartResult(
            provider_reference="VE123",
            provider_status="pending",
        )

    monkeypatch.setattr("backend.apps.accounts_auth.services.start_twilio_verify", fake_start)

    result = request_phone_verification(PhoneVerificationRequestCommand(user=investor))

    assert result.raw_code == ""
    assert result.challenge.provider == "twilio_verify"
    assert result.challenge.provider_reference == "VE123"
    assert result.challenge.code_digest == ""
    assert result.challenge.encrypted_code == ""
    assert not OutboxMessage.objects.filter(topic="sms.phone_verification_requested").exists()


@pytest.mark.django_db
@override_settings(PHONE_VERIFICATION_PROVIDER="twilio_verify")
def test_twilio_phone_verification_confirm_uses_provider(
    investor: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.apps.accounts_auth.services.start_twilio_verify",
        lambda phone_number: PhoneVerificationStartResult("VE123", "pending"),
    )
    monkeypatch.setattr(
        "backend.apps.accounts_auth.services.check_twilio_verify",
        lambda phone_number, raw_code: PhoneVerificationCheckResult(
            approved=raw_code == "123456",
            provider_status="approved" if raw_code == "123456" else "pending",
            provider_reference="VE123",
        ),
    )
    result = request_phone_verification(PhoneVerificationRequestCommand(user=investor))

    with pytest.raises(InvalidOrExpiredCodeError):
        confirm_phone_verification(
            PhoneVerificationConfirmCommand(
                user=investor,
                challenge_id=str(result.challenge.id),
                raw_code="000000",
            )
        )

    confirmed = confirm_phone_verification(
        PhoneVerificationConfirmCommand(
            user=investor,
            challenge_id=str(result.challenge.id),
            raw_code="123456",
        )
    )

    assert confirmed.status == PhoneVerificationStatus.VERIFIED
    assert confirmed.attempts == 2
    investor.refresh_from_db()
    assert investor.phone_verified_at is not None


@override_settings(
    TWILIO_VERIFY_SERVICE_SID="VA11111111111111111111111111111111",
    TWILIO_API_KEY_SID="SK11111111111111111111111111111111",
    TWILIO_API_KEY_SECRET="test-secret",
    TWILIO_ACCOUNT_SID="",
    TWILIO_AUTH_TOKEN="",
    TWILIO_VERIFY_CHANNEL="sms",
    TWILIO_TIMEOUT_SECONDS=8,
)
def test_twilio_verify_provider_adapter_posts_start_and_check_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        "backend.apps.accounts_auth.phone_providers.urllib.request.build_opener",
        lambda handler: _FakeTwilioOpener(calls),
    )

    start = start_twilio_verify("+40740000000")
    check = check_twilio_verify("+40740000000", "123456")

    assert start.provider_reference == "VE-started"
    assert start.provider_status == "pending"
    assert check.provider_reference == "VE-checked"
    assert check.approved is True
    assert calls[0]["url"].endswith(
        "/Services/VA11111111111111111111111111111111/Verifications"
    )
    assert calls[0]["timeout"] == 8
    assert calls[0]["payload"] == {"To": "+40740000000", "Channel": "sms"}
    assert calls[1]["url"].endswith(
        "/Services/VA11111111111111111111111111111111/VerificationCheck"
    )
    assert calls[1]["payload"] == {"To": "+40740000000", "Code": "123456"}


@override_settings(
    ENVIRONMENT="staging",
    PHONE_VERIFICATION_PROVIDER="twilio_verify",
    TWILIO_ACCOUNT_SID="",
    TWILIO_AUTH_TOKEN="",
    TWILIO_API_KEY_SID="SK_test_key",
    TWILIO_API_KEY_SECRET="test-secret",
    TWILIO_VERIFY_SERVICE_SID="VA_test_service",
    TWILIO_TIMEOUT_SECONDS=10,
)
def test_phone_verification_deploy_check_accepts_twilio_api_key_auth() -> None:
    assert check_phone_verification_provider_config(None) == []


@override_settings(
    ENVIRONMENT="staging",
    PHONE_VERIFICATION_PROVIDER="twilio_verify",
    TWILIO_ACCOUNT_SID="",
    TWILIO_AUTH_TOKEN="",
    TWILIO_API_KEY_SID="",
    TWILIO_API_KEY_SECRET="",
    TWILIO_VERIFY_SERVICE_SID="VA_test_service",
    TWILIO_TIMEOUT_SECONDS=10,
)
def test_phone_verification_deploy_check_requires_some_twilio_auth() -> None:
    errors = check_phone_verification_provider_config(None)

    assert {error.id for error in errors} == {"accounts_auth.E002"}


@pytest.mark.django_db
def test_phone_verification_request_rejects_already_verified_user(investor: User) -> None:
    result = request_phone_verification(PhoneVerificationRequestCommand(user=investor))
    confirm_phone_verification(
        PhoneVerificationConfirmCommand(
            user=investor,
            challenge_id=str(result.challenge.id),
            raw_code=result.raw_code,
        )
    )
    investor.refresh_from_db()

    with pytest.raises(PhoneAlreadyVerifiedError):
        request_phone_verification(PhoneVerificationRequestCommand(user=investor))


@pytest.mark.django_db
def test_phone_verification_api_flow(client: Client, investor: User) -> None:
    client.force_login(investor)

    request_response = client.post(
        "/api/v1/auth/phone/request/",
        data={},
        content_type="application/json",
    )

    assert request_response.status_code == 202
    challenge_id = request_response.json()["challenge_id"]
    challenge = PhoneVerificationChallenge.objects.get(id=challenge_id)
    raw_code = delivery_secret_for_phone_verification(challenge)

    confirm_response = client.post(
        "/api/v1/auth/phone/confirm/",
        data={"challenge_id": challenge_id, "code": raw_code},
        content_type="application/json",
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json()["user"]["phone_verified"] is True


@pytest.mark.django_db
def test_phone_verification_request_api_returns_validation_error_for_missing_phone(
    client: Client,
    investor: User,
) -> None:
    investor.phone_number = ""
    investor.save(update_fields=["phone_number"])
    client.force_login(investor)

    response = client.post(
        "/api/v1/auth/phone/request/",
        data={},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Phone number is required."


@pytest.mark.django_db
def test_phone_verification_confirm_api_rejects_challenge_owned_by_another_user(
    client: Client,
    investor: User,
) -> None:
    other_user = User.objects.create_user(
        email="other@example.test",
        full_name="Other Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.PENDING_KYC,
        phone_number="+41790000001",
    )
    result = request_phone_verification(PhoneVerificationRequestCommand(user=investor))
    client.force_login(other_user)

    response = client.post(
        "/api/v1/auth/phone/confirm/",
        data={"challenge_id": str(result.challenge.id), "code": result.raw_code},
        content_type="application/json",
    )

    assert response.status_code == 400
    result.challenge.refresh_from_db()
    investor.refresh_from_db()
    other_user.refresh_from_db()
    assert result.challenge.status == PhoneVerificationStatus.PENDING
    assert result.challenge.attempts == 0
    assert investor.phone_verified_at is None
    assert other_user.phone_verified_at is None


@pytest.mark.django_db
def test_phone_verification_confirm_api_throttles_repeated_attempts(
    client: Client,
    investor: User,
    settings: Any,
) -> None:
    client.force_login(investor)

    for _ in range(settings.AUTH_PHONE_VERIFICATION_CONFIRM_HOURLY_LIMIT):
        response = client.post(
            "/api/v1/auth/phone/confirm/",
            data={"challenge_id": str(uuid.uuid4()), "code": "000000"},
            content_type="application/json",
        )
        assert response.status_code == 400

    blocked = client.post(
        "/api/v1/auth/phone/confirm/",
        data={"challenge_id": str(uuid.uuid4()), "code": "000000"},
        content_type="application/json",
    )

    assert blocked.status_code == 429


@pytest.mark.django_db
def test_phone_verification_api_throttles_repeated_request(
    client: Client,
    investor: User,
) -> None:
    client.force_login(investor)

    first = client.post(
        "/api/v1/auth/phone/request/",
        data={},
        content_type="application/json",
    )
    second = client.post(
        "/api/v1/auth/phone/request/",
        data={},
        content_type="application/json",
    )

    assert first.status_code == 202
    assert second.status_code == 429
    assert "detail" in second.json()
