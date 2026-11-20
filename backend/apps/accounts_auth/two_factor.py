"""IP of Webby-Soft SRL. 18.5 (U33-DEC-01, Q05, D1-D4, D-1, D-2): sign-in and account security.

- Sign-in: password + one second factor. The factor is the investor's authenticator app when one is
  active, otherwise an SMS code to the verified phone; a recovery code (10 per account, single
  use) replaces either. A trusted browser skips the factor for 30 days (the password is still
  asked). An account without a factor yet (registration not finished) signs in with the password
  only and must set up a factor before anything else (financial access needs a factor).
- Security changes while signed in (password, factor, recovery codes) need a fresh confirmation:
  the password and the current factor.
- Recovery: forgotten password = single-use email link + second factor; forgotten PIN = password +
  SMS code (app users have no PIN); a lost factor without codes = assisted recovery (support case,
  identity check, approval by another person, 24 h notice with "This was not me", single-use link,
  new password and new factor; then 72 h without new bank accounts or a new default return account).
- Every reset is notified; a password or factor reset ends the other sessions.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from backend.apps.accounts_auth import factor_sms, rate_limits, totp
from backend.apps.accounts_auth import services as accounts_services
from backend.apps.accounts_auth.crypto import (
    decrypt_delivery_secret,
    digest_secret,
    encrypt_delivery_secret,
)
from backend.apps.accounts_auth.factors import (
    FACTOR_APP,
    FACTOR_SMS,
    active_authenticator,
    factor_kind,
)
from backend.apps.accounts_auth.models import (
    AccountType,
    AssistedRecoveryCase,
    AssistedRecoveryStatus,
    AuthenticatorApp,
    EmailLoginToken,
    LoginChallenge,
    PasswordResetToken,
    PhoneVerificationPurpose,
    RecoveryCode,
    SecurityRestriction,
    SensitiveAction,
    SensitiveActionCode,
    SessionEndReason,
    TrustedDevice,
    User,
    UserSession,
)
from backend.apps.accounts_auth.passwords import PasswordPolicyError, validate_new_password
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message
from backend.apps.platform_core.services.ip_privacy import keyed_ip_hash as ip_hash

CHALLENGE_TTL = timedelta(minutes=10)
SECURITY_CONFIRMATION_TTL = timedelta(minutes=10)
PASSWORD_RESET_TTL = timedelta(minutes=30)
RECOVERY_LINK_TTL = timedelta(hours=24)
ASSISTED_RECOVERY_WAIT = timedelta(hours=24)
ASSISTED_RECOVERY_LIMIT = 3
ASSISTED_RECOVERY_WINDOW = timedelta(days=7)
RESTRICTION_AFTER_RECOVERY = timedelta(hours=72)
RECOVERY_CODE_COUNT = 10
TRUSTED_COOKIE_NAME = "banxum_trusted"
INVESTOR_ACCOUNT_TYPES = frozenset(
    {AccountType.NATURAL_PERSON_LENDER, AccountType.LEGAL_ENTITY_LENDER_REPRESENTATIVE}
)
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def is_investor(user: Any) -> bool:
    return getattr(user, "account_type", None) in INVESTOR_ACCOUNT_TYPES


class TwoFactorError(ValueError):
    http_status = 400

    def __init__(
        self,
        message: str,
        *,
        code: str,
        http_status: int | None = None,
        extra: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.extra: dict[str, object] = dict(extra or {})
        if http_status is not None:
            self.http_status = http_status

    def payload(self) -> dict[str, object]:
        return {"detail": str(self), "code": self.code, **self.extra}


def _now() -> Any:
    return timezone.now()


def _issuer() -> str:
    return str(getattr(settings, "PLATFORM_BRAND_NAME", "") or "Banxum").title()


def _audit(user: User, action: str, metadata: dict[str, Any] | None = None) -> None:
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(user),
            action=action,
            target_type="User",
            target_id=str(user.pk),
            metadata=metadata or {},
        )
    )


def _security_notice(user: User, *, key: str, subject: str, headline: str, body: str) -> None:
    """A security email, always sent (independent of marketing consent)."""
    brand = str(getattr(settings, "PLATFORM_BRAND_NAME", "") or "BANXUM")
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"security:{key}",
            topic="email.security_change",
            payload={
                "user_id": str(user.pk),
                "email": str(user.email),
                "subject": subject.replace("{brand}", brand),
                "notice_label": "Security",
                "headline": headline,
                "status_label": "Security change",
                "status_tone": "warning",
                "body_text": body.replace("{brand}", brand)
                + "\n\nIf you did not do this, contact support at once.",
                "template_key": "security.change.v1",
                "metadata": {"navigation_target": "none"},
            },
        )
    )


# --- Factors -------------------------------------------------------------------------------


def phone_last_digits(user: User) -> str:
    digits = "".join(ch for ch in str(user.phone_number or "") if ch.isdigit())
    return digits[-2:] if user.phone_verified_at and digits else ""


def _app_max_attempts() -> int:
    return max(int(getattr(settings, "AUTH_PIN_MAX_ATTEMPTS", 5)), 1)


def _app_lock_duration() -> timedelta:
    return timedelta(seconds=max(int(getattr(settings, "AUTH_PIN_LOCK_SECONDS", 1800)), 1))


def _lock_time_label(value: Any) -> str:
    from backend.apps.platform_core.domain.time import to_business_time

    return f"{to_business_time(value).strftime('%H:%M')} (Zurich time)"


def check_app_code(user: User, code: str, *, context: str) -> None:
    """Check a code of the active authenticator app (sign-in, security step or operation).

    A code is accepted once (``last_used_step``). Wrong codes count toward the same lock as the
    PIN: after AUTH_PIN_MAX_ATTEMPTS the app is locked for AUTH_PIN_LOCK_SECONDS (recovery codes
    still work for sign-in). The count commits before the error is raised, so call this outside
    a rollbackable transaction.
    """
    failure: TwoFactorError | None
    with transaction.atomic():
        app = (
            AuthenticatorApp.objects.select_for_update()
            .filter(user=user, confirmed_at__isnull=False, disabled_at__isnull=True)
            .first()
        )
        now = _now()
        if app is None:
            failure = TwoFactorError(
                "This account has no authenticator app.", code="authenticator_missing"
            )
        elif app.locked_until is not None and app.locked_until > now:
            _audit(
                user, "auth.authenticator_check_failed", {"context": context, "reason": "locked"}
            )
            failure = TwoFactorError(
                "Too many wrong authenticator codes. Try again after "
                f"{_lock_time_label(app.locked_until)}.",
                code="authenticator_locked",
                http_status=423,
                extra={"locked_until": app.locked_until.isoformat()},
            )
        else:
            failure = _check_unlocked_app(app, user, code, context=context, now=now)
    if failure is not None:
        raise failure


def _check_unlocked_app(
    app: AuthenticatorApp, user: User, code: str, *, context: str, now: Any
) -> TwoFactorError | None:
    step = totp.verify(
        decrypt_delivery_secret(app.encrypted_secret), code, last_used_step=app.last_used_step
    )
    if step is not None:
        app.last_used_step = step
        app.failed_attempts = 0
        app.locked_until = None
        app.save(update_fields=["last_used_step", "failed_attempts", "locked_until", "updated_at"])
        return None
    app.failed_attempts = int(app.failed_attempts) + 1
    max_attempts = _app_max_attempts()
    if app.failed_attempts >= max_attempts:
        app.failed_attempts = 0
        app.locked_until = now + _app_lock_duration()
        failure = TwoFactorError(
            "Too many wrong authenticator codes. Try again after "
            f"{_lock_time_label(app.locked_until)}.",
            code="authenticator_locked",
            http_status=423,
            extra={"locked_until": app.locked_until.isoformat()},
        )
    else:
        attempts_left = max_attempts - app.failed_attempts
        failure = TwoFactorError(
            "Wrong authenticator code. Check the time on your phone. "
            + (
                "1 attempt left before the lock."
                if attempts_left == 1
                else f"{attempts_left} attempts left before the lock."
            ),
            code="authenticator_code_invalid",
            extra={"attempts_left": attempts_left},
        )
    app.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
    _audit(
        user,
        "auth.authenticator_check_failed",
        {"context": context, "reason": failure.code},
    )
    return failure


def start_authenticator_enrollment(user: User) -> dict[str, str]:
    """A new secret to scan; it becomes active only after a code is confirmed."""
    AuthenticatorApp.objects.filter(user=user, confirmed_at__isnull=True).delete()
    secret = totp.new_secret()
    app = AuthenticatorApp.objects.create(
        user=user, encrypted_secret=encrypt_delivery_secret(secret)
    )
    return {
        "enrollment_id": str(app.id),
        "secret": secret,
        "otpauth_uri": totp.provisioning_uri(
            secret=secret, account_name=str(user.email), issuer=_issuer()
        ),
    }


@transaction.atomic
def confirm_authenticator_enrollment(
    *,
    user: User,
    enrollment_id: str,
    code: str,
    security_confirmation_id: str = "",
    keep_session_id: str = "",
) -> AuthenticatorApp:
    """Activate the app. A user who already has a factor needs a fresh security confirmation.

    The app replaces an older app; for an SMS user it becomes the sign-in factor and replaces the
    PIN in operations (D-1). The verified phone stays as contact data.
    """
    had_factor = factor_kind(user)
    if had_factor:
        _consume_security_confirmation(user, security_confirmation_id)
    app = (
        AuthenticatorApp.objects.select_for_update()
        .filter(id=enrollment_id, user=user, confirmed_at__isnull=True)
        .first()
    )
    if app is None:
        raise TwoFactorError("Start the set-up again.", code="enrollment_not_found")
    step = totp.verify(decrypt_delivery_secret(app.encrypted_secret), code)
    if step is None:
        raise TwoFactorError(
            "The code is wrong. Check the time on your phone and try again.",
            code="authenticator_code_invalid",
        )
    now = _now()
    AuthenticatorApp.objects.filter(
        user=user, confirmed_at__isnull=False, disabled_at__isnull=True
    ).update(disabled_at=now, disabled_reason="replaced")
    app.confirmed_at = now
    app.last_used_step = step
    app.save(update_fields=["confirmed_at", "last_used_step", "updated_at"])
    _audit(user, "auth.authenticator_enrolled", {"previous_factor": had_factor})
    if had_factor:
        # A changed second factor ends the other sessions and remembered browsers.
        end_sessions(user, keep_session_id=keep_session_id, reason="authenticator_changed")
        revoke_trusted_devices(user, reason="authenticator_changed")
        _security_notice(
            user,
            key=f"authenticator:{app.id}",
            subject="Authenticator app set up for your {brand} account",
            headline="Authenticator app set up",
            body=(
                "An authenticator app is now the second factor of your {brand} account. You type "
                "its code when you sign in and to confirm investments, withdrawals and bank "
                "account changes; the PIN is no longer asked."
            ),
        )
    return app


# --- Recovery codes --------------------------------------------------------------------------


def _new_recovery_code() -> str:
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def _normalized_recovery_code(code: str) -> str:
    cleaned = "".join(ch for ch in str(code).upper() if ch.isalnum())
    return f"{cleaned[:5]}-{cleaned[5:]}" if len(cleaned) == 10 else ""


def recovery_codes_remaining(user: User) -> int:
    return RecoveryCode.objects.filter(
        user=user, used_at__isnull=True, replaced_at__isnull=True
    ).count()


@transaction.atomic
def issue_recovery_codes(*, user: User, security_confirmation_id: str = "") -> list[str]:
    """10 new codes, shown once. The first set needs no confirmation; a new set does."""
    if RecoveryCode.objects.filter(user=user).exists():
        _consume_security_confirmation(user, security_confirmation_id)
    now = _now()
    RecoveryCode.objects.filter(user=user, replaced_at__isnull=True).update(replaced_at=now)
    batch = uuid.uuid4()
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    RecoveryCode.objects.bulk_create(
        [RecoveryCode(user=user, batch_id=batch, code_digest=digest_secret(code)) for code in codes]
    )
    _audit(user, "auth.recovery_codes_issued", {"count": len(codes)})
    return codes


def use_recovery_code(user: User, code: str) -> bool:
    normalized = _normalized_recovery_code(code)
    if not normalized:
        return False
    with transaction.atomic():
        record = (
            RecoveryCode.objects.select_for_update()
            .filter(
                user=user,
                code_digest=digest_secret(normalized),
                used_at__isnull=True,
                replaced_at__isnull=True,
            )
            .first()
        )
        if record is None:
            return False
        record.used_at = _now()
        record.save(update_fields=["used_at", "updated_at"])
    remaining = recovery_codes_remaining(user)
    _audit(user, "auth.recovery_code_used", {"remaining": remaining})
    _security_notice(
        user,
        key=f"recovery-code:{record.id}",
        subject="A recovery code of your {brand} account was used",
        headline="Recovery code used",
        body=(
            f"A recovery code was used for your {{brand}} account. {remaining} codes are left. "
            "You can create new codes in Profile & Settings, Security."
        ),
    )
    return True


# --- Challenges (second factor after the first step) ------------------------------------------


def _start_challenge(
    user: User,
    *,
    purpose: str,
    ip_address: str | None,
    user_agent: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[LoginChallenge, str]:
    """A pending second-factor check; an SMS user gets the code now. Returns (challenge, code
    for the mock SMS provider or '')."""
    kind = factor_kind(user)
    if not kind:
        raise TwoFactorError("This account has no second factor yet.", code="no_second_factor")
    LoginChallenge.objects.filter(
        user=user, purpose=purpose, completed_at__isnull=True, cancelled_at__isnull=True
    ).update(cancelled_at=_now())
    phone_challenge_id = None
    raw_code = ""
    if kind == FACTOR_SMS:
        try:
            phone_challenge, raw_code = factor_sms.send_code(
                user, purpose=_sms_purpose(purpose), ip_address=ip_address, user_agent=user_agent
            )
            phone_challenge_id = phone_challenge.id
        except accounts_services.PhoneVerificationThrottleError:
            # A code was sent moments ago and still works: the new step uses it.
            pending = factor_sms.latest_pending(user, purpose=_sms_purpose(purpose))
            if pending is None:
                raise
            phone_challenge_id = pending.id
    challenge = LoginChallenge.objects.create(
        user=user,
        purpose=purpose,
        method=kind,
        phone_challenge_id=phone_challenge_id,
        expires_at=_now() + CHALLENGE_TTL,
        requested_ip_hash=ip_hash(ip_address),
        requested_user_agent=user_agent,
        metadata=metadata or {},
    )
    return challenge, raw_code


def _locked_challenge(challenge_id: str, purpose: str, user: User | None) -> LoginChallenge:
    query = LoginChallenge.objects.select_for_update().filter(id=challenge_id, purpose=purpose)
    if user is not None:
        query = query.filter(user=user)
    challenge = query.select_related("user").first()
    if (
        challenge is None
        or challenge.completed_at is not None
        or challenge.cancelled_at is not None
        or challenge.expires_at <= _now()
    ):
        raise TwoFactorError("This step has expired. Start again.", code="challenge_expired")
    if challenge.attempts >= challenge.max_attempts:
        raise TwoFactorError(
            "Too many wrong codes. Start again.", code="challenge_attempts", http_status=429
        )
    return challenge


def _sms_purpose(purpose: str) -> str:
    return (
        PhoneVerificationPurpose.SIGN_IN
        if purpose == LoginChallenge.Purpose.SIGN_IN
        else PhoneVerificationPurpose.SECURITY
    )


def _check_challenge(
    *,
    challenge_id: str,
    purpose: str,
    code: str,
    recovery_code: str,
    user: User | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> tuple[LoginChallenge, str]:
    """Check the factor of a challenge. Returns (challenge, method used: app|sms|recovery_code).

    Three short transactions: read the challenge, check the factor (each factor commits its own
    counters), then complete the challenge or count the wrong attempt. A rollback of one step
    cannot erase the counts of another.
    """
    if not str(challenge_id or "").strip():
        raise TwoFactorError("This step has expired. Start again.", code="challenge_expired")
    with transaction.atomic():
        challenge = _locked_challenge(challenge_id, purpose, user)
    owner = challenge.user
    # Audit S4-2: wrong codes of one account are counted together (SMS, app and recovery codes,
    # every step and address), on top of the limits of each challenge and each factor.
    account_failures = rate_limits.factor_account_failures()
    wait = account_failures.retry_after(str(owner.pk))
    if wait is not None:
        raise TwoFactorError(
            "Too many wrong codes for this account. Try again later.",
            code="factor_attempts_account",
            http_status=429,
            extra={"retry_after_seconds": wait},
        )
    exhausted = False
    if recovery_code.strip():
        used = "recovery_code"
        ok = use_recovery_code(owner, recovery_code)
    elif challenge.method == FACTOR_APP:
        used = FACTOR_APP
        try:
            check_app_code(owner, code, context=str(purpose))
            ok = True
        except TwoFactorError as exc:
            if exc.code in {"authenticator_locked", "authenticator_missing"}:
                raise
            ok = False
    else:
        used = FACTOR_SMS
        try:
            factor_sms.check_code(
                owner,
                challenge_id=str(challenge.phone_challenge_id),
                raw_code=code,
                purpose=_sms_purpose(purpose),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            ok = True
        except factor_sms.FactorSmsError as exc:
            ok = False
            exhausted = exc.code == "sms_code_attempts"
    with transaction.atomic():
        challenge = _locked_challenge(challenge_id, purpose, user)
        if ok:
            challenge.completed_at = _now()
            challenge.save(update_fields=["completed_at", "updated_at"])
            return challenge, used
        challenge.attempts = (
            challenge.max_attempts
            if exhausted
            else min(challenge.attempts + 1, challenge.max_attempts)
        )
        challenge.save(update_fields=["attempts", "updated_at"])
        left = challenge.max_attempts - challenge.attempts
    account_failures.record_failure(str(owner.pk))
    if left > 0:
        raise TwoFactorError(
            "The code is wrong. Check it and try again.",
            code="factor_code_invalid",
            extra={"attempts_left": left},
        )
    raise TwoFactorError(
        "Too many wrong codes. Start again.", code="factor_code_invalid", http_status=429
    )


def resend_sms(
    *,
    challenge_id: str,
    user: User | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> None:
    query = LoginChallenge.objects.select_related("user").filter(
        id=challenge_id, completed_at__isnull=True, cancelled_at__isnull=True
    )
    if user is not None:
        query = query.filter(user=user)
    else:
        # Without a session only the sign-in and password-reset steps can resend.
        query = query.filter(
            purpose__in=[LoginChallenge.Purpose.SIGN_IN, LoginChallenge.Purpose.PASSWORD_RESET]
        )
    challenge = query.first()
    if challenge is None or challenge.expires_at <= _now() or challenge.method != FACTOR_SMS:
        raise TwoFactorError("This step has expired. Start again.", code="challenge_expired")
    phone_challenge, _code = factor_sms.send_code(
        challenge.user,
        purpose=_sms_purpose(challenge.purpose),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    challenge.phone_challenge_id = phone_challenge.id
    challenge.save(update_fields=["phone_challenge_id", "updated_at"])


# --- Trusted devices -------------------------------------------------------------------------


def _trusted_device_for_token(user: User, token: str) -> TrustedDevice | None:
    if not token:
        return None
    return TrustedDevice.objects.filter(
        user=user,
        token_digest=digest_secret(token),
        revoked_at__isnull=True,
        expires_at__gt=_now(),
    ).first()


def trust_device(user: User, *, device_label: str) -> str:
    """A new trusted browser for the configured days; returns the cookie value."""
    token = secrets.token_urlsafe(32)
    TrustedDevice.objects.create(
        user=user,
        token_digest=digest_secret(token),
        device_label=device_label[:120],
        expires_at=_now() + timedelta(days=int(getattr(settings, "AUTH_TRUSTED_DEVICE_DAYS", 30))),
    )
    _audit(user, "auth.device_trusted", {"device_label": device_label[:120]})
    return token


def list_trusted_devices(user: User) -> list[dict[str, Any]]:
    return [
        {
            "id": str(device.id),
            "device_label": device.device_label or "Unknown device",
            "created_at": device.created_at,
            "expires_at": device.expires_at,
            "last_used_at": device.last_used_at,
        }
        for device in TrustedDevice.objects.filter(
            user=user, revoked_at__isnull=True, expires_at__gt=_now()
        ).order_by("-created_at")
    ]


def revoke_trusted_devices(user: User, *, device_id: str | None = None, reason: str) -> int:
    query = TrustedDevice.objects.filter(user=user, revoked_at__isnull=True)
    if device_id is not None:
        query = query.filter(id=device_id)
    count = query.update(revoked_at=_now(), revoked_reason=reason[:64])
    if count:
        _audit(user, "auth.trusted_devices_revoked", {"count": count, "reason": reason})
    return count


# --- Sign-in -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SignInStep:
    user: User
    # signed_in | factor_required | enrollment_required
    status: str
    method: str = ""
    challenge_id: str = ""
    phone_last_digits: str = ""
    sign_in_method: str = ""
    sms_code_for_tests: str = ""


def _spend_password_time(password: str) -> None:
    make_password(password)


def start_sign_in(
    *,
    email: str,
    password: str,
    trusted_token: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> SignInStep:
    """First step: the password. Wrong data gets one generic error (no account enumeration)."""
    normalized = str(email or "").strip().lower()
    user = User.objects.filter(email=normalized).first()
    generic = TwoFactorError(
        "The email address or the password is wrong.", code="invalid_credentials", http_status=400
    )
    if user is None or user.account_type not in INVESTOR_ACCOUNT_TYPES:
        _spend_password_time(password)
        raise generic
    if not user.has_usable_password() or not user.check_password(password):
        security_sessions = _security_sessions()
        security_sessions.record_sign_in(
            user=user,
            method="password_only",
            result="failed",
            user_agent=user_agent,
            ip_address=ip_address or "",
        )
        raise generic
    if not user.can_login:
        # The right password proves ownership, so the reason can be shown (U33-DEC-25: the
        # refused sign-in is in the account history).
        _security_sessions().record_sign_in(
            user=user,
            method="password_only",
            result="blocked",
            user_agent=user_agent,
            ip_address=ip_address or "",
        )
        status_text = str(user.status)
        if user.is_active and status_text in {"restricted", "locked"}:
            word = "locked" if status_text == "locked" else "restricted"
            raise TwoFactorError(
                f"Your account is {word}. Please contact support at "
                f"{accounts_services._support_email()} for further details.",  # noqa: SLF001
                code=f"account_{status_text}",
                http_status=403,
            )
        raise TwoFactorError(
            "The email address or the password is wrong.",
            code="invalid_credentials",
            http_status=400,
        )
    kind = factor_kind(user)
    if not kind:
        if not EmailLoginToken.objects.filter(user=user, used_at__isnull=False).exists():
            # The email address is not confirmed yet: send the registration link again.
            try:
                accounts_services.issue_magic_link(
                    accounts_services.MagicLinkRequestCommand(
                        email=str(user.email), ip_address=ip_address, user_agent=user_agent
                    )
                )
            except accounts_services.AccountsAuthError:
                pass
            raise TwoFactorError(
                "Confirm your email address first: open the link we sent you. "
                "We sent the link again.",
                code="email_not_confirmed",
                http_status=403,
            )
        return SignInStep(user=user, status="enrollment_required", sign_in_method="password_only")
    device = _trusted_device_for_token(user, trusted_token)
    if device is not None:
        device.last_used_at = _now()
        device.save(update_fields=["last_used_at", "updated_at"])
        return SignInStep(
            user=user, status="signed_in", sign_in_method="password_trusted_device", method=kind
        )
    challenge, raw_code = _start_challenge(
        user,
        purpose=LoginChallenge.Purpose.SIGN_IN,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return SignInStep(
        user=user,
        status="factor_required",
        method=kind,
        challenge_id=str(challenge.id),
        phone_last_digits=phone_last_digits(user),
        sms_code_for_tests=raw_code,
    )


def complete_sign_in(
    *,
    challenge_id: str,
    code: str = "",
    recovery_code: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> tuple[User, str]:
    """Second step: the factor (or a recovery code). Returns (user, sign-in method)."""
    try:
        challenge, used = _check_challenge(
            challenge_id=challenge_id,
            purpose=LoginChallenge.Purpose.SIGN_IN,
            code=code,
            recovery_code=recovery_code,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except TwoFactorError as exc:
        owner = LoginChallenge.objects.filter(id=challenge_id).select_related("user").first()
        if owner is not None and exc.code == "factor_code_invalid":
            _security_sessions().record_sign_in(
                user=owner.user,
                method="password_app" if owner.method == FACTOR_APP else "password_sms",
                result="failed_factor",
                user_agent=user_agent,
                ip_address=ip_address or "",
            )
        raise
    method = {
        FACTOR_APP: "password_app",
        FACTOR_SMS: "password_sms",
        "recovery_code": "password_recovery_code",
    }[used]
    return challenge.user, method


# --- Admin sign-in: password + authenticator app ---------------------------------------------


@dataclass(frozen=True, slots=True)
class AdminSignInStep:
    user: User
    # factor_required | enrollment_required
    status: str
    challenge_id: str = ""
    code_id: str = ""
    code_expires_at: Any = None
    enrollment: dict[str, str] | None = None


def start_admin_sign_in(
    *, email: str, password: str, ip_address: str | None = None, user_agent: str = ""
) -> AdminSignInStep:
    """An admin with an app types its code next. An admin without one (first sign-in, or the
    app was reset by a super admin) gets an email code and a new app to set up; both are
    needed to finish (the email code proves the mailbox, the app code the new app)."""
    user = accounts_services.check_admin_credentials(
        accounts_services.AdminLoginStartCommand(
            email=email, password=password, ip_address=ip_address, user_agent=user_agent
        )
    )
    if active_authenticator(user) is not None:
        LoginChallenge.objects.filter(
            user=user,
            purpose=LoginChallenge.Purpose.ADMIN_SIGN_IN,
            completed_at__isnull=True,
            cancelled_at__isnull=True,
        ).update(cancelled_at=_now())
        challenge = LoginChallenge.objects.create(
            user=user,
            purpose=LoginChallenge.Purpose.ADMIN_SIGN_IN,
            method=FACTOR_APP,
            expires_at=_now() + CHALLENGE_TTL,
            requested_ip_hash=ip_hash(ip_address),
            requested_user_agent=user_agent,
        )
        return AdminSignInStep(user=user, status="factor_required", challenge_id=str(challenge.id))
    with transaction.atomic():
        code_record = accounts_services.issue_admin_enrollment_code(
            user, ip_address=ip_address, user_agent=user_agent
        )
        enrollment = start_authenticator_enrollment(user)
    return AdminSignInStep(
        user=user,
        status="enrollment_required",
        code_id=str(code_record.id),
        code_expires_at=code_record.expires_at,
        enrollment=enrollment,
    )


def complete_admin_sign_in(
    *, challenge_id: str, code: str, ip_address: str | None = None, user_agent: str = ""
) -> User:
    challenge, _used = _check_challenge(
        challenge_id=challenge_id,
        purpose=LoginChallenge.Purpose.ADMIN_SIGN_IN,
        code=code,
        recovery_code="",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    user = challenge.user
    if not is_admin_actor(user) or not user.can_login:
        raise TwoFactorError("Admin credentials are invalid.", code="invalid_credentials")
    _audit(user, "auth.admin_login_completed", {"method": "password_app"})
    return user


def complete_admin_enrollment(
    *,
    code_id: str,
    email_code: str,
    enrollment_id: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str = "",
) -> User:
    """Check the email code (not yet used up), then the new app code; then use the email code
    and activate the app. A wrong app code leaves the email code usable."""
    try:
        code_record = accounts_services.consume_sensitive_action_code(
            accounts_services.SensitiveActionCodeConsumeCommand(
                code_id=code_id,
                raw_code=email_code,
                expected_action=SensitiveAction.ADMIN_LOGIN,
                ip_address=ip_address,
                user_agent=user_agent,
                consume=False,
            )
        )
    except accounts_services.AccountsAuthError as exc:
        raise TwoFactorError(str(exc), code="email_code_invalid") from exc
    user = code_record.user
    if not is_admin_actor(user) or not user.can_login:
        raise TwoFactorError("Admin credentials are invalid.", code="invalid_credentials")
    with transaction.atomic():
        confirm_authenticator_enrollment(user=user, enrollment_id=enrollment_id, code=code)
        try:
            accounts_services.consume_sensitive_action_code(
                accounts_services.SensitiveActionCodeConsumeCommand(
                    code_id=code_id,
                    raw_code=email_code,
                    expected_action=SensitiveAction.ADMIN_LOGIN,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            )
        except accounts_services.AccountsAuthError as exc:
            raise TwoFactorError(str(exc), code="email_code_invalid") from exc
    _audit(user, "auth.admin_login_completed", {"method": "password_app", "enrolled": True})
    return user


@transaction.atomic
def reset_admin_authenticator(*, actor: Any, admin_user_id: str) -> None:
    """A super admin resets the app of another admin (lost phone): the next sign-in sets up a
    new app with an email code. The admin's sessions end."""
    if not getattr(actor, "is_superuser", False):
        raise TwoFactorError(
            "Only a super admin can reset an authenticator app.", code="forbidden", http_status=403
        )
    target = User.objects.filter(id=admin_user_id).first()
    if target is None or not is_admin_actor(target):
        raise TwoFactorError("Choose an admin account.", code="not_found", http_status=404)
    if str(target.pk) == str(actor.pk):
        raise TwoFactorError(
            "Another super admin must reset your own app.",
            code="second_person_required",
            http_status=403,
        )
    now = _now()
    AuthenticatorApp.objects.filter(user=target, disabled_at__isnull=True).update(
        disabled_at=now, disabled_reason="reset_by_super_admin"
    )
    end_sessions(target, reason="authenticator_reset")
    event = record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="auth.admin_authenticator_reset",
            target_type="User",
            target_id=str(target.pk),
        )
    )
    _notify_admin_authenticator_reset(actor=actor, target=target, at=now, event_id=str(event.pk))


