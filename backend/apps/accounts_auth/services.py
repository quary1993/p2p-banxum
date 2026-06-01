from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from backend.apps.accounts_auth.crypto import (
    decrypt_delivery_secret,
    digest_secret,
    encrypt_delivery_secret,
)
from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    EmailLoginToken,
    PhoneVerificationChallenge,
    PhoneVerificationStatus,
    RegistrationTermsAcceptance,
    SensitiveAction,
    SensitiveActionCode,
    User,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    record_domain_event,
)


class AccountsAuthError(ValueError):
    pass


class DuplicateEmailError(AccountsAuthError):
    pass


class InvalidOrExpiredTokenError(AccountsAuthError):
    pass


class InvalidOrExpiredCodeError(AccountsAuthError):
    pass


class TooManyCodeAttemptsError(AccountsAuthError):
    pass


class InvalidTermsAcceptanceError(AccountsAuthError):
    pass


class SensitiveActionCodeThrottleError(AccountsAuthError):
    pass


class PhoneVerificationThrottleError(AccountsAuthError):
    pass


class PhoneAlreadyVerifiedError(AccountsAuthError):
    pass


def normalize_email(email: str) -> str:
    normalized = User.objects.normalize_email(email).strip().lower()
    if not normalized:
        raise AccountsAuthError("Email is required.")
    return normalized


def _audit_auth_failure(
    *,
    action: str,
    user_id: str = "",
    metadata: dict[str, object] | None = None,
) -> None:
    record_audit_event(
        AuditCommand(
            actor=ActorRef("investor", user_id) if user_id else ActorRef.system(),
            action=action,
            target_type="User" if user_id else "",
            target_id=user_id,
            metadata=metadata or {},
        )
    )


def _validate_registration_terms(version: str, terms_hash: str) -> None:
    if (
        version != settings.REGISTRATION_TERMS_VERSION
        or terms_hash != settings.REGISTRATION_TERMS_HASH
    ):
        raise InvalidTermsAcceptanceError("Registration terms are not current.")


@dataclass(frozen=True, slots=True)
class RegisterNaturalPersonCommand:
    email: str
    full_name: str
    phone_number: str
    terms_version: str
    terms_hash: str
    ip_address: str | None = None
    user_agent: str = ""
    marketing_consent: bool = False


@dataclass(frozen=True, slots=True)
class MagicLinkRequestCommand:
    email: str
    ip_address: str | None = None
    user_agent: str = ""
    ttl: timedelta = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class MagicLinkIssueResult:
    login_token: EmailLoginToken
    raw_token: str


@dataclass(frozen=True, slots=True)
class MagicLinkConsumeCommand:
    raw_token: str
    ip_address: str | None = None
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class SensitiveActionCodeCommand:
    user: User
    action: SensitiveAction
    ip_address: str | None = None
    user_agent: str = ""
    ttl: timedelta = timedelta(minutes=10)
    max_attempts: int = 3


@dataclass(frozen=True, slots=True)
class SensitiveActionCodeIssueResult:
    code_record: SensitiveActionCode
    raw_code: str


@dataclass(frozen=True, slots=True)
class SensitiveActionCodeConsumeCommand:
    code_id: str
    raw_code: str
    ip_address: str | None = None
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class PhoneVerificationRequestCommand:
    user: User
    ip_address: str | None = None
    user_agent: str = ""
    ttl: timedelta | None = None
    max_attempts: int | None = None


@dataclass(frozen=True, slots=True)
class PhoneVerificationRequestResult:
    challenge: PhoneVerificationChallenge
    raw_code: str


@dataclass(frozen=True, slots=True)
class PhoneVerificationConfirmCommand:
    user: User
    challenge_id: str
    raw_code: str
    ip_address: str | None = None
    user_agent: str = ""


