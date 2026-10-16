"""Public site newsletter "New projects by email": double opt-in, digest and cleanup.

A marketing list of people who are not necessarily users, kept apart from investor
notices: its emails use the ``marketing_email.`` topics, so they never appear in the
investor notification centre, and investor notices never depend on it (COMMS-DEC-009).

Link tokens are ``HMAC(key, purpose:subscription:nonce)`` with a key derived from the
server secret. Only the random nonce and the SHA-256 hash of the token are stored, so a
copy of the database alone cannot confirm or unsubscribe anyone; the live token is
rebuilt only when an email is rendered for the provider. Stored copies of the emails
(delivery records) carry "[redacted]" instead of the token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import secrets
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from backend.apps.communications.models import (
    NewsletterDigestDelivery,
    NewsletterDigestRun,
    NewsletterDigestRunStatus,
    NewsletterSource,
    NewsletterSubscription,
    NewsletterSubscriptionStatus,
)
from backend.apps.communications.public_forms import public_ip_hash
from backend.apps.communications.services import (
    NEWSLETTER_CONFIRMATION_EMAIL_TOPIC,
    NEWSLETTER_NEW_PROJECTS_EMAIL_TOPIC,
    REDACTED_SECRET,
    CommunicationsError,
    EmailButton,
    EmailListItem,
    EmailNotNeededError,
    EmailTemplateContent,
    RenderedEmail,
    _base_url,
    _render_banxum_email_html,
)
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message

logger = logging.getLogger(__name__)

# The consent the subscriber gave with the double opt-in (public site form text of
# 2026-10-15). Change the version when the wording changes.
NEWSLETTER_CONSENT_VERSION = "newsletter-new-projects-2026-10-15"
CONFIRMATION_TEMPLATE_KEY = "newsletter.confirmation.v1"
NEW_PROJECTS_TEMPLATE_KEY = "newsletter.new_projects.v1"
CONFIRM_TOKEN_LIFETIME = timedelta(days=7)
CONFIRMATION_RESEND_INTERVAL = timedelta(hours=1)
CONFIRMATION_DAILY_LIMIT = 3
ANONYMISE_UNSUBSCRIBED_AFTER = timedelta(days=30)
# The first run ever has no previous run: it looks back one day, so switching the job on
# does not email every project that is already open.
FIRST_RUN_LOOKBACK = timedelta(days=1)
ANNOUNCED_LOAN_LOOKBACK_DAYS = 180
OPEN_PROJECTS_SCAN_LIMIT = 500

TOKEN_PURPOSE_CONFIRM = "confirm"
TOKEN_PURPOSE_UNSUBSCRIBE = "unsubscribe"
TOKEN_RE = re.compile(r"\A[A-Za-z0-9_-]{20,128}\Z")


class NewsletterError(CommunicationsError):
    pass


class NewsletterTokenError(NewsletterError):
    """The link is not valid (unknown, malformed or expired)."""


@dataclass(frozen=True, slots=True)
class SubscribeNewsletterCommand:
    email: str
    source: str = NewsletterSource.OTHER
    ip_address: str = ""


@dataclass(frozen=True, slots=True)
class SubscribeNewsletterResult:
    confirmation_queued: bool


@dataclass(frozen=True, slots=True)
class NewsletterDigestResult:
    run_id: str
    run_date: date
    window_start: datetime
    window_end: datetime
    project_count: int
    queued_count: int
    already_completed: bool
    resumed_run_dates: tuple[date, ...] = ()


# --- Tokens -------------------------------------------------------------------------------


def _token_key() -> bytes:
    return hashlib.sha256(
        f"{settings.SECRET_KEY}:communications-newsletter-token:v1".encode()
    ).digest()


def _new_nonce() -> str:
    return secrets.token_hex(16)


def newsletter_token(purpose: str, subscription_id: uuid.UUID | str, nonce: str) -> str:
    message = f"{purpose}:{subscription_id}:{nonce}".encode()
    digest = hmac.new(_token_key(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _presented_token_hash(token: object) -> str:
    if not isinstance(token, str) or not TOKEN_RE.match(token):
        raise NewsletterTokenError("This link is not valid or has expired.")
    return token_hash(token)


def _issue_confirm_token(subscription: NewsletterSubscription, *, now: datetime) -> None:
    """Give the subscription a valid confirmation link for 7 more days.

    A link that has not expired is kept (so the first email still works after a re-send);
    an expired one is replaced.
    """

    expired = (
        subscription.confirm_token_expires_at is None
        or subscription.confirm_token_expires_at <= now
    )
    if not subscription.confirm_token_nonce or expired:
        subscription.confirm_token_nonce = _new_nonce()
    subscription.confirm_token_hash = token_hash(
        newsletter_token(TOKEN_PURPOSE_CONFIRM, subscription.id, subscription.confirm_token_nonce)
    )
    subscription.confirm_token_expires_at = now + CONFIRM_TOKEN_LIFETIME


def _issue_unsubscribe_token(subscription: NewsletterSubscription) -> None:
    subscription.unsubscribe_token_nonce = _new_nonce()
    subscription.unsubscribe_token_hash = token_hash(
        newsletter_token(
            TOKEN_PURPOSE_UNSUBSCRIBE, subscription.id, subscription.unsubscribe_token_nonce
        )
    )


def _live_token(subscription: NewsletterSubscription, purpose: str) -> str:
    """Rebuild a link token for the provider copy.

    If the stored hash no longer matches, the server key was rotated: the hash is renewed
    for the current key so this and later emails work (links in emails sent before the
    rotation stop working), instead of failing every newsletter email from then on.
    """

    if purpose == TOKEN_PURPOSE_CONFIRM:
        nonce, stored_hash = subscription.confirm_token_nonce, subscription.confirm_token_hash
        hash_field = "confirm_token_hash"
    else:
        nonce = subscription.unsubscribe_token_nonce
        stored_hash = subscription.unsubscribe_token_hash
        hash_field = "unsubscribe_token_hash"
    if not nonce or not stored_hash:
        raise NewsletterError("The subscription has no link token to send.")
    token = newsletter_token(purpose, subscription.id, nonce)
    current_hash = token_hash(token)
    if not hmac.compare_digest(current_hash, stored_hash):
        logger.warning(
            "Newsletter %s link of subscription %s renewed after a server key change.",
            purpose,
            subscription.id,
        )
        setattr(subscription, hash_field, current_hash)
        subscription.save(update_fields=[hash_field, "updated_at"])
    return token


# --- Subscribe, confirm, unsubscribe --------------------------------------------------------


def _confirmation_idempotency_prefix(subscription: NewsletterSubscription) -> str:
    return f"newsletter-confirmation:{subscription.id}:"


def _may_send_confirmation(subscription: NewsletterSubscription, *, now: datetime) -> bool:
    """At most one confirmation email an hour and three in 24 hours per address."""

    if (
        subscription.confirmation_sent_at is not None
        and now - subscription.confirmation_sent_at < CONFIRMATION_RESEND_INTERVAL
    ):
        return False
    sent_last_day = OutboxMessage.objects.filter(
        topic=NEWSLETTER_CONFIRMATION_EMAIL_TOPIC,
        idempotency_key__startswith=_confirmation_idempotency_prefix(subscription),
        created_at__gte=now - timedelta(days=1),
    ).count()
    return sent_last_day < CONFIRMATION_DAILY_LIMIT


def _queue_confirmation_email(subscription: NewsletterSubscription) -> OutboxMessage:
    return enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=(f"{_confirmation_idempotency_prefix(subscription)}{uuid.uuid4().hex}"),
            topic=NEWSLETTER_CONFIRMATION_EMAIL_TOPIC,
            # No address and no token in the queue: both are read at send time.
            payload={
                "subscription_id": str(subscription.id),
                "template_key": CONFIRMATION_TEMPLATE_KEY,
            },
        )
    )


@transaction.atomic
def subscribe_to_newsletter(command: SubscribeNewsletterCommand) -> SubscribeNewsletterResult:
    """Start (or repeat) the double opt-in. The caller always answers the same way.

    - new address: pending row and a confirmation email;
    - pending: the confirmation again, at most once an hour and three times a day;
    - confirmed: nothing;
    - unsubscribed: a new double opt-in with new links (same send limits).
    """

    email = command.email.strip().lower()
    source = command.source if command.source in NewsletterSource.values else NewsletterSource.OTHER
    now = now_utc()
    subscription = NewsletterSubscription.objects.select_for_update().filter(email=email).first()
    if subscription is None:
        try:
            with transaction.atomic():
                subscription = NewsletterSubscription(
                    email=email,
                    status=NewsletterSubscriptionStatus.PENDING,
                    source=source,
                    consent_version=NEWSLETTER_CONSENT_VERSION,
                    ip_hash=public_ip_hash(command.ip_address),
                )
                _issue_unsubscribe_token(subscription)
                _issue_confirm_token(subscription, now=now)
                subscription.save()
        except IntegrityError:
            subscription = NewsletterSubscription.objects.select_for_update().get(email=email)

    if subscription.status == NewsletterSubscriptionStatus.CONFIRMED:
        return SubscribeNewsletterResult(confirmation_queued=False)
    if not _may_send_confirmation(subscription, now=now):
        return SubscribeNewsletterResult(confirmation_queued=False)

    if subscription.status == NewsletterSubscriptionStatus.UNSUBSCRIBED:
        subscription.status = NewsletterSubscriptionStatus.PENDING
        subscription.source = source
        subscription.consent_version = NEWSLETTER_CONSENT_VERSION
        subscription.confirmed_at = None
        subscription.unsubscribed_at = None
        subscription.confirm_token_nonce = ""
        _issue_unsubscribe_token(subscription)
    subscription.ip_hash = public_ip_hash(command.ip_address) or subscription.ip_hash
    _issue_confirm_token(subscription, now=now)
    subscription.confirmation_sent_at = now
    subscription.save()
    _queue_confirmation_email(subscription)
    return SubscribeNewsletterResult(confirmation_queued=True)


@transaction.atomic
def confirm_newsletter_subscription(token: object) -> NewsletterSubscription:
    """Confirm with the emailed link. Confirming twice is fine; expired links fail."""

    digest = _presented_token_hash(token)
    subscription = (
        NewsletterSubscription.objects.select_for_update()
        .filter(confirm_token_hash=digest, email__isnull=False)
        .first()
    )
    if subscription is None:
        raise NewsletterTokenError("This link is not valid or has expired.")
    if subscription.status == NewsletterSubscriptionStatus.CONFIRMED:
        return subscription
    now = now_utc()
    if (
        subscription.status != NewsletterSubscriptionStatus.PENDING
        or subscription.confirm_token_expires_at is None
        or subscription.confirm_token_expires_at <= now
    ):
        raise NewsletterTokenError("This link is not valid or has expired.")
    subscription.status = NewsletterSubscriptionStatus.CONFIRMED
    subscription.confirmed_at = now
    subscription.save(update_fields=["status", "confirmed_at", "updated_at"])
    return subscription


@transaction.atomic
def unsubscribe_from_newsletter(token: object) -> NewsletterSubscription:
    """Unsubscribe with the link of any newsletter email. Repeating it is a no-op."""

    digest = _presented_token_hash(token)
    subscription = (
        NewsletterSubscription.objects.select_for_update()
        .filter(unsubscribe_token_hash=digest)
        .first()
    )
    if subscription is None:
        raise NewsletterTokenError("This link is not valid or has expired.")
    if subscription.status != NewsletterSubscriptionStatus.UNSUBSCRIBED:
        subscription.status = NewsletterSubscriptionStatus.UNSUBSCRIBED
        subscription.unsubscribed_at = now_utc()
        subscription.confirm_token_nonce = ""
        subscription.confirm_token_hash = ""
        subscription.confirm_token_expires_at = None
        subscription.save(
            update_fields=[
                "status",
                "unsubscribed_at",
                "confirm_token_nonce",
                "confirm_token_hash",
                "confirm_token_expires_at",
                "updated_at",
            ]
        )
    return subscription


# --- Emails ---------------------------------------------------------------------------------


def _link(path: str, token: str) -> str:
    return f"{_base_url()}{path}?token={urllib.parse.quote(token, safe='')}"


def _one_click_unsubscribe_url(token: str) -> str:
    """Backend endpoint for RFC 8058 one-click unsubscribe (List-Unsubscribe header)."""

    path = reverse("public-newsletter-unsubscribe")
    return f"{_base_url()}{path}?token={urllib.parse.quote(token, safe='')}"


def _support_email() -> str:
    return str(getattr(settings, "SUPPORT_EMAIL", "") or "support@banxum.com")


def _newsletter_footer(unsubscribe_url: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    platform = str(settings.PLATFORM_BRAND_NAME)
    note = (
        f"You receive this email because this address asked for new {platform} projects by "
        "email on our website. It is not an account notice. You can unsubscribe at any time."
    )
    links = (
        ("Website", _base_url()),
        ("Unsubscribe", unsubscribe_url),
        (_support_email(), f"mailto:{_support_email()}"),
    )
    return note, links


def _rate_label(rate_bps: int) -> str:
    percent = (Decimal(rate_bps) / Decimal(100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return f"{percent}%"


def _term_label(term_months: int) -> str:
    return "1 month" if term_months == 1 else f"{term_months} months"


def _project_detail(project: dict[str, Any]) -> str:
    rate = _rate_label(int(project.get("interest_rate_bps") or 0))
    term = _term_label(int(project.get("term_months") or 0))
    return f"{rate} a year · {term} · {project.get('currency', '')}"


def _project_url(project: dict[str, Any]) -> str:
    loan_id = urllib.parse.quote(str(project.get("loan_id", "")), safe="")
    return f"{_base_url()}/projects/{loan_id}"


def _subscription_for_email(message: OutboxMessage) -> NewsletterSubscription:
    subscription_id = str(message.payload.get("subscription_id", "")).strip()
    try:
        subscription = NewsletterSubscription.objects.filter(id=subscription_id).first()
    except (ValueError, DjangoValidationError):
        # A malformed id is the same as a missing row.
        subscription = None
    if subscription is None or not subscription.email:
        raise EmailNotNeededError("The newsletter subscription no longer exists.")
    return subscription


def _render_confirmation_email(
    subscription: NewsletterSubscription, *, redact: bool
) -> RenderedEmail:
    now = now_utc()
    if (
        subscription.status != NewsletterSubscriptionStatus.PENDING
        or subscription.confirm_token_expires_at is None
        or subscription.confirm_token_expires_at <= now
    ):
        raise EmailNotNeededError("The subscription is no longer waiting for confirmation.")
    confirm_token = REDACTED_SECRET if redact else _live_token(subscription, TOKEN_PURPOSE_CONFIRM)
    unsubscribe_token = (
        REDACTED_SECRET if redact else _live_token(subscription, TOKEN_PURPOSE_UNSUBSCRIBE)
    )
    confirm_url = _link("/newsletter/confirm", confirm_token)
    unsubscribe_url = _link("/newsletter/unsubscribe", unsubscribe_token)
    platform = str(settings.PLATFORM_BRAND_NAME)
    intro = (
        "You asked to get new projects by email. Once or twice a month, when new projects "
        "open. If you did not ask for this, ignore this email."
    )
    unsubscribe_note = "You can unsubscribe at any time with the link at the end of every email."
    footer_note, footer_links = _newsletter_footer(unsubscribe_url)
    body_text = (
        "Confirm your email address\n\n"
        f"{intro}\n\n"
        f"Confirm my subscription: {confirm_url}\n\n"
        "The link works for 7 days.\n\n"
        f"{unsubscribe_note}\n"
        f"Unsubscribe: {unsubscribe_url}\n\n"
        f"{platform} is operated by {settings.LEGAL_OPERATOR_NAME}."
    )
    return RenderedEmail(
        recipient_email=str(subscription.email),
        subject="Confirm your email address",
        body_text=body_text,
        body_html=_render_banxum_email_html(
            EmailTemplateContent(
                notice_label="New projects by email",
                preheader="Confirm your email address to get new projects by email.",
                status_label="Action needed",
                status_tone="warning",
                headline="Confirm your email address",
                paragraphs=(intro,),
                buttons=(EmailButton("Confirm my subscription", confirm_url),),
                fine_print=(
                    "The link works for 7 days. If the button does not work, copy this link "
                    f"into your browser: {confirm_url}. {unsubscribe_note}"
                ),
                footer_note=footer_note,
                footer_links=footer_links,
            )
        ),
        template_key=CONFIRMATION_TEMPLATE_KEY,
        metadata={
            "newsletter_subscription_id": str(subscription.id),
            "tokens_redacted_in_record": redact,
        },
    )


def _render_new_projects_email(
    subscription: NewsletterSubscription, message: OutboxMessage, *, redact: bool
) -> RenderedEmail:
    if subscription.status != NewsletterSubscriptionStatus.CONFIRMED:
        raise EmailNotNeededError("The subscriber is no longer subscribed.")
    run_id = str(message.payload.get("run_id", "")).strip()
    run = NewsletterDigestRun.objects.filter(id=run_id).first() if run_id else None
    projects = [project for project in (run.projects if run else []) if isinstance(project, dict)]
    if not projects:
        raise EmailNotNeededError("The new-projects run has no projects.")
    unsubscribe_token = (
        REDACTED_SECRET if redact else _live_token(subscription, TOKEN_PURPOSE_UNSUBSCRIBE)
    )
    unsubscribe_url = _link("/newsletter/unsubscribe", unsubscribe_token)
    one_click_url = _one_click_unsubscribe_url(unsubscribe_token)
    platform = str(settings.PLATFORM_BRAND_NAME)
    count = len(projects)
    subject = (
        f"A new project is open on {platform}"
        if count == 1
        else f"{count} new projects are open on {platform}"
    )
    headline = "A new project is open" if count == 1 else "New projects are open"
    intro = (
        "This project opened since our last email."
        if count == 1
        else "These projects opened since our last email."
    )
    risk_note = (
        "Lending carries risks, including the loss of the money you lend. This email is "
        "information about new projects, not investment advice."
    )
    projects_url = f"{_base_url()}/projects"
    items = tuple(
        EmailListItem(
            title=str(project.get("title", "")),
            detail=_project_detail(project),
            url=_project_url(project),
            link_label="View project",
        )
        for project in projects
    )
    footer_note, footer_links = _newsletter_footer(unsubscribe_url)
    project_lines = "\n\n".join(f"{item.title}\n{item.detail}\n{item.url}" for item in items)
    body_text = (
        f"{headline}\n\n{intro}\n\n{project_lines}\n\n"
        f"See all projects: {projects_url}\n\n"
        f"{risk_note}\n\n"
        f"Unsubscribe: {unsubscribe_url}\n\n"
        f"{platform} is operated by {settings.LEGAL_OPERATOR_NAME}."
    )
    return RenderedEmail(
        recipient_email=str(subscription.email),
        subject=subject,
        body_text=body_text,
        body_html=_render_banxum_email_html(
            EmailTemplateContent(
                notice_label="New projects by email",
                preheader=f"{items[0].title}: {items[0].detail}",
                status_label="New projects" if count > 1 else "New project",
                status_tone="info",
                headline=headline,
                paragraphs=(intro,),
                items=items,
                buttons=(EmailButton("See all projects", projects_url),),
                fine_print=f"{risk_note} You can unsubscribe in one click below.",
                footer_note=footer_note,
                footer_links=footer_links,
            )
        ),
        template_key=NEW_PROJECTS_TEMPLATE_KEY,
        metadata={
            "newsletter_subscription_id": str(subscription.id),
            "newsletter_digest_run_id": str(run.id) if run else "",
            "loan_ids": [str(project.get("loan_id", "")) for project in projects],
            "list_unsubscribe": True,
            "tokens_redacted_in_record": redact,
        },
        headers=(
            ("List-Unsubscribe", f"<{one_click_url}>"),
            ("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"),
        ),
    )


def render_newsletter_email(message: OutboxMessage, *, redact: bool) -> RenderedEmail:
    subscription = _subscription_for_email(message)
    if message.topic == NEWSLETTER_CONFIRMATION_EMAIL_TOPIC:
        return _render_confirmation_email(subscription, redact=redact)
    if message.topic == NEWSLETTER_NEW_PROJECTS_EMAIL_TOPIC:
        return _render_new_projects_email(subscription, message, redact=redact)
    raise NewsletterError(f"Unknown newsletter email topic '{message.topic}'.")


# --- New-projects digest (scheduled job) ---------------------------------------------------


def _marketplace_services() -> Any:
    return import_module("backend.apps.marketplace_primary.services")


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _recently_announced_loan_ids(run_date: date) -> set[str]:
    since = run_date - timedelta(days=ANNOUNCED_LOAN_LOOKBACK_DAYS)
    announced: set[str] = set()
    for projects in NewsletterDigestRun.objects.filter(run_date__gte=since).values_list(
        "projects", flat=True
    ):
        for project in projects or []:
            if isinstance(project, dict) and project.get("loan_id"):
                announced.add(str(project["loan_id"]))
    return announced


def new_public_projects(
    *, window_start: datetime, window_end: datetime, exclude_loan_ids: set[str]
) -> list[dict[str, Any]]:
    """Open public projects first published in (window_start, window_end].

    Uses the investor marketplace's open-loan selector (published, capacity left) and its
    deadline, so a project is announced only while a visitor can still invest. Only the
    title, rate, term and currency are kept: never the borrower.
    """

    marketplace = _marketplace_services()
    today = business_date(window_end)
    rows = [
        row
        for row in marketplace.list_open_marketplace_loans(limit=OPEN_PROJECTS_SCAN_LIMIT)
        if marketplace.marketplace_payload_has_capacity(row)
    ]
    loan_ids = [str(row.get("loan_id", "")) for row in rows if row.get("loan_id")]
    loan_model = apps.get_model("loans", "Loan")
    published_at_by_id = {
        str(loan_id): published_at
        for loan_id, published_at in loan_model.objects.filter(id__in=loan_ids).values_list(
            "id", "published_at"
        )
    }
    projects: list[dict[str, Any]] = []
    for row in rows:
        loan_id = str(row.get("loan_id", ""))
        published_at = published_at_by_id.get(loan_id)
        if published_at is None or not (window_start < published_at <= window_end):
            continue
        if loan_id in exclude_loan_ids:
            continue
        deadline = _as_date(row.get("funding_deadline"))
        if deadline is not None and deadline < today:
            continue
        projects.append(
            {
                "loan_id": loan_id,
                "title": str(row.get("title") or ""),
                "interest_rate_bps": int(row.get("yield_bps") or row.get("interest_rate_bps") or 0),
                "term_months": int(row.get("term_months") or 0),
                "currency": str(row.get("currency") or ""),
                "published_at": published_at.isoformat(),
            }
        )
    projects.sort(key=lambda project: (project["published_at"], project["title"]))
    return projects


def _open_digest_run(*, run_date: date, as_of: datetime) -> NewsletterDigestRun:
    existing = NewsletterDigestRun.objects.filter(run_date=run_date).first()
    if existing is not None:
        return existing
    previous = (
        NewsletterDigestRun.objects.filter(run_date__lt=run_date).order_by("-run_date").first()
    )
    window_start = previous.window_end if previous is not None else as_of - FIRST_RUN_LOOKBACK
    window_start = min(window_start, as_of)
    projects = new_public_projects(
        window_start=window_start,
        window_end=as_of,
        exclude_loan_ids=_recently_announced_loan_ids(run_date),
    )
    try:
        with transaction.atomic():
            return NewsletterDigestRun.objects.create(
                run_date=run_date,
                window_start=window_start,
                window_end=as_of,
                projects=projects,
            )
    except IntegrityError:
        return NewsletterDigestRun.objects.get(run_date=run_date)


def _queue_digest_email(run: NewsletterDigestRun, subscription_id: uuid.UUID) -> bool:
    with transaction.atomic():
        subscription = (
            NewsletterSubscription.objects.select_for_update()
            .filter(
                id=subscription_id,
                status=NewsletterSubscriptionStatus.CONFIRMED,
                email__isnull=False,
            )
            .first()
        )
        if subscription is None:
            return False
        if NewsletterDigestDelivery.objects.filter(run=run, subscription=subscription).exists():
            return False
        message = enqueue_outbox_message(
            OutboxCommand(
                idempotency_key=f"newsletter-digest:{run.id}:{subscription.id}",
                topic=NEWSLETTER_NEW_PROJECTS_EMAIL_TOPIC,
                payload={
                    "subscription_id": str(subscription.id),
                    "run_id": str(run.id),
                    "template_key": NEW_PROJECTS_TEMPLATE_KEY,
                },
            )
        )
        NewsletterDigestDelivery.objects.create(
            run=run, subscription=subscription, outbox_message=message
        )
    return True


def _finish_digest_run(run: NewsletterDigestRun) -> int:
    """Queue the run's email for every confirmed subscriber not yet served. Idempotent."""

    queued = 0
    if run.projects:
        pending_ids = list(
            NewsletterSubscription.objects.filter(
                status=NewsletterSubscriptionStatus.CONFIRMED,
                email__isnull=False,
            )
            .exclude(digest_deliveries__run=run)
            .order_by("confirmed_at", "id")
            .values_list("id", flat=True)
        )
        for subscription_id in pending_ids:
            if _queue_digest_email(run, subscription_id):
                queued += 1
    run.status = NewsletterDigestRunStatus.COMPLETED
    run.recipient_count = NewsletterDigestDelivery.objects.filter(run=run).count()
    run.completed_at = now_utc()
    run.save(update_fields=["status", "recipient_count", "completed_at", "updated_at"])
    return queued