def _notify_admin_authenticator_reset(*, actor: Any, target: User, at: Any, event_id: str) -> None:
    """Audit S4-6 (D3: every reset is notified): the admin whose app was reset gets an email at
    once and a task in the admin console. One notice per reset; no code or link in it."""
    from backend.apps.platform_core.domain.time import to_business_time

    when = to_business_time(at).strftime("%d %b %Y, %H:%M")
    who = str(getattr(actor, "full_name", "") or "").strip() or "A super admin"
    who_email = str(getattr(actor, "email", "") or "")
    support = str(getattr(settings, "OPERATIONS_ALERT_EMAIL", "") or "hq@banxum.com")
    brand = str(getattr(settings, "PLATFORM_BRAND_NAME", "") or "BANXUM")
    what = (
        f"{who} ({who_email}) reset the authenticator app of your {brand} admin account on "
        f"{when} (Europe/Zurich). You are signed out on all devices. At your next sign-in you "
        "set up a new authenticator app with a code that we send to this email address."
    )
    not_me = (
        "This was not me: if you did not ask for this reset, do not set up a new app. Tell "
        f"another super admin at once and write to {support}."
    )
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"security:admin-authenticator-reset:{event_id}",
            topic="email.security_change",
            payload={
                "user_id": str(target.pk),
                "email": str(target.email),
                "subject": f"The authenticator app of your {brand} admin account was reset",
                "notice_label": "Security",
                "headline": "Authenticator app reset",
                "status_label": "Security change",
                "status_tone": "warning",
                "body_text": f"{what}\n\n{not_me}",
                "data_rows": [
                    ["Reset by", f"{who} ({who_email})"],
                    ["Time", f"{when} (Europe/Zurich)"],
                    ["Contact", support],
                ],
                "template_key": "security.admin_authenticator_reset.v1",
                "metadata": {
                    "navigation_target": "none",
                    "audit_event_id": event_id,
                    "reset_by_admin_id": str(actor.pk),
                },
            },
        )
    )
    # The notice inside the admin console: a task for the admin, seen after the next sign-in.
    admin_ops: Any = import_module("backend.apps.admin_ops.services")
    admin_ops.ensure_related_admin_task(
        actor=actor,
        task_type="account_access_review",
        related_object_type="AdminAuthenticatorReset",
        related_object_id=event_id,
        title="Your authenticator app was reset",
        priority="high",
        notes=f"{what}\n\n{not_me}\n\nClose this task when you have read it.",
        assigned_admin_id=str(target.pk),
    )