@transaction.atomic
def register_natural_person_lender(command: RegisterNaturalPersonCommand) -> User:
    email = normalize_email(command.email)
    _validate_registration_terms(command.terms_version, command.terms_hash)
    if User.objects.filter(email=email).exists():
        raise DuplicateEmailError("An account already exists for this email.")

    try:
        user = User.objects.create_user(
            email=email,
            full_name=command.full_name.strip(),
            account_type=AccountType.NATURAL_PERSON_LENDER,
            status=AccountStatus.PENDING_KYC,
            phone_number=command.phone_number.strip(),
            marketing_consent=command.marketing_consent,
        )
    except IntegrityError as exc:
        raise DuplicateEmailError("An account already exists for this email.") from exc

    RegistrationTermsAcceptance.objects.create(
        user=user,
        terms_version=command.terms_version,
        terms_hash=command.terms_hash,
        ip_address=command.ip_address,
        user_agent=command.user_agent,
    )
    actor = ActorRef("investor", str(user.id))
    record_audit_event(
        AuditCommand(
            actor=actor,
            action="account.registered",
            target_type="User",
            target_id=str(user.id),
            metadata={
                "account_type": user.account_type,
                "terms_version": command.terms_version,
                "marketing_consent": command.marketing_consent,
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="NaturalPersonLenderRegistered",
            aggregate_type="User",
            aggregate_id=str(user.id),
            payload={"email": user.email, "phone_number_present": bool(user.phone_number)},
            idempotency_key=f"user:{user.id}:registered",
        )
    )
    return user


@transaction.atomic
def issue_magic_link(command: MagicLinkRequestCommand) -> MagicLinkIssueResult:
    email = normalize_email(command.email)
    user = User.objects.filter(email=email).first()
    if user is None or not user.can_login:
        raise InvalidOrExpiredTokenError("Account cannot receive a login link.")

    raw_token = secrets.token_urlsafe(32)
    token = EmailLoginToken.objects.create(
        user=user,
        email=user.email,
        token_digest=digest_secret(raw_token),
        encrypted_token=encrypt_delivery_secret(raw_token),
        expires_at=timezone.now() + command.ttl,
        requested_ip=command.ip_address,
        requested_user_agent=command.user_agent,
    )
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"magic-link:{token.id}",
            topic="email.magic_link_requested",
            payload={
                "user_id": str(user.id),
                "email": user.email,
                "delivery_secret_type": "email_login_token",
                "delivery_secret_ref": str(token.id),
                "secret_redacted": True,
                "expires_at": token.expires_at.isoformat(),
            },
        )
    )
    record_audit_event(
        AuditCommand(
            actor=ActorRef("investor", str(user.id)),
            action="auth.magic_link_requested",
            target_type="User",
            target_id=str(user.id),
        )
    )
    return MagicLinkIssueResult(login_token=token, raw_token=raw_token)


def consume_magic_link(command: MagicLinkConsumeCommand) -> User:
    failure: AccountsAuthError | None = None
    with transaction.atomic():
        token = (
            EmailLoginToken.objects.select_for_update()
            .filter(token_digest=digest_secret(command.raw_token))
            .first()
        )
        now = timezone.now()
        if token is None or token.used_at is not None or token.expires_at <= now:
            _audit_auth_failure(
                action="auth.magic_link_failed",
                user_id=str(token.user_id) if token is not None else "",
                metadata={"reason": "invalid_or_expired"},
            )
            failure = InvalidOrExpiredTokenError("Login link is invalid or expired.")
        elif not token.user.can_login:
            _audit_auth_failure(
                action="auth.magic_link_failed",
                user_id=str(token.user_id),
                metadata={"reason": "account_cannot_login"},
            )
            failure = InvalidOrExpiredTokenError("Account cannot log in.")
        else:
            token.used_at = now
            token.consumed_ip = command.ip_address
            token.consumed_user_agent = command.user_agent
            token.save(
                update_fields=["used_at", "consumed_ip", "consumed_user_agent", "updated_at"]
            )
            record_audit_event(
                AuditCommand(
                    actor=ActorRef("investor", str(token.user_id)),
                    action="auth.magic_link_consumed",
                    target_type="User",
                    target_id=str(token.user_id),
                )
            )

    if failure is not None:
        raise failure
    assert token is not None
    return token.user


