from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import (
    AppendOnlyModel,
    PlatformDateTimeField,
    TimestampedModel,
)


class EmailDeliveryStatus(models.TextChoices):
    RENDERED = "rendered", "Rendered"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class CommunicationEventType(models.TextChoices):
    EMAIL_SENT = "email_sent", "Email sent"
    EMAIL_FAILED = "email_failed", "Email failed"


class EmailDeliveryRecord(AppendOnlyModel):
    outbox_message = models.ForeignKey(
        "platform_core.OutboxMessage",
        on_delete=models.PROTECT,
        related_name="email_delivery_records",
    )
    topic = models.CharField(max_length=128)
    template_key = models.CharField(max_length=128)
    recipient_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    provider = models.CharField(max_length=64)
    provider_message_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=EmailDeliveryStatus.choices)
    attempt_number = models.PositiveSmallIntegerField()
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = PlatformDateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["outbox_message", "attempt_number"],
                name="unique_email_delivery_attempt",
            )
        ]
        indexes = [
            models.Index(fields=["topic", "created_at"]),
            models.Index(fields=["recipient_email", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["provider", "provider_message_id"]),
        ]


class CommunicationEvent(AppendOnlyModel):
    event_type = models.CharField(max_length=64, choices=CommunicationEventType.choices)
    outbox_message = models.ForeignKey(
        "platform_core.OutboxMessage",
        on_delete=models.PROTECT,
        related_name="communication_events",
        null=True,
        blank=True,
    )
    email_delivery_record = models.ForeignKey(
        EmailDeliveryRecord,
        on_delete=models.PROTECT,
        related_name="communication_events",
        null=True,
        blank=True,
    )
    occurred_at = PlatformDateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["event_type", "occurred_at"]),
        ]


class NotificationReadReceipt(AppendOnlyModel):
    """An investor marked one portal notification as read.

    Keyed by the outbox message so the read state survives the notification moving from
    "queued" to "delivered". One receipt per investor and message; never updated.
    """

    investor_user_id = models.UUIDField()
    outbox_message = models.ForeignKey(
        "platform_core.OutboxMessage",
        on_delete=models.PROTECT,
        related_name="notification_read_receipts",
    )
    read_at = PlatformDateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-read_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["investor_user_id", "outbox_message"],
                name="unique_notification_read_receipt",
            )
        ]
        indexes = [
            models.Index(fields=["investor_user_id", "read_at"]),
        ]


# --- Public site: forms and newsletter (COMMS-DEC-009) ------------------------------------


class PublicEnquiryKind(models.TextChoices):
    COMPANY = "company", "Company application"
    ORIGINATOR = "originator", "Loan originator request"
    CONTACT = "contact", "Contact message"


class PublicEnquiryDeliveryStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    RETRYING = "retrying", "Retrying"
    FAILED = "failed", "Failed"


class PublicEnquiry(TimestampedModel):
    """One accepted public-site form, emailed once to ``PUBLIC_ENQUIRY_EMAIL``.

    Kept for 24 months, then deleted by the public-site retention job. The IP is stored
    only as a keyed SHA-256 hash.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=PublicEnquiryKind.choices)
    reference = models.CharField(max_length=32, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    sender_email = models.EmailField(max_length=254)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    delivery_status = models.CharField(
        max_length=32,
        choices=PublicEnquiryDeliveryStatus.choices,
        default=PublicEnquiryDeliveryStatus.QUEUED,
    )
    outbox_message = models.ForeignKey(
        "platform_core.OutboxMessage",
        on_delete=models.SET_NULL,
        related_name="public_enquiries",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["kind", "created_at"]),
        ]


class PublicEnquiryReferenceCounter(models.Model):
    """Last reference number per prefix (APP, PAR, MSG) and year."""

    prefix = models.CharField(max_length=8)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["prefix", "year"],
                name="unique_public_enquiry_reference_counter",
            )
        ]


class NewsletterSubscriptionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    UNSUBSCRIBED = "unsubscribed", "Unsubscribed"


class NewsletterSource(models.TextChoices):
    HOME = "home", "Home"
    PROJECTS = "projects", "Projects"
    GUIDES = "guides", "Guides"
    OTHER = "other", "Other"


class NewsletterSubscription(TimestampedModel):
    """A public-site "New projects by email" subscription with double opt-in.

    Marketing list of non-users, separate from investor notices. Links carry a token
    that is an HMAC of a random per-subscription nonce under a key derived from the
    server secret; the database keeps only the nonce and the SHA-256 hash of the token,
    so database contents alone never yield a working link. Unsubscribed rows are
    anonymised 30 days after unsubscribing (``email`` cleared); the unsubscribe hash is
    kept so a late click on an old link still answers "unsubscribed".
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=NewsletterSubscriptionStatus.choices,
        default=NewsletterSubscriptionStatus.PENDING,
    )
    source = models.CharField(
        max_length=32,
        choices=NewsletterSource.choices,
        default=NewsletterSource.OTHER,
    )
    consent_version = models.CharField(max_length=64)
    ip_hash = models.CharField(max_length=64, blank=True)
    confirm_token_nonce = models.CharField(max_length=64, blank=True)
    confirm_token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    confirm_token_expires_at = models.DateTimeField(null=True, blank=True)
    unsubscribe_token_nonce = models.CharField(max_length=64, blank=True)
    unsubscribe_token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    anonymised_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "confirmed_at"]),
            models.Index(fields=["status", "unsubscribed_at"]),
        ]


class NewsletterDigestRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"


class NewsletterDigestRun(TimestampedModel):
    """One daily "new projects" run: the window it covered and the projects it found."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_date = models.DateField(unique=True)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    projects = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=32,
        choices=NewsletterDigestRunStatus.choices,
        default=NewsletterDigestRunStatus.RUNNING,
    )
    recipient_count = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-run_date"]


class NewsletterDigestDelivery(AppendOnlyModel):
    """The new-projects email queued for one subscriber in one run (at most one)."""

    run = models.ForeignKey(
        NewsletterDigestRun,
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    subscription = models.ForeignKey(
        NewsletterSubscription,
        on_delete=models.PROTECT,
        related_name="digest_deliveries",
    )
    outbox_message = models.ForeignKey(
        "platform_core.OutboxMessage",
        on_delete=models.PROTECT,
        related_name="newsletter_digest_deliveries",
    )
    created_at = PlatformDateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "subscription"],
                name="unique_newsletter_digest_delivery",
            )
        ]