def _security_sessions() -> Any:
    from backend.apps.accounts_auth import security_sessions

    return security_sessions


# --- Security confirmation (password + factor) ----------------------------------------------


def start_security_confirmation(
    *, user: User, password: str, ip_address: str | None = None, user_agent: str = ""
) -> SignInStep:
    if not user.has_usable_password() or not user.check_password(password):
        _audit(user, "auth.security_confirmation_failed", {"reason": "password"})
        raise TwoFactorError("The password is wrong.", code="invalid_password")
    challenge, raw_code = _start_challenge(
        user,
        purpose=LoginChallenge.Purpose.SECURITY_CHANGE,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return SignInStep(
        user=user,
        status="factor_required",
        method=challenge.method,
        challenge_id=str(challenge.id),
        phone_last_digits=phone_last_digits(user),
        sms_code_for_tests=raw_code,
    )


def complete_security_confirmation(
    *,
    user: User,
    challenge_id: str,
    code: str = "",
    recovery_code: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> str:
    """Returns the confirmation id to pass to the change (valid 10 minutes, once)."""
    challenge, _used = _check_challenge(
        challenge_id=challenge_id,
        purpose=LoginChallenge.Purpose.SECURITY_CHANGE,
        code=code,
        recovery_code=recovery_code,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return str(challenge.id)


def _consume_security_confirmation(user: User, confirmation_id: str) -> None:
    challenge = (
        LoginChallenge.objects.select_for_update()
        .filter(
            id=confirmation_id,
            user=user,
            purpose=LoginChallenge.Purpose.SECURITY_CHANGE,
            completed_at__isnull=False,
        )
        .first()
        if confirmation_id
        else None
    )
    if (
        challenge is None
        or challenge.completed_at is None
        or challenge.completed_at + SECURITY_CONFIRMATION_TTL <= _now()
        or challenge.metadata.get("used")
    ):
        raise TwoFactorError(
            "Confirm with your password and your second factor first.",
            code="security_confirmation_required",
            http_status=403,
        )
    challenge.metadata = {**challenge.metadata, "used": True}
    challenge.save(update_fields=["metadata", "updated_at"])


# --- Sessions and authorizations -----------------------------------------------------------


def end_sessions(user: User, *, keep_session_id: str = "", reason: str) -> int:
    """End the signed-in sessions of the account (all, or all but the current one)."""
    query = UserSession.objects.filter(user=user, ended_at__isnull=True)
    if keep_session_id:
        query = query.exclude(id=keep_session_id)
    count = int(
        query.update(
            ended_at=_security_sessions().wall_clock(), end_reason=SessionEndReason.SECURITY_RESET
        )
    )
    if count:
        _audit(user, "auth.sessions_ended", {"sessions_ended": count, "reason": reason})
    return count


def invalidate_unfinished_authorizations(user: User) -> None:
    """Pending email codes and second-factor steps stop working (valid investments stay)."""
    now = _now()
    SensitiveActionCode.objects.filter(
        user=user, consumed_at__isnull=True, superseded_at__isnull=True
    ).update(superseded_at=now)
    LoginChallenge.objects.filter(
        user=user, completed_at__isnull=True, cancelled_at__isnull=True
    ).update(cancelled_at=now)


# --- Password -------------------------------------------------------------------------------


def set_password(user: User, password: str) -> None:
    try:
        validate_new_password(password, email=str(user.email))
    except PasswordPolicyError as exc:
        raise TwoFactorError(str(exc), code=exc.code) from exc
    user.set_password(password)
    user.password_changed_at = _now()
    user.save(update_fields=["password", "password_changed_at"])


@transaction.atomic
def change_password(
    *,
    user: User,
    new_password: str,
    security_confirmation_id: str,
    keep_session_id: str = "",
) -> None:
    _consume_security_confirmation(user, security_confirmation_id)
    if user.check_password(new_password):
        raise TwoFactorError(
            "Choose a password you have not used for this account.", code="password_unchanged"
        )
    set_password(user, new_password)
    ended = end_sessions(user, keep_session_id=keep_session_id, reason="password_changed")
    revoke_trusted_devices(user, reason="password_changed")
    _audit(user, "auth.password_changed", {"sessions_ended": ended})
    _security_notice(
        user,
        key=f"password-changed:{user.pk}:{_now().timestamp()}",
        subject="Your {brand} password was changed",
        headline="Password changed",
        body="The password of your {brand} account was changed. Other devices were signed out.",
    )


def request_password_reset(*, email: str, ip_address: str | None = None) -> str:
    """Send the reset link when the account exists and can sign in. Returns the raw token for
    tests (the API never returns it)."""
    user = User.objects.filter(email=str(email or "").strip().lower()).first()
    if user is None or not user.can_login or user.account_type not in INVESTOR_ACCOUNT_TYPES:
        return ""
    now = _now()
    PasswordResetToken.objects.filter(
        user=user, purpose="password_reset", used_at__isnull=True, superseded_at__isnull=True
    ).update(superseded_at=now)
    raw = secrets.token_urlsafe(32)
    token = PasswordResetToken.objects.create(
        user=user,
        token_digest=digest_secret(raw),
        encrypted_token=encrypt_delivery_secret(raw),
        expires_at=now + PASSWORD_RESET_TTL,
        requested_ip_hash=ip_hash(ip_address),
    )
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"password-reset:{token.id}",
            topic="email.password_reset",
            payload={
                "user_id": str(user.pk),
                "email": str(user.email),
                "subject": "Set a new password",
                "notice_label": "Security",
                "headline": "Set a new password",
                "status_label": "Action needed",
                "status_tone": "info",
                "body_text": (
                    "Use the link to set a new password. You also need your second factor "
                    "(authenticator app, SMS code or a recovery code). The link works once and "
                    "for 30 minutes. If you did not ask for it, you can ignore this email."
                ),
                **_secret_link("/reset-password", "password_reset_link", str(token.id)),
                "action_label": "Set a new password",
                "template_key": "security.password_reset.v1",
                "metadata": {"navigation_target": "none"},
            },
        )
    )
    _audit(user, "auth.password_reset_requested")
    return raw


def _reset_token(raw_token: str, *, purpose: str) -> PasswordResetToken:
    token = (
        PasswordResetToken.objects.select_for_update()
        .select_related("user")
        .filter(token_digest=digest_secret(raw_token or ""), purpose=purpose)
        .first()
    )
    if (
        token is None
        or token.used_at is not None
        or token.superseded_at is not None
        or token.expires_at <= _now()
    ):
        raise TwoFactorError("This link is invalid or expired.", code="reset_link_invalid")
    return token


@transaction.atomic
def start_password_reset(
    *, raw_token: str, ip_address: str | None = None, user_agent: str = ""
) -> SignInStep:
    token = _reset_token(raw_token, purpose="password_reset")
    user = token.user
    if not factor_kind(user):
        return SignInStep(user=user, status="enrollment_required")
    challenge, raw_code = _start_challenge(
        user,
        purpose=LoginChallenge.Purpose.PASSWORD_RESET,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"reset_token_id": str(token.id)},
    )
    return SignInStep(
        user=user,
        status="factor_required",
        method=challenge.method,
        challenge_id=str(challenge.id),
        phone_last_digits=phone_last_digits(user),
        sms_code_for_tests=raw_code,
    )