@transaction.atomic
def issue_sensitive_action_code(
    command: SensitiveActionCodeCommand,
) -> SensitiveActionCodeIssueResult:
    if not command.user.can_login:
        raise InvalidOrExpiredCodeError("Account cannot receive a sensitive-action code.")
    if command.max_attempts <= 0:
        raise AccountsAuthError("max_attempts must be positive.")

    now = timezone.now()
    cooldown_seconds = settings.AUTH_SENSITIVE_CODE_COOLDOWN_SECONDS
    latest_active = (
        SensitiveActionCode.objects.filter(
            user=command.user,
            action=command.action,
            consumed_at__isnull=True,
            superseded_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )
    if latest_active is not None:
        elapsed = now - latest_active.created_at
        if elapsed < timedelta(seconds=cooldown_seconds):
            raise SensitiveActionCodeThrottleError("Sensitive-action code requested too recently.")

        SensitiveActionCode.objects.filter(
            user=command.user,
            action=command.action,
            consumed_at__isnull=True,
            superseded_at__isnull=True,
            expires_at__gt=now,
        ).update(superseded_at=now)

    raw_code = f"{secrets.randbelow(1_000_000):06d}"
    code_record = SensitiveActionCode.objects.create(
        user=command.user,
        action=command.action,
        code_digest=digest_secret(raw_code),
        encrypted_code=encrypt_delivery_secret(raw_code),
        expires_at=now + command.ttl,
        max_attempts=command.max_attempts,
        requested_ip=command.ip_address,
        requested_user_agent=command.user_agent,
    )
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"sensitive-action-code:{code_record.id}",
            topic="email.sensitive_action_code_requested",
            payload={
                "user_id": str(command.user.id),
                "email": command.user.email,
                "action": command.action,
                "delivery_secret_type": "sensitive_action_code",
                "delivery_secret_ref": str(code_record.id),
                "secret_redacted": True,
                "expires_at": code_record.expires_at.isoformat(),
            },
        )
    )
    record_audit_event(
        AuditCommand(
            actor=ActorRef("investor", str(command.user.id)),
            action="auth.sensitive_action_code_requested",
            target_type="User",
            target_id=str(command.user.id),
            metadata={"action": command.action},
        )
    )
    return SensitiveActionCodeIssueResult(code_record=code_record, raw_code=raw_code)


@transaction.atomic
def request_phone_verification(
    command: PhoneVerificationRequestCommand,
) -> PhoneVerificationRequestResult:
    user = command.user
    if not user.can_login:
        raise InvalidOrExpiredCodeError("Account cannot receive a phone verification code.")
    if user.is_phone_verified:
        raise PhoneAlreadyVerifiedError("Phone number is already verified.")
    if not user.phone_number.strip():
        raise AccountsAuthError("Phone number is required.")

    now = timezone.now()
    cooldown_seconds = settings.AUTH_PHONE_VERIFICATION_COOLDOWN_SECONDS
    latest_active = (
        PhoneVerificationChallenge.objects.filter(
            user=user,
            status=PhoneVerificationStatus.PENDING,
            superseded_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )
    if latest_active is not None:
        elapsed = now - latest_active.created_at
        if elapsed < timedelta(seconds=cooldown_seconds):
            raise PhoneVerificationThrottleError("Phone verification requested too recently.")

        PhoneVerificationChallenge.objects.filter(
            user=user,
            status=PhoneVerificationStatus.PENDING,
            superseded_at__isnull=True,
            expires_at__gt=now,
        ).update(
            status=PhoneVerificationStatus.SUPERSEDED,
            superseded_at=now,
        )

    ttl = command.ttl or timedelta(seconds=settings.AUTH_PHONE_VERIFICATION_TTL_SECONDS)
    max_attempts = command.max_attempts or settings.AUTH_PHONE_VERIFICATION_MAX_ATTEMPTS
    if max_attempts <= 0:
        raise AccountsAuthError("max_attempts must be positive.")

    raw_code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = PhoneVerificationChallenge.objects.create(
        user=user,
        phone_number=user.phone_number,
        provider=settings.PHONE_VERIFICATION_PROVIDER,
        code_digest=digest_secret(raw_code),
        encrypted_code=encrypt_delivery_secret(raw_code),
        expires_at=now + ttl,
        max_attempts=max_attempts,
        requested_ip=command.ip_address,
        requested_user_agent=command.user_agent,
    )
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"phone-verification:{challenge.id}",
            topic="sms.phone_verification_requested",
            payload={
                "user_id": str(user.id),
                "phone_number": user.phone_number,
                "delivery_secret_type": "phone_verification_code",
                "delivery_secret_ref": str(challenge.id),
                "secret_redacted": True,
                "expires_at": challenge.expires_at.isoformat(),
            },
        )
    )
    record_audit_event(
        AuditCommand(
            actor=ActorRef("investor", str(user.id)),
            action="auth.phone_verification_requested",
            target_type="User",
            target_id=str(user.id),
            metadata={"provider": challenge.provider},
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="PhoneVerificationRequested",
            aggregate_type="User",
            aggregate_id=str(user.id),
            payload={"challenge_id": str(challenge.id), "provider": challenge.provider},
            idempotency_key=f"user:{user.id}:phone-verification:{challenge.id}:requested",
        )
    )
    return PhoneVerificationRequestResult(challenge=challenge, raw_code=raw_code)