def run_newsletter_new_projects_digest(*, as_of: datetime) -> NewsletterDigestResult:
    """Daily job: one email per confirmed subscriber listing projects opened since the last run.

    No new projects, no email. A run is keyed by its Europe/Zurich date; repeating it is a
    no-op, and a run interrupted on an earlier day is finished first.
    """

    run_date = business_date(as_of)
    resumed: list[date] = []
    for unfinished in NewsletterDigestRun.objects.filter(
        status=NewsletterDigestRunStatus.RUNNING, run_date__lt=run_date
    ).order_by("run_date"):
        _finish_digest_run(unfinished)
        resumed.append(unfinished.run_date)
    run = _open_digest_run(run_date=run_date, as_of=as_of)
    if run.status == NewsletterDigestRunStatus.COMPLETED:
        return NewsletterDigestResult(
            run_id=str(run.id),
            run_date=run.run_date,
            window_start=run.window_start,
            window_end=run.window_end,
            project_count=len(run.projects or []),
            queued_count=0,
            already_completed=True,
            resumed_run_dates=tuple(resumed),
        )
    queued = _finish_digest_run(run)
    return NewsletterDigestResult(
        run_id=str(run.id),
        run_date=run.run_date,
        window_start=run.window_start,
        window_end=run.window_end,
        project_count=len(run.projects or []),
        queued_count=queued,
        already_completed=False,
        resumed_run_dates=tuple(resumed),
    )