def complete_password_reset(
    *,
    raw_token: str,
    new_password: str,
    challenge_id: str = "",
    code: str = "",
    recovery_code: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> User:
    with transaction.atomic():
        token = _reset_token(raw_token, purpose="password_reset")
        user = token.user
    if factor_kind(user):
        challenge, _used = _check_challenge(
            challenge_id=challenge_id,
            purpose=LoginChallenge.Purpose.PASSWORD_RESET,
            code=code,
            recovery_code=recovery_code,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        if challenge.metadata.get("reset_token_id") != str(token.id):
            raise TwoFactorError("Start again from the link.", code="challenge_expired")
    with transaction.atomic():
        token = _reset_token(raw_token, purpose="password_reset")
        set_password(user, new_password)
        token.used_at = _now()
        token.save(update_fields=["used_at", "updated_at"])
        ended = end_sessions(user, reason="password_reset")
        revoke_trusted_devices(user, reason="password_reset")
        invalidate_unfinished_authorizations(user)
        _audit(user, "auth.password_reset_completed", {"sessions_ended": ended})
        _security_notice(
            user,
            key=f"password-reset:{token.id}",
            subject="Your {brand} password was reset",
            headline="Password reset",
            body="A new password was set for your {brand} account. All devices were signed out.",
        )
    return user


# --- Assisted recovery ---------------------------------------------------------------------


def _require_admin(actor: Any) -> None:
    if not is_admin_actor(actor):
        raise TwoFactorError(
            "Only an admin can manage account recovery.", code="forbidden", http_status=403
        )


def _case_audit(actor: Any, case: AssistedRecoveryCase, action: str, **metadata: Any) -> None:
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor) if actor is not None else ActorRef.system(),
            action=f"auth.assisted_recovery_{action}",
            target_type="AssistedRecoveryCase",
            target_id=str(case.id),
            metadata={"user_id": str(case.user_id), "status": case.status, **metadata},
        )
    )


