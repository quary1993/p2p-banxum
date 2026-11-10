"""IP of Webby-Soft SRL. Portal Help messages and account closure requests by email.

U33-DEC-35: the Help form is sent by email to the support mailbox, with no ticket system. The
investor gets a real receipt (a reference and an email), the page or investment the message
is about, and no unnecessary sensitive data. U33-DEC-28: "Close account" sends a request to
the team; receiving it does not close the account. The team checks balances, investments and
open obligations first (an admin task is opened) and confirms the closure separately.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import F, Model

from backend.apps.communications.models import (
    InvestorSupportRequest,
    InvestorSupportRequestKind,
    PublicEnquiryReferenceCounter,
)
from backend.apps.communications.services import CommunicationsError
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.selectors.settings import get_platform_setting_value
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message
from backend.apps.platform_core.services.rate_limits import (
    WindowLimit,
    WindowRule,
    record_window_hits,
    window_wait_seconds,
)

SUPPORT_REQUEST_EMAIL_TOPIC = "email.investor_support_request"
SUPPORT_REQUEST_RECEIPT_TOPIC = "email.support_request_received"
SUPPORT_REQUEST_SCOPE = "investor-support-request"
MESSAGE_MAX_LENGTH = 4000
TOPIC_MAX_LENGTH = 120
CONTEXT_TYPES = ("", "holding")
REFERENCE_PREFIXES: dict[str, str] = {
    InvestorSupportRequestKind.HELP: "SUP",
    InvestorSupportRequestKind.ACCOUNT_CLOSURE: "CLS",
}
# Generous for a person, low enough to stop a loop or a script.
RATE_RULES: dict[str, tuple[WindowRule, ...]] = {
    InvestorSupportRequestKind.HELP: (
        WindowRule("hour", 3600, 10),
        WindowRule("day", 86400, 30),
    ),
    InvestorSupportRequestKind.ACCOUNT_CLOSURE: (WindowRule("day", 86400, 3),),
}


class SupportRequestError(CommunicationsError):
    pass


class SupportRequestThrottled(SupportRequestError):
    def __init__(self, wait_seconds: int) -> None:
        super().__init__("Too many messages. Try again later or write to the support email.")
        self.wait_seconds = wait_seconds


class SupportRequestConflict(SupportRequestError):
    pass


@dataclass(frozen=True, slots=True)
class SubmitSupportRequestCommand:
    actor: Model
    kind: str
    idempotency_key: str
    topic: str = ""
    message: str = ""
    context_type: str = ""
    context_id: str = ""


def support_mailbox() -> str:
    """The support mailbox: platform setting ``platform.support_email``, then SUPPORT_EMAIL."""
    configured = str(get_platform_setting_value("platform.support_email", "") or "").strip()
    fallback = str(getattr(settings, "SUPPORT_EMAIL", "") or "support@banxum.com").strip()
    for candidate in (configured, fallback):
        try:
            validate_email(candidate)
        except DjangoValidationError:
            continue
        return candidate.lower()
    raise SupportRequestError("The support mailbox is not configured.")


def _allocate_reference(kind: str) -> str:
    prefix = REFERENCE_PREFIXES[kind]
    year = business_date(now_utc()).year
    with transaction.atomic():
        PublicEnquiryReferenceCounter.objects.get_or_create(prefix=prefix, year=year)
        PublicEnquiryReferenceCounter.objects.filter(prefix=prefix, year=year).update(
            last_number=F("last_number") + 1
        )
        number = PublicEnquiryReferenceCounter.objects.values_list("last_number", flat=True).get(
            prefix=prefix, year=year
        )
    return f"{prefix}-{year}-{int(number):04d}"


def _fingerprint(values: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()


def _clean_text(value: str, *, label: str, max_length: int, required: bool) -> str:
    cleaned = str(value or "").replace("\r\n", "\n").strip()
    if required and not cleaned:
        raise SupportRequestError(f"Enter the {label}.")
    if len(cleaned) > max_length:
        raise SupportRequestError(f"The {label} can be at most {max_length} characters.")
    return cleaned


def _holding_context_label(*, investor_user_id: str, holding_id: str) -> str:
    """The investment a message is about, read from the investor's own holding only."""
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holding = (
        holding_model.objects.select_related("loan")
        .filter(pk=holding_id, investor_user_id=investor_user_id)
        .first()
        if holding_id
        else None
    )
    if holding is None:
        raise SupportRequestError("The investment of this message was not found.")
    return str(holding.loan.title)[:255]