def confirm_phone_verification(
    command: PhoneVerificationConfirmCommand,
) -> PhoneVerificationChallenge:
    failure: AccountsAuthError | None = None
    with transaction.atomic():
        challenge = (
            PhoneVerificationChallenge.objects.select_for_update()
            .filter(id=command.challenge_id, user=command.user)
            .first()
        )
        now = timezone.now()
        if (
            challenge is None
            or challenge.status != PhoneVerificationStatus.PENDING
            or challenge.expires_at <= now
            or challenge.superseded_at is not None
        ):
            if (
                challenge is not None
                and challenge.status == PhoneVerificationStatus.PENDING
                and challenge.expires_at <= now
            ):
                challenge.status = PhoneVerificationStatus.EXPIRED
                challenge.save(update_fields=["status", "updated_at"])
            _audit_auth_failure(
                action="auth.phone_verification_failed",
                user_id=str(command.user.id),
                metadata={"reason": "invalid_expired_or_superseded"},
            )
            failure = InvalidOrExpiredCodeError("Phone verification code is invalid or expired.")
        elif challenge.attempts >= challenge.max_attempts:
            _audit_auth_failure(
                action="auth.phone_verification_failed",
                user_id=str(challenge.user_id),
                metadata={"reason": "too_many_attempts"},
            )
            failure = TooManyCodeAttemptsError("Phone verification attempt limit exceeded.")
        elif not secrets.compare_digest(challenge.code_digest, digest_secret(command.raw_code)):
            challenge.attempts += 1
            if challenge.attempts >= challenge.max_attempts:
                challenge.status = PhoneVerificationStatus.FAILED
                challenge.save(update_fields=["attempts", "status", "updated_at"])
                _audit_auth_failure(
                    action="auth.phone_verification_failed",
                    user_id=str(challenge.user_id),
                    metadata={"reason": "too_many_attempts"},
                )
                failure = TooManyCodeAttemptsError(
                    "Phone verification attempt limit exceeded."
                )
            else:
                challenge.save(update_fields=["attempts", "updated_at"])
                _audit_auth_failure(
                    action="auth.phone_verification_failed",
                    user_id=str(challenge.user_id),
                    metadata={"reason": "invalid_code"},
                )
                failure = InvalidOrExpiredCodeError(
                    "Phone verification code is invalid or expired."
                )
        elif failure is None:
            challenge.attempts += 1
            challenge.status = PhoneVerificationStatus.VERIFIED
            challenge.verified_at = now
            challenge.confirmed_ip = command.ip_address
            challenge.confirmed_user_agent = command.user_agent
            challenge.save(
                update_fields=[
                    "attempts",
                    "status",
                    "verified_at",
                    "confirmed_ip",
                    "confirmed_user_agent",
                    "updated_at",
                ]
            )
            challenge.user.phone_verified_at = now
            challenge.user.save(update_fields=["phone_verified_at"])
            record_audit_event(
                AuditCommand(
                    actor=ActorRef("investor", str(challenge.user_id)),
                    action="auth.phone_verified",
                    target_type="User",
                    target_id=str(challenge.user_id),
                    metadata={"challenge_id": str(challenge.id)},
                )
            )
            record_domain_event(
                DomainEventCommand(
                    event_type="PhoneVerified",
                    aggregate_type="User",
                    aggregate_id=str(challenge.user_id),
                    payload={"challenge_id": str(challenge.id)},
                    idempotency_key=f"user:{challenge.user_id}:phone-verification:{challenge.id}:verified",
                )
            )

    if failure is not None:
        raise failure
    assert challenge is not None
    return challenge