@transaction.atomic
def open_assisted_recovery(*, actor: Any, user_id: str, note: str) -> AssistedRecoveryCase:
    _require_admin(actor)
    user = User.objects.select_for_update().filter(id=user_id).first()
    if user is None or user.account_type not in INVESTOR_ACCOUNT_TYPES:
        raise TwoFactorError("Choose an investor account.", code="not_found", http_status=404)
    recent = AssistedRecoveryCase.objects.filter(
        user=user, created_at__gte=_now() - ASSISTED_RECOVERY_WINDOW
    ).count()
    if recent >= ASSISTED_RECOVERY_LIMIT:
        raise TwoFactorError(
            "This account already had 3 recovery requests in the last 7 days.",
            code="assisted_recovery_limit",
            http_status=429,
        )
    if AssistedRecoveryCase.objects.filter(
        user=user,
        status__in=[
            AssistedRecoveryStatus.REQUESTED,
            AssistedRecoveryStatus.IDENTITY_CONFIRMED,
            AssistedRecoveryStatus.APPROVED,
            AssistedRecoveryStatus.LINK_SENT,
        ],
    ).exists():
        raise TwoFactorError(
            "A recovery of this account is already open.", code="assisted_recovery_open"
        )
    case = AssistedRecoveryCase.objects.create(
        user=user, requested_by_admin_id=actor.pk, request_note=note.strip()
    )
    _case_audit(actor, case, "opened", note=note.strip())
    return case


