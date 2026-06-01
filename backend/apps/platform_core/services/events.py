from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.utils import timezone

from backend.apps.platform_core.models import DomainEvent, OutboxMessage
from backend.apps.platform_core.models.events import OutboxStatus

RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=3),
    timedelta(hours=12),
    timedelta(days=1),
    timedelta(days=2),
)


@dataclass(frozen=True, slots=True)
class DomainEventCommand:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class OutboxCommand:
    idempotency_key: str
    topic: str
    payload: dict[str, Any] = field(default_factory=dict)


@transaction.atomic
def record_domain_event(command: DomainEventCommand) -> DomainEvent:
    if command.idempotency_key:
        existing = DomainEvent.objects.filter(idempotency_key=command.idempotency_key).first()
        if existing is not None:
            return cast(DomainEvent, existing)

    try:
        return cast(
            DomainEvent,
            DomainEvent.objects.create(
                event_type=command.event_type,
                aggregate_type=command.aggregate_type,
                aggregate_id=command.aggregate_id,
                payload=command.payload,
                schema_version=command.schema_version,
                idempotency_key=command.idempotency_key,
            ),
        )
    except IntegrityError:
        if not command.idempotency_key:
            raise
        return cast(DomainEvent, DomainEvent.objects.get(idempotency_key=command.idempotency_key))


@transaction.atomic
def enqueue_outbox_message(command: OutboxCommand) -> OutboxMessage:
    message, _created = OutboxMessage.objects.get_or_create(
        idempotency_key=command.idempotency_key,
        defaults={"topic": command.topic, "payload": command.payload},
    )
    return message


@transaction.atomic
def mark_outbox_processed(message: OutboxMessage) -> OutboxMessage:
    message.status = OutboxStatus.PROCESSED
    message.processed_at = timezone.now()
    message.last_error = ""
    message.save(update_fields=["status", "processed_at", "last_error", "updated_at"])
    return message


@transaction.atomic
def mark_outbox_failed(message: OutboxMessage, error: str) -> OutboxMessage:
    message.attempts += 1
    message.last_error = error[:4000]
    if message.attempts >= len(RETRY_DELAYS):
        message.status = OutboxStatus.DEAD_LETTER
        message.next_attempt_at = None
    else:
        message.status = OutboxStatus.PENDING
        message.next_attempt_at = timezone.now() + RETRY_DELAYS[message.attempts - 1]
    message.save(
        update_fields=[
            "attempts",
            "last_error",
            "status",
            "next_attempt_at",
            "updated_at",
        ]
    )
    return message