def _rate_limits(*, kind: str, investor_user_id: str) -> list[WindowLimit]:
    return [
        WindowLimit(identifier=f"{kind}:{investor_user_id}", rule=rule) for rule in RATE_RULES[kind]
    ]


def _support_email_payload(request: InvestorSupportRequest) -> dict[str, Any]:
    brand = str(getattr(settings, "PLATFORM_BRAND_NAME", "") or "BANXUM")
    closure = request.kind == InvestorSupportRequestKind.ACCOUNT_CLOSURE
    subject = (
        f"Account closure request {request.reference}"
        if closure
        else f"Portal message {request.reference}: {request.topic}"
    )
    rows = [
        ["Reference", request.reference],
        ["Investor reference", request.investor_reference or "-"],
        ["Email", request.investor_email],
    ]
    if request.topic:
        rows.append(["Topic", request.topic])
    if request.context_label:
        rows.append(["About the investment", request.context_label])
    intro = (
        "The investor asked to close their account. An admin task is open. Check balances, "
        "investments and open obligations first; the account is not closed yet."
        if closure
        else f"An investor sent this message from the {brand} portal Help page."
    )
    body = [intro]
    if request.message:
        body.append(f"Message:\n{request.message}")
    body.append("Answer the investor by email; reply to this email to reach them.")
    # No "user_id" key: this email is for the team, not the investor's notification centre.
    return {
        "email": support_mailbox(),
        "reply_to": request.investor_email,
        "investor_user_id": str(request.investor_user_id),
        "subject": subject,
        "notice_label": "Portal support request",
        "headline": "Account closure request" if closure else "New portal message",
        "status_label": "Request received",
        "status_tone": "warning",
        "body_text": "\n\n".join(body),
        "data_rows": rows,
        "template_key": "support.investor_request.v1",
        "fine_print": (
            "Internal email from the investor portal. Keep the reference when you answer."
        ),
        "metadata": {"support_request_id": str(request.id), "kind": request.kind},
    }


def _receipt_email_payload(request: InvestorSupportRequest) -> dict[str, Any]:
    closure = request.kind == InvestorSupportRequestKind.ACCOUNT_CLOSURE
    if closure:
        subject = f"We received your account closure request ({request.reference})"
        body = (
            "We received your request to close your account. Your account is not closed yet. "
            "We first check your balances, investments and any open obligations, and we "
            "confirm by email when the account is closed.\n\n"
            "Records that the law requires, and those needed to settle open obligations, "
            "are kept."
        )
    else:
        subject = f"We received your message ({request.reference})"
        body = (
            f"We received your message about: {request.topic}. Our team answers by email. "
            "Keep the reference if you write to us again about it."
        )
    rows = [["Reference", request.reference]]
    if request.context_label:
        rows.append(["About the investment", request.context_label])
    return {
        "user_id": str(request.investor_user_id),
        "email": request.investor_email,
        "subject": subject,
        "notice_label": "Support",
        "headline": "Request received" if closure else "Message received",
        "status_label": "Received",
        "status_tone": "info",
        "body_text": body,
        "data_rows": rows,
        "template_key": "support.request_received.v1",
        "metadata": {"support_request_id": str(request.id), "kind": request.kind},
    }