@transaction.atomic
def confirm_assisted_identity(*, actor: Any, case_id: str, evidence: str) -> AssistedRecoveryCase:
    """The new Didit check matches the stored identity (evidence: the Didit session and result)."""
    _require_admin(actor)
    case = AssistedRecoveryCase.objects.select_for_update().filter(id=case_id).first()
    if case is None or case.status != AssistedRecoveryStatus.REQUESTED:
        raise TwoFactorError(
            "This recovery is not waiting for the identity check.", code="bad_state"
        )
    if not evidence.strip():
        raise TwoFactorError(
            "Record the identity check (Didit session and result).", code="evidence_required"
        )
    case.status = AssistedRecoveryStatus.IDENTITY_CONFIRMED
    case.identity_confirmed_by_admin_id = actor.pk
    case.identity_confirmed_at = _now()
    case.identity_evidence = evidence.strip()
    case.save()
    _case_audit(actor, case, "identity_confirmed", evidence=evidence.strip())
    return case


def _secret_link(path: str, secret_type: str, ref: str) -> dict[str, object]:
    """The email payload of a single-use link: the token itself is never in the payload. The
    email service reads it encrypted from the record at send time; stored copies show
    "[redacted]" (audit A-49). The token is in the fragment, so it reaches no server log."""
    base = str(getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").rstrip("/")
    return {
        "action_url_template": f"{base}{path}#token={{secret}}",
        "delivery_secret_type": secret_type,
        "delivery_secret_ref": ref,
        "secret_redacted": True,
    }


@transaction.atomic
def approve_assisted_recovery(*, actor: Any, case_id: str) -> AssistedRecoveryCase:
    """A second person approves; old access ends at once; the 24-hour notice starts."""
    _require_admin(actor)
    case = (
        AssistedRecoveryCase.objects.select_for_update()
        .select_related("user")
        .filter(id=case_id)
        .first()
    )
    if case is None or case.status != AssistedRecoveryStatus.IDENTITY_CONFIRMED:
        raise TwoFactorError("Confirm the identity first.", code="bad_state")
    if str(actor.pk) in {str(case.requested_by_admin_id), str(case.identity_confirmed_by_admin_id)}:
        raise TwoFactorError(
            "Another authorized person must approve this recovery.",
            code="second_person_required",
            http_status=403,
        )
    user = case.user
    now = _now()
    invalidate_unfinished_authorizations(user)
    end_sessions(user, reason="assisted_recovery")
    revoke_trusted_devices(user, reason="assisted_recovery")
    AuthenticatorApp.objects.filter(user=user, disabled_at__isnull=True).update(
        disabled_at=now, disabled_reason="assisted_recovery"
    )
    RecoveryCode.objects.filter(user=user, replaced_at__isnull=True).update(replaced_at=now)
    if user.phone_verified_at is not None:
        user.phone_verified_at = None
        user.save(update_fields=["phone_verified_at"])
    dispute = secrets.token_urlsafe(32)
    case.status = AssistedRecoveryStatus.APPROVED
    case.approved_by_admin_id = actor.pk
    case.approved_at = now
    case.wait_until = now + ASSISTED_RECOVERY_WAIT
    case.dispute_token_digest = digest_secret(dispute)
    case.encrypted_dispute_token = encrypt_delivery_secret(dispute)
    case.save()
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"assisted-recovery:{case.id}:notice",
            topic="email.security_change",
            payload={
                "user_id": str(user.pk),
                "email": str(user.email),
                "subject": "Account recovery started",
                "notice_label": "Security",
                "headline": "Account recovery started",
                "status_label": "Security change",
                "status_tone": "warning",
                "body_text": (
                    "We started the recovery of your account after a request to our support. "
                    "Your old second factor and all sessions were stopped. In 24 hours we send "
                    "you a link to set a new password and a new second factor.\n\nIf you did not "
                    'ask for this, use the link "This was not me" at once: the recovery stops.'
                ),
                **_secret_link(
                    "/account-recovery/not-me", "assisted_recovery_dispute_link", str(case.id)
                ),
                "action_label": "This was not me",
                "template_key": "security.assisted_recovery_notice.v1",
                "metadata": {"navigation_target": "none"},
            },
        )
    )
    _case_audit(actor, case, "approved")
    return case


