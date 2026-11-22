"""IP of Webby-Soft SRL. 18.5: SMS codes to the verified phone as a second factor.

Used by sign-in, password reset and security changes (purposes ``sign_in`` and ``security``).
The flow is the one of the forgotten-PIN SMS: Twilio Verify in production, a local code with the
mock provider; a real-time cooldown; a limited number of attempts per code.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from backend.apps.accounts_auth.crypto import digest_secret, encrypt_delivery_secret
from backend.apps.accounts_auth.models import (
    PhoneVerificationChallenge,
    PhoneVerificationStatus,
    User,
)
from backend.apps.accounts_auth.phone_providers import (
    PhoneProviderError,
    check_twilio_verify,
    start_twilio_verify,
)
from backend.apps.accounts_auth.services import (
    LOCAL_PHONE_VERIFICATION_PROVIDERS,
    TWILIO_VERIFY_PROVIDER,
    PhoneVerificationProviderError,
    PhoneVerificationThrottleError,
    lock_account_for_sms,
)
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message
from backend.apps.platform_core.services.ip_privacy import keyed_ip_hash as ip_hash


class FactorSmsError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _provider() -> str:
    return str(settings.PHONE_VERIFICATION_PROVIDER).strip().lower()


def latest_pending(user: User, *, purpose: str) -> PhoneVerificationChallenge | None:
    return (
        PhoneVerificationChallenge.objects.filter(
            user=user,
            purpose=purpose,
            status=PhoneVerificationStatus.PENDING,
            superseded_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )


@transaction.atomic
def send_code(
    user: User, *, purpose: str, ip_address: str | None = None, user_agent: str = ""
) -> tuple[PhoneVerificationChallenge, str]:
    """Send a code to the verified phone. Returns the challenge and, for the mock provider only,
    the code (tests and local development)."""
    if not user.phone_verified_at or not user.phone_number:
        raise FactorSmsError(
            "Your account has no verified phone number for an SMS code.", code="no_verified_phone"
        )
    now = timezone.now()
    # Audit S4-2: the account lock and the account-wide SMS limits (hour and day).
    lock_account_for_sms(user, now=now)
    ttl = timedelta(seconds=int(settings.AUTH_PHONE_VERIFICATION_TTL_SECONDS))
    cooldown = timedelta(seconds=int(settings.AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS))
    pending = PhoneVerificationChallenge.objects.filter(
        user=user,
        purpose=purpose,
        status=PhoneVerificationStatus.PENDING,
        superseded_at__isnull=True,
        expires_at__gt=now,
    )
    latest = pending.order_by("-created_at").first()
    if latest is not None:
        elapsed = now - (latest.expires_at - ttl)
        if elapsed < cooldown:
            retry_after = max(1, int((cooldown - elapsed).total_seconds()) + 1)
            raise PhoneVerificationThrottleError(
                f"An SMS code was sent moments ago. Try again in {retry_after} seconds.",
                retry_after_seconds=retry_after,
            )
        pending.update(status=PhoneVerificationStatus.SUPERSEDED, superseded_at=now)
    provider = _provider()
    if provider in LOCAL_PHONE_VERIFICATION_PROVIDERS:
        raw_code = f"{secrets.randbelow(1_000_000):06d}"
        code_digest = digest_secret(raw_code)
        encrypted_code = encrypt_delivery_secret(raw_code)
    elif provider == TWILIO_VERIFY_PROVIDER:
        raw_code, code_digest, encrypted_code = "", "", ""
    else:
        raise PhoneVerificationProviderError(
            f"Unsupported phone verification provider '{provider}'."
        )
    challenge = PhoneVerificationChallenge.objects.create(
        user=user,
        purpose=purpose,
        phone_number=user.phone_number,
        provider=provider,
        code_digest=code_digest,
        encrypted_code=encrypted_code,
        expires_at=now + ttl,
        max_attempts=int(settings.AUTH_PHONE_VERIFICATION_MAX_ATTEMPTS),
        requested_ip_hash=ip_hash(ip_address),
        requested_user_agent=user_agent,
    )
    if provider == TWILIO_VERIFY_PROVIDER:
        try:
            result = start_twilio_verify(user.phone_number)
        except PhoneProviderError as exc:
            raise PhoneVerificationProviderError(
                "Phone verification provider is unavailable."
            ) from exc
        challenge.provider_reference = result.provider_reference
        challenge.save(update_fields=["provider_reference", "updated_at"])
    else:
        enqueue_outbox_message(
            OutboxCommand(
                idempotency_key=f"phone-verification:{challenge.id}",
                topic="sms.phone_verification_requested",
                payload={
                    "user_id": str(user.pk),
                    "phone_number": user.phone_number,
                    "purpose": purpose,
                    "delivery_secret_type": "phone_verification_code",
                    "delivery_secret_ref": str(challenge.id),
                    "secret_redacted": True,
                    "expires_at": challenge.expires_at.isoformat(),
                },
            )
        )
    return challenge, raw_code


def check_code(
    user: User,
    *,
    challenge_id: str,
    raw_code: str,
    purpose: str,
    ip_address: str | None = None,
    user_agent: str = "",
) -> None:
    """Check an SMS code; a wrong code counts as an attempt (committed on its own)."""
    failure: FactorSmsError | PhoneVerificationProviderError | None = None
    with transaction.atomic():
        challenge = (
            PhoneVerificationChallenge.objects.select_for_update()
            .filter(id=challenge_id, user=user, purpose=purpose)
            .first()
        )
        now = timezone.now()
        if (
            challenge is None
            or challenge.status != PhoneVerificationStatus.PENDING
            or challenge.superseded_at is not None
            or challenge.expires_at <= now
        ):
            failure = FactorSmsError(
                "The SMS code is invalid or expired. Send a new SMS code.", code="sms_code_invalid"
            )
        elif challenge.attempts >= challenge.max_attempts:
            failure = FactorSmsError(
                "Too many wrong SMS codes. Send a new SMS code.", code="sms_code_attempts"
            )
        else:
            provider = str(challenge.provider).strip().lower()
            valid = False
            if provider == TWILIO_VERIFY_PROVIDER:
                try:
                    valid = check_twilio_verify(challenge.phone_number, raw_code).approved
                except PhoneProviderError:
                    failure = PhoneVerificationProviderError(
                        "Phone verification provider is unavailable."
                    )
            else:
                valid = bool(challenge.code_digest) and secrets.compare_digest(
                    challenge.code_digest, digest_secret(str(raw_code).strip())
                )
            if failure is None:
                challenge.attempts += 1
                if valid:
                    challenge.status = PhoneVerificationStatus.VERIFIED
                    challenge.verified_at = now
                    challenge.confirmed_ip_hash = ip_hash(ip_address)
                    challenge.confirmed_user_agent = user_agent
                elif challenge.attempts >= challenge.max_attempts:
                    challenge.status = PhoneVerificationStatus.FAILED
                challenge.save()
                if not valid:
                    failure = FactorSmsError(
                        "Too many wrong SMS codes. Send a new SMS code."
                        if challenge.status == PhoneVerificationStatus.FAILED
                        else "The SMS code is wrong. Check the code and try again.",
                        code=(
                            "sms_code_attempts"
                            if challenge.status == PhoneVerificationStatus.FAILED
                            else "sms_code_invalid"
                        ),
                    )
    if failure is not None:
        raise failure
