from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from backend.apps.accounts_auth.models import (
    AccountStatus,
    AccountType,
    EmailLoginToken,
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


def normalize_email(email: str) -> str:
    normalized = User.objects.normalize_email(email).strip().lower()
    if not normalized:
        raise AccountsAuthError("Email is required.")
    return normalized


def _digest_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


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


@transaction.atomic
def register_natural_person_lender(command: RegisterNaturalPersonCommand) -> User:
    email = normalize_email(command.email)
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
        token_digest=_digest_secret(raw_token),
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
                "token": raw_token,
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


@transaction.atomic
def consume_magic_link(command: MagicLinkConsumeCommand) -> User:
    token = (
        EmailLoginToken.objects.select_for_update()
        .filter(token_digest=_digest_secret(command.raw_token))
        .first()
    )
    now = timezone.now()
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise InvalidOrExpiredTokenError("Login link is invalid or expired.")
    if not token.user.can_login:
        raise InvalidOrExpiredTokenError("Account cannot log in.")

    token.used_at = now
    token.consumed_ip = command.ip_address
    token.consumed_user_agent = command.user_agent
    token.save(update_fields=["used_at", "consumed_ip", "consumed_user_agent", "updated_at"])
    record_audit_event(
        AuditCommand(
            actor=ActorRef("investor", str(token.user_id)),
            action="auth.magic_link_consumed",
            target_type="User",
            target_id=str(token.user_id),
        )
    )
    return token.user


@transaction.atomic
def issue_sensitive_action_code(
    command: SensitiveActionCodeCommand,
) -> SensitiveActionCodeIssueResult:
    if not command.user.can_login:
        raise InvalidOrExpiredCodeError("Account cannot receive a sensitive-action code.")
    if command.max_attempts <= 0:
        raise AccountsAuthError("max_attempts must be positive.")

    raw_code = f"{secrets.randbelow(1_000_000):06d}"
    code_record = SensitiveActionCode.objects.create(
        user=command.user,
        action=command.action,
        code_digest=_digest_secret(raw_code),
        expires_at=timezone.now() + command.ttl,
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
                "code": raw_code,
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
        ):
            raise InvalidOrExpiredCodeError("Sensitive-action code is invalid or expired.")
        if code_record.attempts >= code_record.max_attempts:
            raise TooManyCodeAttemptsError("Sensitive-action code attempt limit exceeded.")

        if not secrets.compare_digest(code_record.code_digest, _digest_secret(command.raw_code)):
            code_record.attempts += 1
            code_record.save(update_fields=["attempts", "updated_at"])
            if code_record.attempts >= code_record.max_attempts:
                failure = TooManyCodeAttemptsError(
                    "Sensitive-action code attempt limit exceeded."
                )
            else:
                failure = InvalidOrExpiredCodeError(
                    "Sensitive-action code is invalid or expired."
                )
        else:
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
    return code_record
