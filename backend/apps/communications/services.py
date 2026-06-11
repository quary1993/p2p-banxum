from __future__ import annotations

import html
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from backend.apps.communications.models import (
    CommunicationEvent,
    CommunicationEventType,
    EmailDeliveryRecord,
    EmailDeliveryStatus,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.models.events import OutboxStatus
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    mark_outbox_failed,
    mark_outbox_processed,
    record_domain_event,
)


class CommunicationsError(RuntimeError):
    pass


class UnsupportedEmailTopicError(CommunicationsError):
    pass


class EmailProviderError(CommunicationsError):
    pass


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    recipient_email: str
    subject: str
    body_text: str
    body_html: str
    template_key: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmailProviderResult:
    provider_message_id: str


class EmailProvider(Protocol):
    provider_name: str

    def send(self, email: RenderedEmail) -> EmailProviderResult:
        ...


@dataclass(frozen=True, slots=True)
class DispatchEmailOutboxCommand:
    limit: int | None = None
    now: Any | None = None


@dataclass(frozen=True, slots=True)
class DispatchEmailOutboxResult:
    processed_count: int
    sent_count: int
    failed_count: int
    dead_letter_count: int
    skipped_count: int
    message_ids: tuple[int, ...]


class MockEmailProvider:
    provider_name = "mock"

    def send(self, email: RenderedEmail) -> EmailProviderResult:
        stable = f"{email.template_key}:{email.recipient_email}:{timezone.now().timestamp()}"
        return EmailProviderResult(provider_message_id=f"mock-{abs(hash(stable))}")


