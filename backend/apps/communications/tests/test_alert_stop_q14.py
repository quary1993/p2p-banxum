# IP of Webby-Soft SRL.
"""Q14 (2026-11-13): "Stop these alerts" links and one News/newsletter preference."""

from __future__ import annotations

import urllib.parse
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client

from backend.apps.communications.alert_stop import (
    AlertStopTokenError,
    alert_stop_token,
    stop_alerts,
)
from backend.apps.communications.models import NewsletterSubscription
from backend.apps.communications.services import render_email_for_outbox_message
from backend.apps.platform_core.models import OutboxMessage

pytestmark = pytest.mark.django_db

# Peer apps are reached at run time (import contract: no static imports between domain apps).
_coming_soon = import_module("backend.apps.marketplace_primary.tests.test_coming_soon_u33")
_draft = _coming_soon._draft
_make_investor = _coming_soon._make_investor
_publish = _coming_soon._publish
LoanOpeningAlert: Any = apps.get_model("marketplace_primary", "LoanOpeningAlert")
SavedOpportunity: Any = apps.get_model("marketplace_primary", "SavedOpportunity")


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="stop-admin@example.test",
            password="AdminPass123!",
            full_name="Stop Admin",
            account_type="superadmin",
            status="active",
            is_staff=True,
            is_superuser=True,
        ),
    )


def _post_stop(token: str) -> Any:
    return Client().post("/api/v1/public/alerts/stop/", {"token": token}, "application/json")


def test_smart_invest_link_stops_only_the_emails(admin_user: Model) -> None:
    investor = _make_investor("stop-smart@example.test")
    rule_model = apps.get_model("smart_invest", "SmartInvestRule")
    rule = rule_model.objects.create(user=investor, is_active=True, minimum_yield_bps=500)

    response = _post_stop(alert_stop_token(user_id=str(investor.pk), kind="smart_invest"))

    assert response.status_code == 200, response.content
    assert response.json()["kind"] == "smart_invest"
    assert "Smart Invest emails are stopped" in response.json()["message"]
    rule.refresh_from_db()
    assert (rule.notify_email, rule.notify_in_app, rule.is_active) == (False, True, True)
    # Repeating the link is fine.
    again = _post_stop(alert_stop_token(user_id=str(investor.pk), kind="smart_invest"))
    assert again.status_code == 200


def test_opening_and_saved_links_stop_their_project_and_bad_links_are_refused(
    admin_user: Model,
) -> None:
    investor = _make_investor("stop-loans@example.test")
    soon = _draft(admin_user, title="Soon loan")
    LoanOpeningAlert.objects.create(loan=soon, investor_user_id=investor.pk)
    open_loan = _draft(admin_user, title="Open loan")
    _publish(admin_user, open_loan)
    saved = SavedOpportunity.objects.create(loan=open_loan, investor_user_id=investor.pk)

    opening = _post_stop(
        alert_stop_token(user_id=str(investor.pk), kind="opening_alert", loan_id=str(soon.pk))
    )
    assert opening.status_code == 200, opening.content
    assert opening.json()["loan_title"] == "Soon loan"
    assert not LoanOpeningAlert.objects.filter(loan=soon, investor_user_id=investor.pk).exists()

    reminder = _post_stop(
        alert_stop_token(user_id=str(investor.pk), kind="saved_reminder", loan_id=str(open_loan.pk))
    )
    assert reminder.status_code == 200, reminder.content
    assert "stays saved" in reminder.json()["message"]
    saved.refresh_from_db()
    assert saved.email_reminders_stopped_at is not None

    token = alert_stop_token(user_id=str(investor.pk), kind="smart_invest")
    assert _post_stop(token[:-2] + "xx").status_code == 400
    assert _post_stop("not-a-token").json()["code"] == "invalid_token"
    with pytest.raises(AlertStopTokenError):
        stop_alerts("")


def test_alert_emails_carry_the_link_and_the_stored_copy_is_redacted(admin_user: Model) -> None:
    investor = _make_investor("stop-email@example.test")
    loan = _draft(admin_user, title="Email loan")
    message = OutboxMessage.objects.create(
        idempotency_key="q14-email",
        topic="email.loan_opening_alert",
        payload={
            "user_id": str(investor.pk),
            "email": "stop-email@example.test",
            "subject": "Now open: Email loan",
            "body_text": "Email loan is now open for investment.",
            "stop_alerts": {"kind": "opening_alert", "loan_id": str(loan.pk)},
        },
    )

    live = render_email_for_outbox_message(message)
    stored = render_email_for_outbox_message(message, redact_secrets=True)

    assert "Stop these alerts: http" in live.body_text
    assert "/alerts/stop?token=" in live.body_html
    assert "token=%5Bredacted%5D" in stored.body_text
    assert "token=%5Bredacted%5D" in stored.body_html
    token = live.body_text.rsplit("token=", 1)[1].strip()
    assert stop_alerts(urllib.parse.unquote(token)).kind == "opening_alert"


def test_saved_reminder_after_stop_is_in_app_only(admin_user: Model) -> None:
    from datetime import UTC, datetime, time, timedelta

    saved_module = import_module("backend.apps.marketplace_primary.saved_opportunities")
    investor = _make_investor("stop-reminder@example.test")
    loan = _draft(admin_user, title="Reminder loan")
    _publish(admin_user, loan)
    loan.refresh_from_db()
    deadline = cast(Any, loan).funding_deadline
    saved = SavedOpportunity.objects.create(loan=loan, investor_user_id=investor.pk)
    SavedOpportunity.objects.filter(pk=saved.pk).update(
        created_at=datetime.combine(deadline - timedelta(days=20), time(9), tzinfo=UTC)
    )
    saved_module.stop_saved_reminder_emails(
        investor_user_id=str(investor.pk), loan_id=str(loan.pk)
    )

    saved_module.send_saved_opportunity_reminders(
        as_of=datetime.combine(deadline - timedelta(days=7), time(9), tzinfo=UTC)
    )

    topics = list(
        OutboxMessage.objects.filter(payload__user_id=str(investor.pk)).values_list(
            "topic", flat=True
        )
    )
    assert topics == ["notice.saved_opportunity_closing"]


def test_news_and_newsletter_are_one_preference_for_the_same_address(admin_user: Model) -> None:
    accounts = import_module("backend.apps.accounts_auth.services")
    newsletter = import_module("backend.apps.communications.newsletter")
    investor = _make_investor("one-preference@example.test")
    cast(Any, investor).marketing_consent = True
    investor.save(update_fields=["marketing_consent"])
    subscription = NewsletterSubscription.objects.create(
        email="one-preference@example.test",
        status="confirmed",
        source="other",
        consent_version="test",
    )

    accounts.update_marketing_consent(
        accounts.UpdateMarketingConsentCommand(user=investor, marketing_consent=False)
    )
    subscription.refresh_from_db()
    assert subscription.status == "unsubscribed"

    # The other way round: a newsletter unsubscribe stops "News from Banxum".
    investor.refresh_from_db()
    cast(Any, investor).marketing_consent = True
    investor.save(update_fields=["marketing_consent"])
    NewsletterSubscription.objects.filter(pk=subscription.pk).update(status="confirmed")
    subscription.refresh_from_db()
    newsletter._issue_unsubscribe_token(subscription)
    subscription.save(update_fields=["unsubscribe_token_nonce", "unsubscribe_token_hash"])
    token = newsletter._live_token(subscription, newsletter.TOKEN_PURPOSE_UNSUBSCRIBE)
    newsletter.unsubscribe_from_newsletter(token)
    investor.refresh_from_db()
    assert cast(Any, investor).marketing_consent is False
