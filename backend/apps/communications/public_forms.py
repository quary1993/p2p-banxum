"""Public site forms: one email per accepted form to ``PUBLIC_ENQUIRY_EMAIL`` (COMMS-DEC-009).

The For borrowers, For loan originators and Contact forms of the public site are stored as
``PublicEnquiry`` rows and emailed through the normal outbox, so the usual retry, delivery
record and evidence machinery applies. Nothing is sent to the person who filled the form.
Input is validated by the API serializers; this module stores, numbers and renders.
"""

from __future__ import annotations

import calendar
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F

from backend.apps.communications.models import (
    EmailDeliveryRecord,
    EmailDeliveryStatus,
    PublicEnquiry,
    PublicEnquiryDeliveryStatus,
    PublicEnquiryKind,
    PublicEnquiryReferenceCounter,
)
from backend.apps.communications.services import (
    PUBLIC_ENQUIRY_EMAIL_TOPIC,
    REDACTED_SECRET,
    CommunicationsError,
    EmailTemplateContent,
    RenderedEmail,
    _base_url,
    _email_time,
    _render_banxum_email_html,
)
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.models.events import OutboxStatus
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message

logger = logging.getLogger(__name__)

PUBLIC_ENQUIRY_TEMPLATE_KEY = "public_site.enquiry.v1"
USER_AGENT_MAX_LENGTH = 255
REFERENCE_PREFIXES: dict[str, str] = {
    PublicEnquiryKind.COMPANY: "APP",
    PublicEnquiryKind.ORIGINATOR: "PAR",
    PublicEnquiryKind.CONTACT: "MSG",
}
SUBJECT_TEXT: dict[str, str] = {
    PublicEnquiryKind.COMPANY: "New financing request",
    PublicEnquiryKind.ORIGINATOR: "New partnership request",
    PublicEnquiryKind.CONTACT: "New conversation request",
}
FORM_NAMES: dict[str, str] = {
    PublicEnquiryKind.COMPANY: "For borrowers",
    PublicEnquiryKind.ORIGINATOR: "For loan originators",
    PublicEnquiryKind.CONTACT: "Contact",
}
# Field order and labels in the email, per form (the U33 forms, 2026-11-09). The company form's
# currency is shown with the amount ("EUR 250,000.00"), not on its own row.
FIELD_LABELS: dict[str, tuple[tuple[str, str], ...]] = {
    PublicEnquiryKind.COMPANY: (
        ("company_name", "Company name"),
        ("country", "Country of registration"),
        ("amount", "Amount requested"),
        ("purpose", "Purpose of financing"),
        ("collateral", "Available collateral"),
        ("contact_name", "Name"),
        ("email", "Email"),
    ),
    PublicEnquiryKind.ORIGINATOR: (
        ("company_name", "Company name"),
        ("country", "Country of registration"),
        ("contact_name", "Name"),
        ("email", "Email"),
        ("proposal", "Proposal"),
        ("about", "Introduction"),
    ),
    PublicEnquiryKind.CONTACT: (
        ("name", "Full name"),
        ("email", "Email"),
        ("topic", "Topic"),
        ("message", "Message"),
    ),
}
# Fields shown with another one, never on their own row.
COMBINED_FIELDS = frozenset({"currency"})
# "revenue" and "loan_book" belong to enquiries sent with the October forms.
AMOUNT_FIELDS = frozenset({"amount", "revenue", "loan_book"})


class PublicEnquiryError(CommunicationsError):
    pass


@dataclass(frozen=True, slots=True)
class SubmitPublicEnquiryCommand:
    kind: str
    fields: dict[str, Any]
    ip_address: str = ""
    user_agent: str = ""


def public_ip_hash(ip_address: str) -> str:
    """Keyed SHA-256 of an IP: a pepper derived from SECRET_KEY, so it cannot be reversed
    by hashing the IPv4 space without the server secret."""

    if not ip_address:
        return ""
    pepper = hashlib.sha256(f"{settings.SECRET_KEY}:communications-public-ip:v1".encode()).digest()
    return hmac.new(pepper, ip_address.encode("utf-8"), hashlib.sha256).hexdigest()


def _reference_year() -> int:
    return business_date(now_utc()).year


def _format_reference(prefix: str, year: int, number: int) -> str:
    return f"{prefix}-{year}-{number:04d}"


