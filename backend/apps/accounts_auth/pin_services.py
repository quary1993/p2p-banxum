"""IP of Webby-Soft SRL. Investor PIN for sensitive actions (ACC-DEC-009).

Every sensitive investor action needs the email code and the 6-digit PIN. The PIN is
stored only as a Django password hash. Five wrong PINs in a row lock it for 30 minutes
(``AUTH_PIN_MAX_ATTEMPTS``, ``AUTH_PIN_LOCK_SECONDS``); a correct PIN resets the count.

- First PIN at registration (pending KYC, phone verified): no email code.
- First PIN of any other account: an email code for ``pin_setup``.
- Change: current PIN, an email code for ``pin_change`` and the new PIN twice.
- Forgot PIN: an email code for ``pin_reset``, an SMS code to the verified phone and
  the new PIN twice. It clears the lock.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from backend.apps.accounts_auth.crypto import digest_secret, encrypt_delivery_secret
from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    PhoneVerificationChallenge,
    PhoneVerificationPurpose,
    PhoneVerificationStatus,
    SensitiveAction,
    SensitiveActionPin,
    User,
)
from backend.apps.accounts_auth.phone_providers import (
    PhoneProviderError,
    check_twilio_verify,
    start_twilio_verify,
)
from backend.apps.accounts_auth.services import (
    LOCAL_PHONE_VERIFICATION_PROVIDERS,
    MAGIC_LINK_ACCOUNT_TYPES,
    TWILIO_VERIFY_PROVIDER,
    AccountsAuthError,
    InvalidOrExpiredCodeError,
    PhoneVerificationProviderError,
    PhoneVerificationThrottleError,
    SensitiveActionCodeConsumeCommand,
    TooManyCodeAttemptsError,
    _dispatch_auth_email_after_commit,
    _support_email,
    actor_for_user,
    consume_sensitive_action_code,
)
from backend.apps.platform_core.domain.time import to_business_time
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message

PIN_LENGTH = 6
_PIN_PATTERN = re.compile(r"\d{6}")


# ---- Errors -------------------------------------------------------------------------------
# Each error carries the API code and status, documented in plan/03 ACC-DEC-009.


class PinError(AccountsAuthError):
    code = "pin_error"
    http_status = 400

    def __init__(self, message: str, **extra: object) -> None:
        super().__init__(message)
        self.extra: dict[str, object] = dict(extra)

    def payload(self) -> dict[str, object]:
        return {"detail": str(self), "code": self.code, **self.extra}


class PinRequiredError(PinError):
    """The account has no PIN yet."""

    code = "pin_required"
    http_status = 409


class PinInvalidError(PinError):
    """Wrong PIN; ``attempts_left`` before the lock."""

    code = "pin_invalid"
    http_status = 400


class PinLockedError(PinError):
    """Too many wrong PINs; ``locked_until`` is an ISO timestamp."""

    code = "pin_locked"
    http_status = 423


class PinWeakError(PinError):
    """The new PIN is not 6 digits, repeats one digit or is a straight run."""

    code = "pin_weak"
    http_status = 400


class PinMismatchError(PinError):
    code = "pin_mismatch"
    http_status = 400


class PinUnchangedError(PinError):
    code = "pin_unchanged"
    http_status = 400


class PinAlreadySetError(PinError):
    code = "pin_already_set"
    http_status = 409


class PinNotAvailableError(PinError):
    """Admins, blocked accounts and other non-investor accounts have no PIN."""

    code = "pin_not_available"
    http_status = 403


class PinPhoneVerificationRequiredError(PinError):
    code = "phone_verification_required"
    http_status = 409


class PinResetUnavailableError(PinError):
    """No verified phone number to send the reset SMS to."""

    code = "pin_reset_unavailable"
    http_status = 409


class PhoneCodeInvalidError(InvalidOrExpiredCodeError):
    """The SMS code of a PIN reset is wrong, expired or replaced."""

    code = "phone_code_invalid"


class PhoneCodeAttemptsError(TooManyCodeAttemptsError):
    code = "phone_code_attempts_exceeded"


# ---- Rules --------------------------------------------------------------------------------


def pin_weakness(pin: str) -> str | None:
    """Why a new PIN is refused, or None when it is acceptable."""

    if not _PIN_PATTERN.fullmatch(pin):
        return "Your PIN must be exactly 6 digits."
    if len(set(pin)) == 1:
        return "Choose a PIN that does not repeat one digit, like 111111."
    steps = {int(after) - int(before) for before, after in zip(pin, pin[1:], strict=False)}
    if steps in ({1}, {-1}):
        return "Choose a PIN that is not a straight run of digits, like 123456 or 654321."
    return None


def _validate_new_pin(new_pin: str, confirmation: str) -> None:
    weakness = pin_weakness(new_pin)
    if weakness is not None:
        raise PinWeakError(weakness)
    if not secrets.compare_digest(new_pin, confirmation):
        raise PinMismatchError("The two PINs do not match. Enter the same PIN twice.")


def _can_have_pin(user: User) -> bool:
    return user.is_active and user.can_login and user.account_type in MAGIC_LINK_ACCOUNT_TYPES


def _require_pin_account(user: Any) -> User:
    if not isinstance(user, User) or not _can_have_pin(user):
        raise PinNotAvailableError("This account cannot use a PIN.")
    return user


def registration_pin_allowed(user: User) -> bool:
    """The registration step: the user just proved the email and phone, no money yet."""

    return (
        user.account_type == AccountType.NATURAL_PERSON_LENDER
        and user.status == AccountStatus.PENDING_KYC
        and user.is_phone_verified
    )


def _format_lock_time(value: datetime) -> str:
    local = to_business_time(value)
    return f"{local.strftime('%H:%M')} (Zurich time)"


# ---- Status -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PinStatus:
    pin_set: bool
    locked_until: datetime | None
    attempts_left: int
    max_attempts: int
    setup_requires_email_code: bool
    reset_available: bool
    phone_last_digits: str


def _max_attempts() -> int:
    return max(int(settings.AUTH_PIN_MAX_ATTEMPTS), 1)


def _lock_duration() -> timedelta:
    return timedelta(seconds=max(int(settings.AUTH_PIN_LOCK_SECONDS), 1))


def _active_lock(record: SensitiveActionPin | None, now: datetime) -> datetime | None:
    if record is None or record.locked_until is None or record.locked_until <= now:
        return None
    return record.locked_until


def user_has_pin(user: Any) -> bool:
    return SensitiveActionPin.objects.filter(user_id=str(user.pk)).exists()


def pin_locked_until(user: Any) -> datetime | None:
    record = SensitiveActionPin.objects.filter(user_id=str(user.pk)).first()
    return _active_lock(record, timezone.now())


def _phone_last_digits(user: User) -> str:
    digits = re.sub(r"\D", "", user.phone_number or "")
    return digits[-2:] if user.is_phone_verified and len(digits) >= 2 else ""


def pin_status_for_user(user: User) -> PinStatus:
    record = SensitiveActionPin.objects.filter(user_id=user.pk).first()
    now = timezone.now()
    locked_until = _active_lock(record, now)
    max_attempts = _max_attempts()
    failed = 0 if record is None or locked_until is not None else int(record.failed_attempts)
    return PinStatus(
        pin_set=record is not None,
        locked_until=locked_until,
        attempts_left=0 if locked_until is not None else max(max_attempts - failed, 0),
        max_attempts=max_attempts,
        setup_requires_email_code=not registration_pin_allowed(user),
        reset_available=bool(_phone_last_digits(user)),
        phone_last_digits=_phone_last_digits(user),
    )


# ---- Verification -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VerifyPinCommand:
    user: Any
    pin: str = field(repr=False)
    action: str = ""
    ip_address: str | None = None
    user_agent: str = ""


def _audit(user: User, action: str, metadata: dict[str, object] | None = None) -> None:
    record_audit_event(
        AuditCommand(
            actor=actor_for_user(user),
            action=action,
            target_type="User",
            target_id=str(user.pk),
            metadata=metadata or {},
        )
    )


def verify_pin(command: VerifyPinCommand) -> None:
    """Check the PIN of a sensitive action: lock first, then the PIN.

    Wrong PINs commit their count before the error is raised, so call this outside a
    rollbackable transaction (like the email-code check).
    """

    user = command.user
    if not isinstance(user, User):
        raise PinNotAvailableError("This account cannot use a PIN.")
    failure: PinError | None = None
    with transaction.atomic():
        record = SensitiveActionPin.objects.select_for_update().filter(user_id=user.pk).first()
        now = timezone.now()
        locked_until = _active_lock(record, now)
        if record is None:
            _audit(user, "auth.pin_check_failed", {"action": command.action, "reason": "no_pin"})
            failure = PinRequiredError(
                "Create your PIN first. You need it with the email code for every "
                "investment, withdrawal and bank change."
            )
        elif locked_until is not None:
            _audit(user, "auth.pin_check_failed", {"action": command.action, "reason": "locked"})
            failure = PinLockedError(
                "Your PIN is locked after too many wrong attempts. Try again after "
                f"{_format_lock_time(locked_until)} or use Forgot PIN.",
                locked_until=locked_until.isoformat(),
            )
        elif _PIN_PATTERN.fullmatch(command.pin) and check_password(command.pin, record.pin_hash):
            if record.failed_attempts or record.locked_until is not None:
                record.failed_attempts = 0
                record.locked_until = None
                record.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
            _audit(user, "auth.pin_verified", {"action": command.action})
        else:
            failure = _record_wrong_pin(record, user=user, action=command.action, now=now)
    if failure is not None:
        raise failure


def _record_wrong_pin(
    record: SensitiveActionPin,
    *,
    user: User,
    action: str,
    now: datetime,
) -> PinError:
    max_attempts = _max_attempts()
    record.failed_attempts = int(record.failed_attempts) + 1
    record.last_failed_at = now
    if record.failed_attempts < max_attempts:
        record.locked_until = None
        record.save(
            update_fields=["failed_attempts", "last_failed_at", "locked_until", "updated_at"]
        )
        attempts_left = max_attempts - record.failed_attempts
        _audit(
            user,
            "auth.pin_check_failed",
            {"action": action, "reason": "wrong_pin", "attempts_left": attempts_left},
        )
        return PinInvalidError(
            "Wrong PIN. "
            + (
                "1 attempt left before your PIN is locked."
                if attempts_left == 1
                else f"{attempts_left} attempts left before your PIN is locked."
            ),
            attempts_left=attempts_left,
        )

    locked_until = now + _lock_duration()
    record.failed_attempts = 0
    record.locked_until = locked_until
    record.save(update_fields=["failed_attempts", "last_failed_at", "locked_until", "updated_at"])
    _audit(
        user,
        "auth.pin_locked",
        {
            "action": action,
            "max_attempts": max_attempts,
            "locked_until": locked_until.isoformat(),
        },
    )
    _enqueue_pin_notice(
        user,
        topic="email.pin_locked",
        idempotency_key=f"pin-locked-notice:{user.pk}:{locked_until.isoformat()}",
        subject=f"Your {settings.PLATFORM_BRAND_NAME} PIN is locked",
        status_label="Important",
        status_tone="danger",
        body_text=(
            f"Your PIN was locked after {max_attempts} wrong attempts. You cannot confirm "
            "investments, withdrawals or bank changes until "
            f"{_format_lock_time(locked_until)}.\n\n"
            "If you forgot your PIN, use Forgot PIN in Settings to set a new one.\n\n"
            "If this was not you, contact support at "
            f"{_support_email()} and do not share your email or SMS codes."
        ),
        template_key="accounts.pin_locked.v1",
    )
    return PinLockedError(
        f"Wrong PIN. Your PIN is now locked after {max_attempts} wrong attempts. Try again "
        f"after {_format_lock_time(locked_until)} or use Forgot PIN.",
        locked_until=locked_until.isoformat(),
    )


def _enqueue_pin_notice(
    user: User,
    *,
    topic: str,
    idempotency_key: str,
    subject: str,
    status_label: str,
    status_tone: str,
    body_text: str,
    template_key: str,
) -> None:
    outbox_message = enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=idempotency_key,
            topic=topic,
            payload={
                "user_id": str(user.pk),
                "email": user.email,
                "subject": subject,
                "headline": subject,
                "notice_label": "Security notice",
                "status_label": status_label,
                "status_tone": status_tone,
                "body_text": body_text,
                "template_key": template_key,
            },
        )
    )
    _dispatch_auth_email_after_commit(outbox_message.id)


def _notify_pin_changed(user: User, *, changed_at: datetime, reason: str) -> None:
    brand = settings.PLATFORM_BRAND_NAME
    _enqueue_pin_notice(
        user,
        topic="email.pin_changed",
        idempotency_key=f"pin-changed-notice:{user.pk}:{reason}:{changed_at.isoformat()}",
        subject=f"Your {brand} PIN was changed",
        status_label="Information",
        status_tone="info",
        body_text=(
            f"Your {brand} PIN was changed. From now on, use the new PIN with the email "
            "code to confirm investments, withdrawals and bank changes.\n\n"
            f"If this was not you, contact support at {_support_email()}."
        ),
        template_key="accounts.pin_changed.v1",
    )


# ---- Email and SMS codes ------------------------------------------------------------------


def _use_email_code(
    user: User,
    *,
    action: SensitiveAction,
    code_id: str,
    raw_code: str,
    ip_address: str | None,
    user_agent: str,
    consume: bool = True,
) -> None:
    if not str(code_id).strip() or not str(raw_code).strip():
        raise InvalidOrExpiredCodeError("Enter the 6-digit code we sent to your email.")
    consume_sensitive_action_code(
        SensitiveActionCodeConsumeCommand(
            code_id=str(code_id).strip(),
            raw_code=str(raw_code).strip(),
            expected_user=user,
            expected_action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            consume=consume,
        )
    )


@dataclass(frozen=True, slots=True)
class StartPinResetCommand:
    user: Any
    ip_address: str | None = None
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class StartPinResetResult:
    challenge: PhoneVerificationChallenge
    # Local and mock providers only; empty with Twilio Verify.
    raw_code: str = field(repr=False, default="")
    phone_last_digits: str = ""


def _phone_provider() -> str:
    return str(settings.PHONE_VERIFICATION_PROVIDER).strip().lower()


@transaction.atomic
def start_pin_reset(command: StartPinResetCommand) -> StartPinResetResult:
    """Send the SMS code of a forgotten-PIN reset to the verified phone number."""

    user = _require_pin_account(command.user)
    if not _phone_last_digits(user):
        raise PinResetUnavailableError(
            "We cannot send an SMS code because your account has no verified phone number. "
            f"Contact support at {_support_email()}."
        )
    User.objects.select_for_update().filter(pk=user.pk).first()
    now = timezone.now()
    ttl = timedelta(seconds=int(settings.AUTH_PHONE_VERIFICATION_TTL_SECONDS))
    cooldown = timedelta(seconds=int(settings.AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS))
    pending = PhoneVerificationChallenge.objects.filter(
        user=user,
        purpose=PhoneVerificationPurpose.PIN_RESET,
        status=PhoneVerificationStatus.PENDING,
        superseded_at__isnull=True,
        expires_at__gt=now,
    )
    latest = pending.order_by("-created_at").first()
    if latest is not None:
        # Real-time cooldown, as for the registration SMS (QA clock safe).
        elapsed = now - (latest.expires_at - ttl)
        if elapsed < cooldown:
            retry_after = max(1, int((cooldown - elapsed).total_seconds()) + 1)
            raise PhoneVerificationThrottleError(
                f"An SMS code was sent moments ago. Try again in {retry_after} seconds.",
                retry_after_seconds=retry_after,
            )
        pending.update(status=PhoneVerificationStatus.SUPERSEDED, superseded_at=now)

    provider = _phone_provider()
    if provider in LOCAL_PHONE_VERIFICATION_PROVIDERS:
        raw_code = f"{secrets.randbelow(1_000_000):06d}"
        code_digest = digest_secret(raw_code)
        encrypted_code = encrypt_delivery_secret(raw_code)
    elif provider == TWILIO_VERIFY_PROVIDER:
        raw_code = ""
        code_digest = ""
        encrypted_code = ""
    else:
        raise PhoneVerificationProviderError(
            f"Unsupported phone verification provider '{provider}'."
        )
    challenge = PhoneVerificationChallenge.objects.create(
        user=user,
        purpose=PhoneVerificationPurpose.PIN_RESET,
        phone_number=user.phone_number,
        provider=provider,
        code_digest=code_digest,
        encrypted_code=encrypted_code,
        expires_at=now + ttl,
        max_attempts=int(settings.AUTH_PHONE_VERIFICATION_MAX_ATTEMPTS),
        requested_ip=command.ip_address,
        requested_user_agent=command.user_agent,
    )
    if provider == TWILIO_VERIFY_PROVIDER:
        try:
            provider_result = start_twilio_verify(user.phone_number)
        except PhoneProviderError as exc:
            raise PhoneVerificationProviderError(
                "Phone verification provider is unavailable."
            ) from exc
        challenge.provider_reference = provider_result.provider_reference
        challenge.save(update_fields=["provider_reference", "updated_at"])
    else:
        enqueue_outbox_message(
            OutboxCommand(
                idempotency_key=f"phone-verification:{challenge.id}",
                topic="sms.phone_verification_requested",
                payload={
                    "user_id": str(user.pk),
                    "phone_number": user.phone_number,
                    "purpose": PhoneVerificationPurpose.PIN_RESET,
                    "delivery_secret_type": "phone_verification_code",
                    "delivery_secret_ref": str(challenge.id),
                    "secret_redacted": True,
                    "expires_at": challenge.expires_at.isoformat(),
                },
            )
        )
    _audit(user, "auth.pin_reset_sms_requested", {"provider": provider})
    return StartPinResetResult(
        challenge=challenge,
        raw_code=raw_code,
        phone_last_digits=_phone_last_digits(user),
    )


def _verify_reset_sms(
    user: User,
    *,
    challenge_id: str,
    raw_code: str,
    ip_address: str | None,
    user_agent: str,
) -> None:
    failure: AccountsAuthError | None = None
    with transaction.atomic():
        challenge = (
            PhoneVerificationChallenge.objects.select_for_update()
            .filter(id=challenge_id, user=user, purpose=PhoneVerificationPurpose.PIN_RESET)
            .first()
        )
        now = timezone.now()
        if (
            challenge is None
            or challenge.status != PhoneVerificationStatus.PENDING
            or challenge.superseded_at is not None
            or challenge.expires_at <= now
        ):
            _audit(user, "auth.pin_reset_sms_failed", {"reason": "invalid_expired_or_superseded"})
            failure = PhoneCodeInvalidError(
                "The SMS code is invalid or expired. Send a new SMS code."
            )
        elif challenge.attempts >= challenge.max_attempts:
            _audit(user, "auth.pin_reset_sms_failed", {"reason": "too_many_attempts"})
            failure = PhoneCodeAttemptsError("Too many wrong SMS codes. Send a new SMS code.")
        else:
            provider = str(challenge.provider).strip().lower()
            code_is_valid = False
            if provider == TWILIO_VERIFY_PROVIDER:
                try:
                    result = check_twilio_verify(challenge.phone_number, raw_code)
                except PhoneProviderError:
                    failure = PhoneVerificationProviderError(
                        "Phone verification provider is unavailable."
                    )
                else:
                    code_is_valid = result.approved
            else:
                code_is_valid = bool(challenge.code_digest) and secrets.compare_digest(
                    challenge.code_digest, digest_secret(raw_code)
                )
            if failure is None:
                challenge.attempts += 1
                if code_is_valid:
                    challenge.status = PhoneVerificationStatus.VERIFIED
                    challenge.verified_at = now
                    challenge.confirmed_ip = ip_address
                    challenge.confirmed_user_agent = user_agent
                elif challenge.attempts >= challenge.max_attempts:
                    challenge.status = PhoneVerificationStatus.FAILED
                challenge.save()
                if not code_is_valid:
                    _audit(
                        user,
                        "auth.pin_reset_sms_failed",
                        {"reason": "invalid_code", "provider": provider},
                    )
                    failure = (
                        PhoneCodeAttemptsError("Too many wrong SMS codes. Send a new SMS code.")
                        if challenge.status == PhoneVerificationStatus.FAILED
                        else PhoneCodeInvalidError(
                            "The SMS code is wrong. Check the code and try again."
                        )
                    )
    if failure is not None:
        raise failure


# ---- Set, change, reset -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetPinCommand:
    user: Any
    new_pin: str = field(repr=False)
    new_pin_confirmation: str = field(repr=False)
    sensitive_action_code_id: str = ""
    sensitive_action_code: str = field(repr=False, default="")
    ip_address: str | None = None
    user_agent: str = ""


def set_first_pin(command: SetPinCommand) -> SensitiveActionPin:
    """Create the account's first PIN (registration step or the post-login screen)."""

    user = _require_pin_account(command.user)
    _validate_new_pin(command.new_pin, command.new_pin_confirmation)
    if user_has_pin(user):
        raise PinAlreadySetError(
            "You already have a PIN. Use Change PIN or Forgot PIN in Settings."
        )
    registration = registration_pin_allowed(user)
    if not registration:
        if user.status == AccountStatus.PENDING_KYC and not user.is_phone_verified:
            raise PinPhoneVerificationRequiredError(
                "Verify your phone number before you create your PIN."
            )
        _use_email_code(
            user,
            action=SensitiveAction.PIN_SETUP,
            code_id=command.sensitive_action_code_id,
            raw_code=command.sensitive_action_code,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
    pin_hash = make_password(command.new_pin)
    with transaction.atomic():
        User.objects.select_for_update().filter(pk=user.pk).first()
        if SensitiveActionPin.objects.filter(user_id=user.pk).exists():
            raise PinAlreadySetError(
                "You already have a PIN. Use Change PIN or Forgot PIN in Settings."
            )
        now = timezone.now()
        record = SensitiveActionPin.objects.create(
            user=user,
            pin_hash=pin_hash,
            set_at=now,
            changed_at=now,
        )
        _audit(
            user,
            "auth.pin_set",
            {"source": "registration" if registration else "pin_setup"},
        )
    return record


@dataclass(frozen=True, slots=True)
class ChangePinCommand:
    user: Any
    pin: str = field(repr=False)
    new_pin: str = field(repr=False)
    new_pin_confirmation: str = field(repr=False)
    sensitive_action_code_id: str = ""
    sensitive_action_code: str = field(repr=False, default="")
    ip_address: str | None = None
    user_agent: str = ""


def change_pin(command: ChangePinCommand) -> SensitiveActionPin:
    """Current PIN, then email code, then the new PIN replaces the old one."""

    user = _require_pin_account(command.user)
    _validate_new_pin(command.new_pin, command.new_pin_confirmation)
    verify_pin(
        VerifyPinCommand(
            user=user,
            pin=command.pin,
            action=SensitiveAction.PIN_CHANGE,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
    )
    if secrets.compare_digest(command.pin, command.new_pin):
        raise PinUnchangedError("Your new PIN must be different from your current PIN.")
    _use_email_code(
        user,
        action=SensitiveAction.PIN_CHANGE,
        code_id=command.sensitive_action_code_id,
        raw_code=command.sensitive_action_code,
        ip_address=command.ip_address,
        user_agent=command.user_agent,
    )
    return _replace_pin(user, new_pin=command.new_pin, reason="changed")


@dataclass(frozen=True, slots=True)
class ConfirmPinResetCommand:
    user: Any
    phone_challenge_id: str
    phone_code: str = field(repr=False)
    new_pin: str = field(repr=False)
    new_pin_confirmation: str = field(repr=False)
    sensitive_action_code_id: str = ""
    sensitive_action_code: str = field(repr=False, default="")
    ip_address: str | None = None
    user_agent: str = ""


def confirm_pin_reset(command: ConfirmPinResetCommand) -> SensitiveActionPin:
    """Email code and SMS code prove the owner; the new PIN replaces the old one.

    The email code is checked first without being used up, so a wrong SMS code does
    not cost the email code. Both are used only when both are right.
    """

    user = _require_pin_account(command.user)
    if not _phone_last_digits(user):
        raise PinResetUnavailableError(
            "We cannot reset your PIN without a verified phone number. "
            f"Contact support at {_support_email()}."
        )
    _validate_new_pin(command.new_pin, command.new_pin_confirmation)
    _use_email_code(
        user,
        action=SensitiveAction.PIN_RESET,
        code_id=command.sensitive_action_code_id,
        raw_code=command.sensitive_action_code,
        ip_address=command.ip_address,
        user_agent=command.user_agent,
        consume=False,
    )
    _verify_reset_sms(
        user,
        challenge_id=command.phone_challenge_id,
        raw_code=command.phone_code,
        ip_address=command.ip_address,
        user_agent=command.user_agent,
    )
    _use_email_code(
        user,
        action=SensitiveAction.PIN_RESET,
        code_id=command.sensitive_action_code_id,
        raw_code=command.sensitive_action_code,
        ip_address=command.ip_address,
        user_agent=command.user_agent,
    )
    return _replace_pin(user, new_pin=command.new_pin, reason="reset")


def _replace_pin(user: User, *, new_pin: str, reason: str) -> SensitiveActionPin:
    pin_hash = make_password(new_pin)
    with transaction.atomic():
        record = SensitiveActionPin.objects.select_for_update().filter(user_id=user.pk).first()
        now = timezone.now()
        was_locked = _active_lock(record, now) is not None
        if record is None:
            record = SensitiveActionPin.objects.create(
                user=user,
                pin_hash=pin_hash,
                set_at=now,
                changed_at=now,
            )
        else:
            record.pin_hash = pin_hash
            record.changed_at = now
            record.failed_attempts = 0
            record.locked_until = None
            record.save(
                update_fields=[
                    "pin_hash",
                    "changed_at",
                    "failed_attempts",
                    "locked_until",
                    "updated_at",
                ]
            )
        _audit(user, f"auth.pin_{reason}", {"lock_cleared": was_locked})
        _notify_pin_changed(user, changed_at=now, reason=reason)
    return record


# ---- Synthetic QA accounts ----------------------------------------------------------------


def assign_known_qa_pin(user: Any, *, pin: str, source: str, replace: bool = False) -> bool:
    """Give a synthetic QA investor a known PIN; never in production.

    ``replace`` also resets a PIN the tester changed and clears a lock. Returns True
    when a PIN was written.
    """

    if settings.IS_PRODUCTION or settings.ENVIRONMENT not in {"local", "staging", "test"}:
        raise AccountsAuthError("Known QA PINs are forbidden in production.")
    account = _require_pin_account(user)
    if pin_weakness(pin) is not None:
        raise PinWeakError("The QA PIN must follow the PIN rules.")
    record = SensitiveActionPin.objects.select_for_update().filter(user_id=account.pk).first()
    if record is not None and not replace:
        return False
    now = timezone.now()
    if record is None:
        SensitiveActionPin.objects.create(
            user=account,
            pin_hash=make_password(pin),
            set_at=now,
            changed_at=now,
        )
    else:
        record.pin_hash = make_password(pin)
        record.changed_at = now
        record.failed_attempts = 0
        record.locked_until = None
        record.save(
            update_fields=[
                "pin_hash",
                "changed_at",
                "failed_attempts",
                "locked_until",
                "updated_at",
            ]
        )
    _audit(account, "auth.pin_set", {"source": source, "qa_known_pin": True})
    return True
