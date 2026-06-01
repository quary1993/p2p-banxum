from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from backend.apps.platform_core.models import DomainEvent
from backend.apps.platform_core.models.events import OutboxStatus
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    mark_outbox_failed,
    mark_outbox_processed,
    record_domain_event,
)


@pytest.mark.django_db
def test_domain_event_idempotency_returns_existing_event() -> None:
    command = DomainEventCommand(
        event_type="ThingHappened",
        aggregate_type="Thing",
        aggregate_id="thing-1",
        payload={"ok": True},
        idempotency_key="thing-1:happened",
    )

    first = record_domain_event(command)
    second = record_domain_event(command)

    assert first.id == second.id
    assert DomainEvent.objects.count() == 1


@pytest.mark.django_db
def test_outbox_idempotency_and_retry_lifecycle() -> None:
    message = enqueue_outbox_message(
        OutboxCommand(
            idempotency_key="email-1",
            topic="email.send",
            payload={"template": "magic-link"},
        )
    )
    duplicate = enqueue_outbox_message(
        OutboxCommand(idempotency_key="email-1", topic="email.send", payload={"ignored": True})
    )

    assert duplicate.id == message.id

    before_failure = timezone.now()
    failed = mark_outbox_failed(message, "temporary provider error")
    assert failed.status == OutboxStatus.PENDING
    assert failed.attempts == 1
    assert failed.next_attempt_at is not None
    assert failed.next_attempt_at >= before_failure + timedelta(seconds=55)

    processed = mark_outbox_processed(failed)
    assert processed.status == OutboxStatus.PROCESSED
    assert processed.processed_at is not None
    assert processed.last_error == ""


@pytest.mark.django_db
def test_outbox_moves_to_dead_letter_after_retry_budget() -> None:
    message = enqueue_outbox_message(
        OutboxCommand(idempotency_key="job-1", topic="job", payload={})
    )

    for _ in range(8):
        message = mark_outbox_failed(message, "still failing")

    assert message.status == OutboxStatus.DEAD_LETTER
    assert message.next_attempt_at is None