def allocate_public_enquiry_reference(kind: str) -> str:
    """Next reference of the kind's prefix and year, e.g. APP-2026-0143.

    The counter row is raised with one UPDATE inside the caller's transaction, which locks
    the row until commit: two concurrent submissions never get the same number.
    """

    prefix = REFERENCE_PREFIXES[kind]
    year = _reference_year()
    with transaction.atomic():
        PublicEnquiryReferenceCounter.objects.get_or_create(prefix=prefix, year=year)
        PublicEnquiryReferenceCounter.objects.filter(prefix=prefix, year=year).update(
            last_number=F("last_number") + 1
        )
        number = PublicEnquiryReferenceCounter.objects.values_list("last_number", flat=True).get(
            prefix=prefix, year=year
        )
    return _format_reference(prefix, year, int(number))


def believable_fake_reference(kind: str) -> str:
    """A reference in the real format for a refused bot submission. Nothing is stored."""

    prefix = REFERENCE_PREFIXES.get(kind, REFERENCE_PREFIXES[PublicEnquiryKind.CONTACT])
    year = _reference_year()
    last = (
        PublicEnquiryReferenceCounter.objects.filter(prefix=prefix, year=year)
        .values_list("last_number", flat=True)
        .first()
    )
    return _format_reference(prefix, year, int(last or 0) + 1 + secrets.randbelow(3))


@transaction.atomic
def submit_public_enquiry(command: SubmitPublicEnquiryCommand) -> PublicEnquiry:
    """Store a validated form and queue its one email to ``PUBLIC_ENQUIRY_EMAIL``."""

    if command.kind not in REFERENCE_PREFIXES:
        raise PublicEnquiryError(f"Unknown enquiry kind '{command.kind}'.")
    sender_email = str(command.fields.get("email", "")).strip().lower()
    if not sender_email:
        raise PublicEnquiryError("The enquiry has no sender email.")
    reference = allocate_public_enquiry_reference(command.kind)
    enquiry = PublicEnquiry.objects.create(
        kind=command.kind,
        reference=reference,
        payload={"fields": command.fields},
        sender_email=sender_email,
        ip_hash=public_ip_hash(command.ip_address),
        user_agent=command.user_agent[:USER_AGENT_MAX_LENGTH],
    )
    message = enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"public-enquiry:{enquiry.id}",
            topic=PUBLIC_ENQUIRY_EMAIL_TOPIC,
            # Only references: the details are read from the enquiry row at send time, so
            # the 24-month deletion also removes them from the email queue.
            payload={
                "enquiry_id": str(enquiry.id),
                "reference": reference,
                "kind": command.kind,
                "template_key": PUBLIC_ENQUIRY_TEMPLATE_KEY,
            },
        )
    )
    enquiry.outbox_message = message
    enquiry.save(update_fields=["outbox_message", "updated_at"])
    return enquiry


def _format_amount(value: str) -> str:
    try:
        amount = Decimal(value)
    except ArithmeticError:
        return value
    return f"{amount:,.2f}"


def _display_value(name: str, value: Any, fields: dict[str, Any]) -> str:
    text = str(value)
    if name in AMOUNT_FIELDS and text:
        amount = _format_amount(text)
        currency = str(fields.get("currency") or "").strip() if name == "amount" else ""
        return f"{currency} {amount}" if currency else amount
    return text


def _field_rows(kind: str, fields: dict[str, Any]) -> list[tuple[str, str]]:
    """The labelled values of the form, in form order, empty ones left out.

    Values stored under names the current form no longer has (an enquiry sent with an earlier
    version of the form and still waiting for its email) follow with their name as the label,
    so nothing typed is ever dropped from the email.
    """

    labels = FIELD_LABELS[kind]
    known = {name for name, _label in labels}
    rows: list[tuple[str, str]] = []
    for name, label in labels:
        value = fields.get(name)
        if value is None or value == "":
            continue
        rows.append((label, _display_value(name, value, fields)))
    for name, value in fields.items():
        if name in known or name in COMBINED_FIELDS or value is None or value == "":
            continue
        rows.append((name.replace("_", " ").capitalize(), _display_value(name, value, fields)))
    return rows


def _safe_reply_to(address: str) -> str:
    """The sender address as Reply-To only if it is a single valid address (no CR/LF)."""

    if any(character in address for character in '\r\n\x00,;<>"') or len(address) > 254:
        return ""
    try:
        validate_email(address)
    except DjangoValidationError:
        return ""
    return address


