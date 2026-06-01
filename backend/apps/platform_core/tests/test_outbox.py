from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from backend.apps.platform_core.models import DomainEvent
from backend.apps.platform_core.models.events import OutboxStatus
from backend.apps.platform_core.services.events import (
    RETRY_DELAYS,
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    mark_outbox_failed,
    mark_outbox_processed,
    record_domain_event,
    record_event_and_enqueue,
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

    for _ in range(len(RETRY_DELAYS)):
        message = mark_outbox_failed(message, "still failing")
        assert message.status == OutboxStatus.PENDING

    assert message.attempts == len(RETRY_DELAYS)
    assert message.next_attempt_at is not None

    message = mark_outbox_failed(message, "still failing")

    assert message.status == OutboxStatus.DEAD_LETTER
    assert message.next_attempt_at is None


@pytest.mark.django_db
def test_outbox_retry_delay_sequence_reaches_all_configured_delays() -> None:
    message = enqueue_outbox_message(
        OutboxCommand(idempotency_key="job-delays", topic="job", payload={})
    )
    observed_delays: list[timedelta] = []

    for _expected_delay in RETRY_DELAYS:
        before_failure = timezone.now()
        message = mark_outbox_failed(message, "still failing")
        assert message.status == OutboxStatus.PENDING
        assert message.next_attempt_at is not None
        observed_delays.append(message.next_attempt_at - before_failure)

    for observed, expected in zip(observed_delays, RETRY_DELAYS, strict=True):
        assert expected - timedelta(seconds=2) <= observed <= expected + timedelta(seconds=2)


@pytest.mark.django_db
def test_record_event_and_enqueue_creates_both_records_idempotently() -> None:
    event_command = DomainEventCommand(
        event_type="EmailRequested",
        aggregate_type="Account",
        aggregate_id="acc-1",
        idempotency_key="acc-1:email-requested",
    )
    outbox_command = OutboxCommand(
        idempotency_key="acc-1:send-email",
        topic="email.send",
        payload={"template": "welcome"},
    )

    first_event, first_message = record_event_and_enqueue(event_command, outbox_command)
    second_event, second_message = record_event_and_enqueue(event_command, outbox_command)

    assert first_event.id == second_event.id
    assert first_message.id == second_message.id
    assert DomainEvent.objects.count() == 1
