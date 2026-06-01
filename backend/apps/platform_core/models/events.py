from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class DomainEvent(AppendOnlyModel):
    occurred_at = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=128)
    aggregate_type = models.CharField(max_length=128)
    aggregate_id = models.CharField(max_length=128)
    schema_version = models.PositiveSmallIntegerField(default=1)
    idempotency_key = models.CharField(max_length=160, unique=True, null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["aggregate_type", "aggregate_id"]),
        ]


class OutboxStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    PROCESSED = "processed", "Processed"
    DEAD_LETTER = "dead_letter", "Dead letter"


class OutboxMessage(TimestampedModel):
    idempotency_key = models.CharField(max_length=160, unique=True)
    topic = models.CharField(max_length=128)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=32,
        choices=OutboxStatus.choices,
        default=OutboxStatus.PENDING,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"]),
            models.Index(fields=["topic", "status"]),
        ]
