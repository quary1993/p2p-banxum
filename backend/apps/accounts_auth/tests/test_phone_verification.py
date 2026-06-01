from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.test import Client

from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    PhoneVerificationChallenge,
    PhoneVerificationStatus,
    User,
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
                challenge_id=str(result.challenge.id),
                raw_code=result.raw_code,
            )
        )


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
                challenge_id=str(result.challenge.id),
                raw_code=result.raw_code,
            )
        )

    result.challenge.refresh_from_db()
    assert result.challenge.status == PhoneVerificationStatus.EXPIRED


@pytest.mark.django_db
def test_phone_verification_request_enforces_cooldown(investor: User) -> None:
    request_phone_verification(PhoneVerificationRequestCommand(user=investor))

    with pytest.raises(PhoneVerificationThrottleError):
        request_phone_verification(PhoneVerificationRequestCommand(user=investor))


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
                challenge_id=str(first.challenge.id),
                raw_code=first.raw_code,
            )
        )

    confirmed = confirm_phone_verification(
        PhoneVerificationConfirmCommand(
            challenge_id=str(second.challenge.id),
            raw_code=second.raw_code,
        )
    )
    assert confirmed.status == PhoneVerificationStatus.VERIFIED


@pytest.mark.django_db
def test_phone_verification_request_rejects_already_verified_user(investor: User) -> None:
    result = request_phone_verification(PhoneVerificationRequestCommand(user=investor))
    confirm_phone_verification(
        PhoneVerificationConfirmCommand(
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
