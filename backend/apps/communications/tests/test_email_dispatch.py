from __future__ import annotations

import json
from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
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

AGREEMENT_CHECKBOX_LABEL = (
    "I have read, understood and accept the General Terms and Conditions / "
    "User Agreement, including its integral annexes"
)


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


@pytest.fixture
def superadmin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_superuser(
            email="communications-superadmin@example.test",
            password="AdminPass123!",
            full_name="Communications Superadmin",
        ),
    )


def _auth_services() -> Any:
    return import_module("backend.apps.accounts_auth.services")


def _document_services() -> Any:
    return import_module("backend.apps.documents.services")


class _FakeSendGridResponse:
    status = 202
    headers = {"X-Message-Id": "sendgrid-message-1"}

    def __enter__(self) -> _FakeSendGridResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b""


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
    assert dispatch_result.sent_count == 1, EmailDeliveryRecord.objects.get().error
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
    assert (
        '<a class="btn-a font-sans" href="https://app.banxum.test/login?token='
        in delivery.body_html
    )
    assert f'href="https://app.banxum.test/login?token={result.raw_token}"' in delivery.body_html
    assert "Open secure login link" in delivery.body_html
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

    assert dispatch_result.sent_count == 1, EmailDeliveryRecord.objects.get().error
    outbox.refresh_from_db()
    assert outbox.status == OutboxStatus.PROCESSED
    delivery = EmailDeliveryRecord.objects.get(outbox_message=outbox)
    assert result.raw_code in delivery.body_text
    assert result.raw_code in delivery.body_html
    assert "Action needed" in delivery.body_html
    assert "fx" in delivery.metadata["action"]


@pytest.mark.django_db
@override_settings(
    COMMUNICATIONS_EMAIL_PROVIDER="sendgrid",
    SENDGRID_API_KEY="SG.test",
    SENDGRID_FROM_EMAIL="hq@banxum.com",
    SENDGRID_FROM_NAME="BANXUM",
    SENDGRID_TIMEOUT_SECONDS=7,
    PUBLIC_APP_BASE_URL="https://app.banxum.test",
)
def test_sensitive_action_email_dispatch_uses_sendgrid_payload_without_tracking(
    investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_services = _auth_services()
    result = auth_services.issue_sensitive_action_code(
        auth_services.SensitiveActionCodeCommand(user=investor, action="withdrawal")
    )
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int) -> _FakeSendGridResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(cast(bytes, request.data).decode("utf-8"))
        return _FakeSendGridResponse()

    monkeypatch.setattr(
        "backend.apps.communications.services.urllib.request.urlopen",
        fake_urlopen,
    )

    dispatch_result = dispatch_due_email_outbox_messages()

    assert dispatch_result.sent_count == 1, EmailDeliveryRecord.objects.get().error
    assert captured["url"] == "https://api.sendgrid.com/v3/mail/send"
    assert captured["timeout"] == 7
    assert captured["headers"]["Authorization"] == "Bearer SG.test"
    payload = captured["payload"]
    assert payload["from"] == {"email": "hq@banxum.com", "name": "BANXUM"}
    assert payload["personalizations"][0]["to"][0]["email"] == cast(Any, investor).email
    assert payload["tracking_settings"] == {
        "click_tracking": {"enable": False, "enable_text": False},
        "open_tracking": {"enable": False},
    }
    assert result.raw_code in payload["content"][0]["value"]
    assert result.raw_code in payload["content"][1]["value"]
    assert "<a " in payload["content"][1]["value"]
    delivery = EmailDeliveryRecord.objects.get(template_key="auth.withdrawal.code.v1")
    assert delivery.provider == "sendgrid"
    assert delivery.provider_message_id == "sendgrid-message-1"


@pytest.mark.django_db
@override_settings(
    COMMUNICATIONS_EMAIL_PROVIDER="mock",
    PUBLIC_APP_BASE_URL="https://app.banxum.test",
)
def test_dispatch_legacy_document_acceptance_email_points_to_portal_without_attachment(
    investor: Model,
    superadmin_user: Model,
) -> None:
    documents = _document_services()
    version = documents.create_document_template_version(
        documents.CreateDocumentTemplateVersionCommand(
            actor=superadmin_user,
            category="registration",
            name="Garanta Lender User Agreement",
            title="General Terms and Conditions / User Agreement for Lenders",
            body="Agreement body for {{user.full_name}} on {{platform.name}}.",
            checkbox_labels=[AGREEMENT_CHECKBOX_LABEL],
            publish_now=True,
            legal_review_reference="approved-test",
        )
    )
    acceptance = documents.accept_document_terms(
        documents.AcceptDocumentTermsCommand(
            actor=investor,
            category="registration",
            expected_template_version_id=str(version.id),
            accepted_checkbox_labels=list(cast(list[str], version.checkbox_labels)),
            context_type="registration",
            context_id=str(investor.pk),
            idempotency_key="communications-accepted-registration-doc",
        )
    )
    outbox = OutboxMessage.objects.create(
        idempotency_key=f"legacy-document-acceptance:{acceptance.pk}:portal-notice",
        topic="email.document_acceptance_pdf",
        payload={
            "acceptance_id": str(acceptance.pk),
            "email": cast(Any, investor).email,
        },
    )

    dispatch_result = dispatch_due_email_outbox_messages()

    assert dispatch_result.sent_count == 1
    outbox.refresh_from_db()
    assert outbox.status == OutboxStatus.PROCESSED
    delivery = EmailDeliveryRecord.objects.get(outbox_message=outbox)
    assert delivery.recipient_email == cast(Any, investor).email
    assert delivery.template_key == "documents.acceptance_portal_notice.v1"
    assert delivery.metadata["attachment_count"] == 0
    assert delivery.metadata["attachments"] == []
    assert not apps.get_model("documents", "DocumentRenderedArtifact").objects.filter(
        acceptance=acceptance,
        purpose="email_delivery",
    ).exists()
    assert "Your accepted document is available" in delivery.body_html
    assert "https://app.banxum.test/documents" in delivery.body_html


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


@pytest.mark.django_db
@override_settings(
    COMMUNICATIONS_EMAIL_PROVIDER="mock",
    PUBLIC_APP_BASE_URL="https://app.banxum.test",
    SUPPORT_EMAIL="support@banxum.test",
)
def test_payload_email_uses_banxum_template_and_linkifies_urls() -> None:
    outbox = OutboxMessage.objects.create(
        idempotency_key="manual-email-with-link",
        topic="email.manual",
        payload={
            "email": "investor@example.test",
            "subject": "Manual notice",
            "body_text": (
                "Review your account notice here:\n\n"
                "https://app.banxum.test/documents"
            ),
            "template_key": "manual.notice.v1",
        },
    )

    dispatch_due_email_outbox_messages()

    delivery = EmailDeliveryRecord.objects.get(outbox_message=outbox)
    assert "<!DOCTYPE html>" in delivery.body_html
    assert "BANXUM" in delivery.body_html
    assert "Garanta Finanzgruppe AG" in delivery.body_html
    assert (
        '<a href="https://app.banxum.test/documents" target="_blank"'
        in delivery.body_html
    )
    assert "support@banxum.test" in delivery.body_html