def _existing_for_key(idempotency_key: str, fingerprint: str) -> InvestorSupportRequest | None:
    existing = InvestorSupportRequest.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if existing.request_fingerprint != fingerprint:
        raise SupportRequestConflict("This request key was already used for another message.")
    return existing


def submit_support_request(command: SubmitSupportRequestCommand) -> InvestorSupportRequest:
    """Store the request, email it to the support mailbox and send the investor a receipt."""
    actor: Any = command.actor
    if command.kind not in REFERENCE_PREFIXES:
        raise SupportRequestError("Unknown request kind.")
    kind = command.kind
    idempotency_key = _clean_text(
        command.idempotency_key, label="request key", max_length=160, required=True
    )
    closure = kind == InvestorSupportRequestKind.ACCOUNT_CLOSURE
    topic = (
        ""
        if closure
        else _clean_text(command.topic, label="topic", max_length=TOPIC_MAX_LENGTH, required=True)
    )
    message = _clean_text(
        command.message, label="message", max_length=MESSAGE_MAX_LENGTH, required=not closure
    )
    if command.context_type not in CONTEXT_TYPES:
        raise SupportRequestError("Unknown message context.")
    investor_user_id = str(actor.pk)
    context_id = str(command.context_id or "").strip() if command.context_type else ""
    context_label = (
        _holding_context_label(investor_user_id=investor_user_id, holding_id=context_id)
        if command.context_type == "holding"
        else ""
    )
    fingerprint = _fingerprint(
        {
            "kind": kind,
            "topic": topic,
            "message": message,
            "context_type": command.context_type,
            "context_id": context_id,
        }
    )
    existing = _existing_for_key(idempotency_key, fingerprint)
    if existing is not None:
        return existing
    limits = _rate_limits(kind=kind, investor_user_id=investor_user_id)
    wait = window_wait_seconds(SUPPORT_REQUEST_SCOPE, limits)
    if wait is not None:
        raise SupportRequestThrottled(wait)
    try:
        with transaction.atomic():
            request = InvestorSupportRequest.objects.create(
                reference=_allocate_reference(kind),
                kind=kind,
                investor_user_id=actor.pk,
                investor_email=str(actor.email).strip().lower(),
                investor_reference=str(getattr(actor, "investor_reference", "") or ""),
                topic=topic,
                message=message,
                context_type=command.context_type,
                context_id=context_id,
                context_label=context_label,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
            )
            support_message = enqueue_outbox_message(
                OutboxCommand(
                    idempotency_key=f"support-request:{request.id}:team",
                    topic=SUPPORT_REQUEST_EMAIL_TOPIC,
                    payload=_support_email_payload(request),
                )
            )
            receipt_message = enqueue_outbox_message(
                OutboxCommand(
                    idempotency_key=f"support-request:{request.id}:receipt",
                    topic=SUPPORT_REQUEST_RECEIPT_TOPIC,
                    payload=_receipt_email_payload(request),
                )
            )
            request.support_outbox_message = support_message
            request.receipt_outbox_message = receipt_message
            if closure:
                admin_ops = import_module("backend.apps.admin_ops.services")
                task = admin_ops.open_account_closure_request_task(
                    admin_ops.OpenAccountClosureRequestTaskCommand(
                        requested_by=actor,
                        support_request_id=str(request.id),
                        reference=request.reference,
                        investor_user_id=investor_user_id,
                        investor_label=str(getattr(actor, "full_name", "") or actor.email),
                        message=message,
                    )
                )
                request.admin_task_id = task.id
            request.save(
                update_fields=[
                    "support_outbox_message",
                    "receipt_outbox_message",
                    "admin_task_id",
                    "updated_at",
                ]
            )
    except IntegrityError:
        # A retry with the same key won the race: return its request.
        retried = _existing_for_key(idempotency_key, fingerprint)
        if retried is None:
            raise
        return retried
    record_window_hits(SUPPORT_REQUEST_SCOPE, limits)
    return request
