from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import override_settings
from django.utils import timezone

from backend.apps.communications.models import (
    CommunicationEvent,
    EmailDeliveryRecord,
    EmailDeliveryStatus,
)
from backend.apps.communications.services import (
    DispatchEmailOutboxCommand,
    dispatch_due_email_outbox_messages,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent, OutboxMessage
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.models.events import OutboxStatus


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="investor@example.test",
            full_name="Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )


def _auth_services() -> Any:
    return import_module("backend.apps.accounts_auth.services")


@pytest.mark.django_db
@override_settings(
    COMMUNICATIONS_EMAIL_PROVIDER="mock",
    COMMUNICATIONS_IMMEDIATE_AUTH_EMAILS=False,
    PUBLIC_APP_BASE_URL="https://app.banxum.test",
)
def test_dispatch_magic_link_email_archives_full_content_and_marks_processed(
    investor: Model,
) -> None:
    auth_services = _auth_services()
    result = auth_services.issue_magic_link(
        auth_services.MagicLinkRequestCommand(email=cast(Any, investor).email)
    )
    outbox = OutboxMessage.objects.get(topic="email.magic_link_requested")

    dispatch_result = dispatch_due_email_outbox_messages(DispatchEmailOutboxCommand(limit=10))

    assert dispatch_result.processed_count == 1
    assert dispatch_result.sent_count == 1
    outbox.refresh_from_db()
    assert outbox.status == OutboxStatus.PROCESSED
    assert "token" not in outbox.payload

    delivery = EmailDeliveryRecord.objects.get(outbox_message=outbox)
    assert delivery.status == EmailDeliveryStatus.SENT
    assert delivery.template_key == "auth.magic_link.v1"
    assert delivery.recipient_email == cast(Any, investor).email
    assert "BANXUM" in delivery.subject
    assert "Garanta Finanzgruppe AG" in delivery.body_text
    assert "https://app.banxum.test/login?token=" in delivery.body_text
    assert result.raw_token in delivery.body_text
    assert delivery.provider == "mock"
    assert delivery.provider_message_id
    assert delivery.sent_at is not None

    assert CommunicationEvent.objects.filter(
        event_type="email_sent",
        outbox_message=outbox,
        email_delivery_record=delivery,
    ).exists()
    assert AuditEvent.objects.filter(
        action="communications.email_sent",
        target_id=str(outbox.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="EmailSent",
        aggregate_id=str(outbox.id),
    ).exists()


@pytest.mark.django_db
@override_settings(
    COMMUNICATIONS_EMAIL_PROVIDER="mock",
    COMMUNICATIONS_IMMEDIATE_AUTH_EMAILS=False,
    PUBLIC_APP_BASE_URL="https://app.banxum.test",
)
def test_dispatch_sensitive_action_code_email_archives_code(
    investor: Model,
) -> None:
    auth_services = _auth_services()
    result = auth_services.issue_sensitive_action_code(
        auth_services.SensitiveActionCodeCommand(user=investor, action="fx")
    )
    outbox = OutboxMessage.objects.get(topic="email.sensitive_action_code_requested")

    dispatch_result = dispatch_due_email_outbox_messages()

    assert dispatch_result.sent_count == 1
    outbox.refresh_from_db()
    assert outbox.status == OutboxStatus.PROCESSED
    assert result.raw_code in EmailDeliveryRecord.objects.get(outbox_message=outbox).body_text
    assert "fx" in EmailDeliveryRecord.objects.get(outbox_message=outbox).metadata["action"]


@pytest.mark.django_db
@override_settings(COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_dispatch_unsupported_email_topic_records_failure_and_retry() -> None:
    outbox = OutboxMessage.objects.create(
        idempotency_key="unsupported-email",
        topic="email.future_template_without_renderer",
        payload={"email": "investor@example.test"},
    )

    dispatch_result = dispatch_due_email_outbox_messages()

    assert dispatch_result.processed_count == 1
    assert dispatch_result.sent_count == 0
    assert dispatch_result.failed_count == 1
    outbox.refresh_from_db()
    assert outbox.status == OutboxStatus.PENDING
    assert outbox.attempts == 1
    assert outbox.next_attempt_at is not None
    delivery = EmailDeliveryRecord.objects.get(outbox_message=outbox)
    assert delivery.status == EmailDeliveryStatus.FAILED
    assert "no renderable template" in delivery.error
    assert CommunicationEvent.objects.filter(event_type="email_failed").exists()


@pytest.mark.django_db
@override_settings(COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_dispatch_skips_future_retry_messages() -> None:
    OutboxMessage.objects.create(
        idempotency_key="future-email",
        topic="email.future_template_without_renderer",
        payload={"email": "investor@example.test"},
        next_attempt_at=timezone.now() + timedelta(hours=1),
    )

    dispatch_result = dispatch_due_email_outbox_messages()

    assert dispatch_result.processed_count == 0
    assert EmailDeliveryRecord.objects.count() == 0


@pytest.mark.django_db
@override_settings(COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_communications_evidence_is_append_only_at_app_and_database_layers() -> None:
    outbox = OutboxMessage.objects.create(
        idempotency_key="append-only-email",
        topic="email.manual",
        payload={
            "email": "investor@example.test",
            "subject": "Manual notice",
            "body_text": "Notice body",
        },
    )
    dispatch_due_email_outbox_messages()
    delivery = EmailDeliveryRecord.objects.get(outbox_message=outbox)
    event = CommunicationEvent.objects.get(email_delivery_record=delivery)

    delivery.subject = "Changed"
    with pytest.raises(AppendOnlyViolation):
        delivery.save()
    with pytest.raises(AppendOnlyViolation):
        EmailDeliveryRecord.objects.filter(id=delivery.id).update(subject="Changed")
    event.metadata = {"changed": True}
    with pytest.raises(AppendOnlyViolation):
        event.save()

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE communications_emaildeliveryrecord SET id = %s WHERE id = %s",
                [delivery.id.hex, delivery.id.hex],
            )

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM communications_communicationevent WHERE id = %s",
                [event.id.hex],
            )