class SendGridEmailProvider:
    provider_name = "sendgrid"

    def send(self, email: RenderedEmail) -> EmailProviderResult:
        api_key = settings.SENDGRID_API_KEY
        from_email = settings.SENDGRID_FROM_EMAIL
        from_name = settings.SENDGRID_FROM_NAME
        if not api_key or not from_email:
            raise EmailProviderError("SendGrid provider is not configured.")

        payload = {
            "personalizations": [{"to": [{"email": email.recipient_email}]}],
            "from": {"email": from_email, "name": from_name},
            "subject": email.subject,
            "content": [
                {"type": "text/plain", "value": email.body_text},
                {"type": "text/html", "value": email.body_html or _html_from_text(email.body_text)},
            ],
        }
        request = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=settings.SENDGRID_TIMEOUT_SECONDS,
            ) as response:
                if response.status < 200 or response.status >= 300:
                    raise EmailProviderError(f"SendGrid returned HTTP {response.status}.")
                provider_message_id = response.headers.get("X-Message-Id", "")
        except urllib.error.HTTPError as exc:
            raise EmailProviderError(f"SendGrid returned HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise EmailProviderError("SendGrid request failed.") from exc
        return EmailProviderResult(provider_message_id=provider_message_id)


def _email_provider() -> EmailProvider:
    provider = settings.COMMUNICATIONS_EMAIL_PROVIDER.lower()
    if provider == "sendgrid":
        return SendGridEmailProvider()
    if provider in {"mock", "local"}:
        return MockEmailProvider()
    raise EmailProviderError(f"Unsupported email provider '{provider}'.")


def _auth_services_module() -> Any:
    from importlib import import_module

    return import_module("backend.apps.accounts_auth.services")


def _email_login_token_model() -> Any:
    return apps.get_model("accounts_auth", "EmailLoginToken")


def _sensitive_action_code_model() -> Any:
    return apps.get_model("accounts_auth", "SensitiveActionCode")


def _base_url() -> str:
    base_url = str(settings.PUBLIC_APP_BASE_URL).rstrip("/")
    if not base_url:
        raise CommunicationsError("PUBLIC_APP_BASE_URL is required to render email links.")
    return base_url


def _html_from_text(body_text: str) -> str:
    return "<br>".join(html.escape(body_text).splitlines())


def _render_magic_link_email(message: OutboxMessage) -> RenderedEmail:
    payload = message.payload
    token_id = str(payload.get("delivery_secret_ref", ""))
    recipient = str(payload.get("email", "")).strip().lower()
    if not token_id or not recipient:
        raise CommunicationsError("Magic-link email payload is incomplete.")

    token_model = _email_login_token_model()
    token = token_model.objects.select_related("user").get(id=token_id)
    raw_token = _auth_services_module().delivery_secret_for_magic_link(token)
    login_url = f"{_base_url()}/login?token={urllib.parse.quote(raw_token)}"
    platform = settings.PLATFORM_BRAND_NAME
    operator = settings.LEGAL_OPERATOR_NAME
    subject = f"Your {platform} login link"
    body_text = (
        f"Use this secure link to sign in to {platform}:\n\n"
        f"{login_url}\n\n"
        f"The link expires at {token.expires_at.isoformat()} and can be used only once.\n"
        "If you did not request this email, you can ignore it.\n\n"
        f"{platform} is operated by {operator}."
    )
    return RenderedEmail(
        recipient_email=recipient,
        subject=subject,
        body_text=body_text,
        body_html=_html_from_text(body_text),
        template_key="auth.magic_link.v1",
        metadata={
            "user_id": str(payload.get("user_id", "")),
            "expires_at": token.expires_at.isoformat(),
            "secret_redacted_in_outbox": bool(payload.get("secret_redacted")),
        },
    )


def _render_sensitive_action_code_email(message: OutboxMessage) -> RenderedEmail:
    payload = message.payload
    code_id = str(payload.get("delivery_secret_ref", ""))
    recipient = str(payload.get("email", "")).strip().lower()
    action = str(payload.get("action", "sensitive_action"))
    if not code_id or not recipient:
        raise CommunicationsError("Sensitive-action email payload is incomplete.")

    code_model = _sensitive_action_code_model()
    code_record = code_model.objects.select_related("user").get(id=code_id)
    raw_code = _auth_services_module().delivery_secret_for_sensitive_action_code(code_record)
    platform = settings.PLATFORM_BRAND_NAME
    operator = settings.LEGAL_OPERATOR_NAME
    subject = f"Your {platform} confirmation code"
    body_text = (
        f"Your {platform} confirmation code is:\n\n"
        f"{raw_code}\n\n"
        f"It expires at {code_record.expires_at.isoformat()} and is valid for {action}.\n"
        "If you did not request this code, contact support and do not share it.\n\n"
        f"{platform} is operated by {operator}."
    )
    return RenderedEmail(
        recipient_email=recipient,
        subject=subject,
        body_text=body_text,
        body_html=_html_from_text(body_text),
        template_key=f"auth.{action}.code.v1",
        metadata={
            "user_id": str(payload.get("user_id", "")),
            "action": action,
            "expires_at": code_record.expires_at.isoformat(),
            "secret_redacted_in_outbox": bool(payload.get("secret_redacted")),
        },
    )


def _render_payload_email(message: OutboxMessage) -> RenderedEmail:
    payload = message.payload
    recipient = str(
        payload.get("email") or payload.get("recipient_email") or payload.get("to_email") or ""
    ).strip().lower()
    subject = str(payload.get("subject", "")).strip()
    body_text = str(payload.get("body_text", "")).strip()
    body_html = str(payload.get("body_html", "")).strip()
    template_key = str(payload.get("template_key", message.topic)).strip()
    if not recipient or not subject or not (body_text or body_html):
        raise UnsupportedEmailTopicError(
            f"Email topic '{message.topic}' has no renderable template."
        )
    if not body_text:
        body_text = html.unescape(body_html)
    if not body_html:
        body_html = _html_from_text(body_text)
    return RenderedEmail(
        recipient_email=recipient,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        template_key=template_key,
        metadata={"payload_template": True},
    )


def render_email_for_outbox_message(message: OutboxMessage) -> RenderedEmail:
    if message.topic == "email.magic_link_requested":
        return _render_magic_link_email(message)
    if message.topic == "email.sensitive_action_code_requested":
        return _render_sensitive_action_code_email(message)
    if message.topic.startswith("email."):
        return _render_payload_email(message)
    raise UnsupportedEmailTopicError(f"Outbox topic '{message.topic}' is not an email topic.")


def _record_delivery_attempt(
    *,
    message: OutboxMessage,
    rendered_email: RenderedEmail | None,
    provider_name: str,
    attempt_number: int,
    status: EmailDeliveryStatus,
    provider_message_id: str = "",
    error: str = "",
) -> EmailDeliveryRecord:
    return cast(
        EmailDeliveryRecord,
        EmailDeliveryRecord.objects.create(
            outbox_message=message,
            topic=message.topic,
            template_key=rendered_email.template_key if rendered_email else message.topic,
            recipient_email=rendered_email.recipient_email if rendered_email else "",
            subject=rendered_email.subject if rendered_email else "",
            body_text=rendered_email.body_text if rendered_email else "",
            body_html=rendered_email.body_html if rendered_email else "",
            provider=provider_name,
            provider_message_id=provider_message_id,
            status=status,
            attempt_number=attempt_number,
            sent_at=timezone.now() if status == EmailDeliveryStatus.SENT else None,
            error=error[:4000],
            metadata=rendered_email.metadata if rendered_email else {},
        ),
    )


def _record_delivery_events(record: EmailDeliveryRecord) -> None:
    if record.status == EmailDeliveryStatus.SENT:
        event_type = CommunicationEventType.EMAIL_SENT
        action = "communications.email_sent"
        domain_event = "EmailSent"
    else:
        event_type = CommunicationEventType.EMAIL_FAILED
        action = "communications.email_failed"
        domain_event = "EmailDeliveryFailed"
    CommunicationEvent.objects.create(
        event_type=event_type,
        outbox_message=record.outbox_message,
        email_delivery_record=record,
        metadata={
            "topic": record.topic,
            "recipient_email": record.recipient_email,
            "attempt_number": record.attempt_number,
            "status": record.status,
        },
    )
    record_audit_event(
        AuditCommand(
            actor=ActorRef.system(),
            action=action,
            target_type="OutboxMessage",
            target_id=str(record.outbox_message_id),
            metadata={
                "email_delivery_record_id": str(record.id),
                "topic": record.topic,
                "recipient_email": record.recipient_email,
                "attempt_number": record.attempt_number,
                "status": record.status,
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type=domain_event,
            aggregate_type="OutboxMessage",
            aggregate_id=str(record.outbox_message_id),
            payload={
                "email_delivery_record_id": str(record.id),
                "topic": record.topic,
                "status": record.status,
            },
            idempotency_key=f"communications:{record.status}:{record.id}",
        )
    )


def _due_email_message_ids(*, limit: int, now: Any) -> list[int]:
    return list(
        OutboxMessage.objects.filter(
            status=OutboxStatus.PENDING,
            topic__startswith="email.",
        )
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .order_by("created_at", "id")
        .values_list("id", flat=True)[:limit]
    )


@transaction.atomic
def _dispatch_one_email_message(message_id: int, *, provider: EmailProvider, now: Any) -> bool:
    message = (
        OutboxMessage.objects.select_for_update()
        .filter(id=message_id, status=OutboxStatus.PENDING, topic__startswith="email.")
        .first()
    )
    if message is None:
        return False
    if message.next_attempt_at is not None and message.next_attempt_at > now:
        return False

    attempt_number = message.attempts + 1
    rendered_email: RenderedEmail | None = None
    try:
        rendered_email = render_email_for_outbox_message(message)
        provider_result = provider.send(rendered_email)
        record = _record_delivery_attempt(
            message=message,
            rendered_email=rendered_email,
            provider_name=provider.provider_name,
            provider_message_id=provider_result.provider_message_id,
            attempt_number=attempt_number,
            status=EmailDeliveryStatus.SENT,
        )
        mark_outbox_processed(message)
        _record_delivery_events(record)
        return True
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        record = _record_delivery_attempt(
            message=message,
            rendered_email=rendered_email,
            provider_name=provider.provider_name,
            attempt_number=attempt_number,
            status=EmailDeliveryStatus.FAILED,
            error=error,
        )
        mark_outbox_failed(message, error)
        _record_delivery_events(record)
        return True


def dispatch_due_email_outbox_messages(
    command: DispatchEmailOutboxCommand | None = None,
) -> DispatchEmailOutboxResult:
    command = command or DispatchEmailOutboxCommand()
    now = command.now or timezone.now()
    limit = command.limit or settings.COMMUNICATIONS_DISPATCH_LIMIT
    provider = _email_provider()
    message_ids = _due_email_message_ids(limit=limit, now=now)

    processed_ids: list[int] = []
    skipped = 0
    for message_id in message_ids:
        dispatched = _dispatch_one_email_message(message_id, provider=provider, now=now)
        if dispatched:
            processed_ids.append(message_id)
        else:
            skipped += 1

    records = EmailDeliveryRecord.objects.filter(outbox_message_id__in=processed_ids)
    latest_records = {
        record.outbox_message_id: record
        for record in records.order_by("outbox_message_id", "attempt_number")
    }
    sent = sum(1 for record in latest_records.values() if record.status == EmailDeliveryStatus.SENT)
    failed = sum(
        1 for record in latest_records.values() if record.status == EmailDeliveryStatus.FAILED
    )
    dead_letter = OutboxMessage.objects.filter(
        id__in=processed_ids,
        status=OutboxStatus.DEAD_LETTER,
    ).count()
    return DispatchEmailOutboxResult(
        processed_count=len(processed_ids),
        sent_count=sent,
        failed_count=failed,
        dead_letter_count=dead_letter,
        skipped_count=skipped,
        message_ids=tuple(processed_ids),
    )


def dispatch_email_outbox_message_now(message_id: int) -> bool:
    """Dispatch one queued email immediately.

    Auth and step-up emails are time-sensitive. They still go through the
    durable outbox, but callers can ask for immediate delivery after their
    transaction commits so the scheduled dispatcher is only the retry fallback.
    """
    provider = _email_provider()
    return _dispatch_one_email_message(message_id, provider=provider, now=timezone.now())
