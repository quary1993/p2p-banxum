from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel


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
    created_at = models.DateTimeField(auto_now_add=True)

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
    occurred_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["event_type", "occurred_at"]),
        ]