@transaction.atomic
def dispute_assisted_recovery(*, raw_token: str) -> AssistedRecoveryCase:
    case = (
        AssistedRecoveryCase.objects.select_for_update()
        .filter(
            dispute_token_digest=digest_secret(raw_token or ""),
            status__in=[AssistedRecoveryStatus.APPROVED, AssistedRecoveryStatus.LINK_SENT],
        )
        .first()
    )
    if case is None:
        raise TwoFactorError("This link is invalid or no longer needed.", code="reset_link_invalid")
    case.status = AssistedRecoveryStatus.DISPUTED
    case.cancelled_at = _now()
    case.cancelled_reason = "The investor said the request was not theirs."
    case.save()
    PasswordResetToken.objects.filter(
        user_id=case.user_id, purpose="assisted_recovery", used_at__isnull=True
    ).update(superseded_at=_now())
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"assisted-recovery:{case.id}:disputed",
            topic="email.operations_alert",
            payload={
                "email": str(getattr(settings, "OPERATIONS_ALERT_EMAIL", "") or "hq@banxum.com"),
                "subject": "Account recovery stopped by the investor",
                "notice_label": "Security alert",
                "headline": "An investor stopped an account recovery",
                "status_label": "Review needed",
                "status_tone": "danger",
                "body_text": (
                    f'The investor of account {case.user_id} used "This was not me" on an '
                    "account recovery. Review the case and contact the investor."
                ),
                "template_key": "ops.assisted_recovery_disputed.v1",
                "metadata": {"case_id": str(case.id)},
            },
        )
    )
    _case_audit(None, case, "disputed")
    return case


