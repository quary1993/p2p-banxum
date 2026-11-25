"""IP of Webby-Soft SRL. Requested emails, the public response and the scheduled fallback."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import BoundedSemaphore, Event, get_ident
from typing import Any

import pytest
from django.apps import apps
from django.db import connection, transaction
from django.test import Client, override_settings

from backend.apps.communications import services as mail
from backend.apps.communications.models import EmailDeliveryRecord
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.services import prompt_email
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message


def _investor() -> Any:
    return apps.get_model("accounts_auth", "User").objects.create_user(
        email="reset-timing@example.test",
        full_name="Reset Test",
        account_type="natural_person_lender",
        status="active",
    )


@pytest.mark.django_db(transaction=True)
@override_settings(COMMUNICATIONS_IMMEDIATE_AUTH_EMAILS=True, COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_public_reset_returns_before_provider_and_sends_without_cron(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("This test needs independent committed transactions and PostgreSQL teardown.")
    user = _investor()
    request_thread = get_ident()
    entered, release = Event(), Event()
    original_send = mail.MockEmailProvider.send

    def slow_send(provider: Any, email: Any) -> Any:
        assert get_ident() != request_thread
        entered.set()
        assert release.wait(timeout=10)
        return original_send(provider, email)

    monkeypatch.setattr(mail.MockEmailProvider, "send", slow_send)
    url = "/api/v1/auth/password/forgot/"
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(prompt_email, "_executor", pool)
        unknown = client.post(
            url,
            {"email": "absent@example.test"},
            content_type="application/json",
            REMOTE_ADDR="192.0.2.70",
        )
        try:
            accepted = client.post(
                url,
                {"email": user.email},
                content_type="application/json",
                REMOTE_ADDR="192.0.2.71",
            )
            assert accepted.status_code == unknown.status_code == 202
            assert accepted.json() == unknown.json()
            assert entered.wait(timeout=10)
        finally:
            release.set()
    message = OutboxMessage.objects.get(topic="email.password_reset")
    assert message.status == "processed"
    assert EmailDeliveryRecord.objects.get(outbox_message=message).status == "sent"
    assert not mail.dispatch_email_outbox_message_now(message.pk)


@pytest.mark.django_db
@override_settings(COMMUNICATIONS_IMMEDIATE_AUTH_EMAILS=True, COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_requested_reset_is_sent_on_commit_and_not_sent_again_by_cron(
    client: Client, django_capture_on_commit_callbacks: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _investor()
    monkeypatch.setattr(
        prompt_email,
        "_submit",
        lambda message_id, key: mail.dispatch_email_outbox_message_now(
            message_id, expected_key=key
        ),
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/api/v1/auth/password/forgot/",
            {"email": user.email},
            content_type="application/json",
            REMOTE_ADDR="192.0.2.72",
        )
        assert response.status_code == 202
        assert not EmailDeliveryRecord.objects.exists()
    message = OutboxMessage.objects.get(topic="email.password_reset")
    assert EmailDeliveryRecord.objects.get(outbox_message=message).status == "sent"
    mail.dispatch_due_email_outbox_messages()
    assert EmailDeliveryRecord.objects.filter(outbox_message=message).count() == 1


@pytest.mark.django_db
@override_settings(COMMUNICATIONS_IMMEDIATE_AUTH_EMAILS=True)
def test_only_new_requested_emails_get_a_post_commit_callback(
    django_capture_on_commit_callbacks: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[str] = []
    monkeypatch.setattr(prompt_email, "_submit", lambda pk, key: submitted.append(key))
    requested = [
        mail.NEWSLETTER_CONFIRMATION_EMAIL_TOPIC,
        mail.PUBLIC_ENQUIRY_EMAIL_TOPIC,
        "email.investor_support_request",
        "email.support_request_received",
        "email.security_change",
        "email.deposit_reconciled",
        "email.primary_order_released",
        "email.primary_investment_confirmation",
        "email.secondary_market_purchase_confirmation",
        "email.withdrawal_status",
    ]
    deferred = [
        mail.NEWSLETTER_NEW_PROJECTS_EMAIL_TOPIC,
        "email.balance_ageing_reminder",
        "email.loan_opening_alert",
    ]
    with django_capture_on_commit_callbacks(execute=True):
        with prompt_email.prompt_email_request():
            for topic in requested + deferred:
                command = OutboxCommand(idempotency_key=topic, topic=topic)
                enqueue_outbox_message(command)
                enqueue_outbox_message(command)
            with pytest.raises(ValueError), transaction.atomic():
                enqueue_outbox_message(OutboxCommand("rolled-back", requested[0]))
                raise ValueError("rollback")
        enqueue_outbox_message(OutboxCommand("offline-import", requested[0]))
        assert submitted == []
    assert submitted == requested


@pytest.mark.django_db
@override_settings(COMMUNICATIONS_EMAIL_PROVIDER="mock", COMMUNICATIONS_IMMEDIATE_AUTH_EMAILS=True)
def test_saturated_sender_keeps_email_for_cron_and_skips_replaced_link(
    django_capture_on_commit_callbacks: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _investor()
    auth = import_module("backend.apps.accounts_auth.two_factor")
    saturated = BoundedSemaphore(1)
    saturated.acquire()
    monkeypatch.setattr(prompt_email, "_slots", saturated)
    with django_capture_on_commit_callbacks(execute=True), prompt_email.prompt_email_request():
        old = auth.request_password_reset(email=user.email)
        new = auth.request_password_reset(email=user.email)
    assert old and new and old != new
    waiting = list(OutboxMessage.objects.filter(topic="email.password_reset").order_by("pk"))
    assert len(waiting) == 2 and all(item.status == "pending" for item in waiting)
    assert not mail.dispatch_email_outbox_message_now(
        waiting[1].pk, expected_key="previous-qa-seed"
    )
    mail.dispatch_due_email_outbox_messages()
    assert not EmailDeliveryRecord.objects.filter(outbox_message=waiting[0]).exists()
    assert EmailDeliveryRecord.objects.get(outbox_message=waiting[1]).status == "sent"
    assert not OutboxMessage.objects.filter(topic="email.password_reset", status="pending").exists()