# --- Retention ------------------------------------------------------------------------------


def anonymise_old_newsletter_subscriptions(*, as_of: datetime) -> dict[str, int]:
    """Clear personal data of rows unsubscribed, or left unconfirmed, for over 30 days.

    The unsubscribe hash of an unsubscribed row is kept (it is not personal data), so a
    late click on an old unsubscribe link still answers "unsubscribed".
    """

    cutoff = as_of - ANONYMISE_UNSUBSCRIBED_AFTER
    now = now_utc()
    cleared = {
        "email": None,
        "ip_hash": "",
        "confirm_token_nonce": "",
        "confirm_token_hash": "",
        "confirm_token_expires_at": None,
        "unsubscribe_token_nonce": "",
        "anonymised_at": now,
        "updated_at": now,
    }
    unsubscribed = NewsletterSubscription.objects.filter(
        status=NewsletterSubscriptionStatus.UNSUBSCRIBED,
        unsubscribed_at__lt=cutoff,
        anonymised_at__isnull=True,
    ).update(**cleared)
    # Never confirmed: the link expired over 30 days ago, so no consent was ever given.
    unconfirmed = NewsletterSubscription.objects.filter(
        status=NewsletterSubscriptionStatus.PENDING,
        confirm_token_expires_at__lt=cutoff,
        anonymised_at__isnull=True,
    ).update(**{**cleared, "unsubscribe_token_hash": ""})
    if unsubscribed or unconfirmed:
        logger.info(
            "Anonymised %s unsubscribed and %s unconfirmed newsletter subscriptions.",
            unsubscribed,
            unconfirmed,
        )
    return {
        "unsubscribed_anonymised": int(unsubscribed),
        "unconfirmed_anonymised": int(unconfirmed),
    }