def render_public_enquiry_email(message: OutboxMessage, *, redact: bool) -> RenderedEmail:
    """The email to BANXUM for one enquiry.

    ``redact=True`` builds the copy kept in the append-only delivery record: field values
    are replaced by "[redacted]" because the details belong to the enquiry row, which is
    deleted after 24 months. The subject is fixed text plus the reference only.
    """

    enquiry_id = str(message.payload.get("enquiry_id", "")).strip()
    enquiry = PublicEnquiry.objects.filter(id=enquiry_id).first() if enquiry_id else None
    if enquiry is None:
        raise PublicEnquiryError("The public enquiry of this email no longer exists.")
    recipient = str(settings.PUBLIC_ENQUIRY_EMAIL).strip().lower()
    if not recipient:
        raise PublicEnquiryError("PUBLIC_ENQUIRY_EMAIL is not configured.")
    kind = str(enquiry.kind)
    subject_text = SUBJECT_TEXT[kind]
    subject = f"{subject_text} {enquiry.reference}"
    fields: dict[str, Any] = dict((enquiry.payload or {}).get("fields") or {})

    field_rows = [
        (label, REDACTED_SECRET if redact else value) for label, value in _field_rows(kind, fields)
    ]
    received = _email_time(enquiry.created_at)
    data_rows: tuple[tuple[str, str], ...] = (
        ("Reference", enquiry.reference),
        ("Form", FORM_NAMES[kind]),
        ("Received", received),
        *field_rows,
        ("Consent", "Given on the form"),
    )
    platform = str(settings.PLATFORM_BRAND_NAME)
    sender = REDACTED_SECRET if redact else enquiry.sender_email
    intro = (
        f"Someone sent the {FORM_NAMES[kind]} form on the {platform} public site. "
        "The details are below, exactly as typed."
    )
    reply_line = (
        f"The sender's email address is {sender}. No email was sent to the sender, "
        "so please answer from your own mailbox."
    )
    text_lines = [
        f"{subject_text} {enquiry.reference}",
        "",
        intro,
        reply_line,
        "",
    ]
    for label, value in data_rows:
        if "\n" in value:
            indented = "\n".join(f"  {line}" for line in value.splitlines())
            text_lines.append(f"{label}:\n{indented}")
        else:
            text_lines.append(f"{label}: {value}")
    body_text = "\n".join(text_lines)
    reply_to = "" if redact else _safe_reply_to(enquiry.sender_email)
    return RenderedEmail(
        recipient_email=recipient,
        subject=subject,
        body_text=body_text,
        body_html=_render_banxum_email_html(
            EmailTemplateContent(
                notice_label="Public site form",
                preheader=f"{subject_text} {enquiry.reference} from the public site.",
                status_label="New enquiry",
                status_tone="warning",
                headline=subject_text,
                paragraphs=(intro, reply_line),
                data_rows=data_rows,
                plain_data_values=True,
                fine_print=(
                    "Internal email from the public site forms. Keep the reference when you "
                    "answer. The enquiry is kept for 24 months."
                ),
                footer_note=(
                    f"Internal notification for the {platform} team, sent by the public site."
                ),
                footer_links=(("Website", _base_url()),),
            )
        ),
        template_key=PUBLIC_ENQUIRY_TEMPLATE_KEY,
        metadata={
            "public_enquiry_id": str(enquiry.id),
            "reference": enquiry.reference,
            "kind": kind,
            "details_redacted_in_record": redact,
            "reply_to_requested": bool(_safe_reply_to(enquiry.sender_email)),
        },
        reply_to=reply_to,
    )


def record_public_enquiry_delivery(message: OutboxMessage, record: EmailDeliveryRecord) -> None:
    """Mirror the outbox outcome on the enquiry (sent, retrying or failed)."""

    if record.status == EmailDeliveryStatus.SENT:
        status = PublicEnquiryDeliveryStatus.SENT
    elif message.status == OutboxStatus.DEAD_LETTER:
        status = PublicEnquiryDeliveryStatus.FAILED
    else:
        status = PublicEnquiryDeliveryStatus.RETRYING
    PublicEnquiry.objects.filter(outbox_message=message).update(
        delivery_status=status, updated_at=now_utc()
    )


def months_before(value: datetime, months: int) -> datetime:
    """The same wall time ``months`` calendar months earlier (day clamped to month end)."""

    month_index = value.year * 12 + (value.month - 1) - months
    year, month_zero_based = divmod(month_index, 12)
    month = month_zero_based + 1
    last_day = calendar.monthrange(year, month)[1]
    return value.replace(year=year, month=month, day=min(value.day, last_day))


PUBLIC_ENQUIRY_RETENTION_MONTHS = 24


def delete_expired_public_enquiries(*, as_of: datetime) -> int:
    """Delete enquiries older than 24 months. Returns how many were deleted."""

    cutoff = months_before(as_of, PUBLIC_ENQUIRY_RETENTION_MONTHS)
    deleted, _per_model = PublicEnquiry.objects.filter(created_at__lt=cutoff).delete()
    if deleted:
        logger.info("Deleted %s public enquiries older than %s.", deleted, cutoff.isoformat())
    return int(deleted)