def consume_sensitive_action_code(
    command: SensitiveActionCodeConsumeCommand,
) -> SensitiveActionCode:
    failure: AccountsAuthError | None = None
    with transaction.atomic():
        code_record = (
            SensitiveActionCode.objects.select_for_update().filter(id=command.code_id).first()
        )
        now = timezone.now()
        if (
            code_record is None
            or code_record.consumed_at is not None
            or code_record.expires_at <= now
            or code_record.superseded_at is not None
        ):
            _audit_auth_failure(
                action="auth.sensitive_action_code_failed",
                user_id=str(code_record.user_id) if code_record is not None else "",
                metadata={"reason": "invalid_expired_or_superseded"},
            )
            failure = InvalidOrExpiredCodeError("Sensitive-action code is invalid or expired.")
        elif code_record.attempts >= code_record.max_attempts:
            _audit_auth_failure(
                action="auth.sensitive_action_code_failed",
                user_id=str(code_record.user_id),
                metadata={"action": code_record.action, "reason": "too_many_attempts"},
            )
            failure = TooManyCodeAttemptsError("Sensitive-action code attempt limit exceeded.")
        elif not secrets.compare_digest(code_record.code_digest, digest_secret(command.raw_code)):
            code_record.attempts += 1
            code_record.save(update_fields=["attempts", "updated_at"])
            if code_record.attempts >= code_record.max_attempts:
                _audit_auth_failure(
                    action="auth.sensitive_action_code_failed",
                    user_id=str(code_record.user_id),
                    metadata={"action": code_record.action, "reason": "too_many_attempts"},
                )
                failure = TooManyCodeAttemptsError(
                    "Sensitive-action code attempt limit exceeded."
                )
            else:
                _audit_auth_failure(
                    action="auth.sensitive_action_code_failed",
                    user_id=str(code_record.user_id),
                    metadata={"action": code_record.action, "reason": "invalid_code"},
                )
                failure = InvalidOrExpiredCodeError(
                    "Sensitive-action code is invalid or expired."
                )
        elif failure is None:
            code_record.attempts += 1
            code_record.consumed_at = now
            code_record.consumed_ip = command.ip_address
            code_record.consumed_user_agent = command.user_agent
            code_record.save(
                update_fields=[
                    "attempts",
                    "consumed_at",
                    "consumed_ip",
                    "consumed_user_agent",
                    "updated_at",
                ]
            )
            record_audit_event(
                AuditCommand(
                    actor=ActorRef("investor", str(code_record.user_id)),
                    action="auth.sensitive_action_code_consumed",
                    target_type="User",
                    target_id=str(code_record.user_id),
                    metadata={"action": code_record.action},
                )
            )

    if failure is not None:
        raise failure
    assert code_record is not None
    return code_record


def delivery_secret_for_magic_link(token: EmailLoginToken) -> str:
    return decrypt_delivery_secret(token.encrypted_token)


def delivery_secret_for_sensitive_action_code(code_record: SensitiveActionCode) -> str:
    return decrypt_delivery_secret(code_record.encrypted_code)


def delivery_secret_for_phone_verification(challenge: PhoneVerificationChallenge) -> str:
    return decrypt_delivery_secret(challenge.encrypted_code)