def send_due_recovery_links(*, as_of: Any | None = None) -> list[str]:
    """After the 24-hour wait: a single-use link to set a password and a new factor."""
    now = as_of or _now()
    sent: list[str] = []
    for case in AssistedRecoveryCase.objects.select_related("user").filter(
        status=AssistedRecoveryStatus.APPROVED, wait_until__lte=now
    ):
        raw = secrets.token_urlsafe(32)
        with transaction.atomic():
            token = PasswordResetToken.objects.create(
                user=case.user,
                token_digest=digest_secret(raw),
                encrypted_token=encrypt_delivery_secret(raw),
                purpose="assisted_recovery",
                expires_at=now + RECOVERY_LINK_TTL,
            )
            case.status = AssistedRecoveryStatus.LINK_SENT
            case.link_sent_at = now
            case.save()
            enqueue_outbox_message(
                OutboxCommand(
                    idempotency_key=f"assisted-recovery:{case.id}:link",
                    topic="email.password_reset",
                    payload={
                        "user_id": str(case.user_id),
                        "email": str(case.user.email),
                        "subject": "Finish the recovery of your account",
                        "notice_label": "Security",
                        "headline": "Finish the recovery of your account",
                        "status_label": "Action needed",
                        "status_tone": "info",
                        "body_text": (
                            "Use the link to set a new password and a new second factor. The "
                            "link works once and for 24 hours."
                        ),
                        **_secret_link(
                            "/account-recovery", "assisted_recovery_link", str(token.id)
                        ),
                        "action_label": "Finish recovery",
                        "template_key": "security.assisted_recovery_link.v1",
                        "metadata": {"navigation_target": "none"},
                    },
                )
            )
            _case_audit(None, case, "link_sent")
        sent.append(str(case.id))
    return sent


@transaction.atomic
def complete_assisted_recovery(*, raw_token: str, new_password: str) -> User:
    """The investor sets a new password; a new factor is set up right after (signed in)."""
    token = _reset_token(raw_token, purpose="assisted_recovery")
    user = token.user
    case = (
        AssistedRecoveryCase.objects.select_for_update()
        .filter(user=user, status=AssistedRecoveryStatus.LINK_SENT)
        .first()
    )
    if case is None:
        raise TwoFactorError("This recovery is not open any more.", code="reset_link_invalid")
    set_password(user, new_password)
    now = _now()
    token.used_at = now
    token.save(update_fields=["used_at", "updated_at"])
    case.status = AssistedRecoveryStatus.COMPLETED
    case.completed_at = now
    case.save()
    SecurityRestriction.objects.create(
        user=user,
        reason="assisted_recovery",
        starts_at=now,
        ends_at=now + RESTRICTION_AFTER_RECOVERY,
    )
    _case_audit(None, case, "completed")
    _security_notice(
        user,
        key=f"assisted-recovery:{case.id}:completed",
        subject="Your {brand} account was recovered",
        headline="Account recovered",
        body=(
            "A new password was set for your {brand} account. Set up your new second factor now. "
            "For 72 hours you cannot add a bank account or change your default return account; "
            "withdrawals to your verified accounts stay possible."
        ),
    )
    return user


def list_assisted_recoveries(*, status: str = "") -> list[AssistedRecoveryCase]:
    query = AssistedRecoveryCase.objects.select_related("user")
    if status:
        query = query.filter(status=status)
    return list(query.order_by("-created_at")[:200])


# --- Restrictions ---------------------------------------------------------------------------


def active_restriction(user_id: Any) -> SecurityRestriction | None:
    return (
        SecurityRestriction.objects.filter(user_id=user_id, ends_at__gt=_now())
        .order_by("-ends_at")
        .first()
    )


# --- Registration email link -----------------------------------------------------------------


def registration_link_may_sign_in(token: EmailLoginToken) -> bool:
    """A registration link continues the registration only while the account has no factor."""
    return token.purpose == "registration" and not factor_kind(token.user)
