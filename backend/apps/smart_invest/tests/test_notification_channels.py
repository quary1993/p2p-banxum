"""IP of Webby-Soft SRL. U33-DEC-30: in-app and email channels of the Smart Invest alerts."""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.db.models import Model
from django.test import Client

from backend.apps.platform_core.models import OutboxMessage
from backend.apps.smart_invest.models import (
    SmartInvestMatchNotification,
    SmartInvestRule,
    SmartInvestRuleEvent,
)
from backend.apps.smart_invest.services import save_smart_invest_rule
from backend.apps.smart_invest.tests.test_smart_invest import (
    _borrower,
    _loan_command,
    _loan_services,
    _rule_command,
    admin_user,
    investor,
)

__all__ = ["admin_user", "investor"]

URL = "/api/v1/investor/smart-invest/notifications/"


def _client(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def _set_channels(user: Model, *, in_app: bool, email: bool) -> dict[str, Any]:
    response = _client(user).post(
        URL, data={"in_app": in_app, "email": email}, content_type="application/json"
    )
    assert response.status_code == 200, response.content
    return cast(dict[str, Any], response.json())


def _publish(admin_user: Model, suffix: str) -> Any:
    loans = _loan_services()
    loan = loans.create_loan(
        _loan_command(admin_user, _borrower(admin_user, suffix=suffix), title=suffix)
    )
    loans.publish_loan(loans.PublishLoanCommand(actor=admin_user, loan_id=str(loan.id)))
    return loan


def _notification_titles(user: Model) -> list[str]:
    response = _client(user).get("/api/v1/investor/portal/notifications/")
    assert response.status_code == 200, response.content
    return [row["topic"] for row in response.json()["notifications"]]


@pytest.mark.django_db
def test_both_channels_are_on_until_switched_off_also_before_set_up(
    admin_user: Model, investor: Model
) -> None:
    body = _client(investor).get("/api/v1/investor/smart-invest/").json()
    assert body["notification_channels"] == {"in_app": True, "email": True}

    body = _set_channels(investor, in_app=True, email=False)
    assert body["notification_channels"] == {"in_app": True, "email": False}
    # Only the channels are kept; Smart Invest is still not set up.
    assert body["rule"]["state"] == "not_set_up"
    assert body["rule"]["is_active"] is False

    save_smart_invest_rule(_rule_command(investor))
    rule = SmartInvestRule.objects.get(user_id=investor.pk)
    assert (rule.notify_in_app, rule.notify_email, rule.is_active) == (True, False, True)
    event = SmartInvestRuleEvent.objects.get(rule=rule, event_type="channels_changed")
    assert event.metadata == {
        "previous": {"in_app": True, "email": True},
        "new": {"in_app": True, "email": False},
    }


@pytest.mark.django_db
def test_email_off_sends_an_in_app_notice_that_is_never_emailed(
    admin_user: Model, investor: Model
) -> None:
    save_smart_invest_rule(_rule_command(investor))
    _set_channels(investor, in_app=True, email=False)
    loan = _publish(admin_user, "InApp")

    assert not OutboxMessage.objects.filter(topic="email.smart_invest_opportunity_match").exists()
    notice = OutboxMessage.objects.get(topic="notice.smart_invest_opportunity_match")
    assert notice.status == "processed"
    assert notice.payload["loan_id"] == str(loan.id)
    assert SmartInvestMatchNotification.objects.get(loan_id=loan.id).outbox_message_id == notice.pk
    listed = _client(investor).get("/api/v1/investor/portal/notifications/").json()
    [row] = [
        n for n in listed["notifications"] if n["topic"].endswith("smart_invest_opportunity_match")
    ]
    assert row["notification_source"] == "in_app"
    assert row["topic_label"] == "Smart-Invest"
    assert row["navigation_target"] == "loan"
    assert row["unread"] is True


@pytest.mark.django_db
def test_in_app_off_sends_the_email_but_keeps_it_out_of_notifications(
    admin_user: Model, investor: Model
) -> None:
    save_smart_invest_rule(_rule_command(investor))
    _set_channels(investor, in_app=False, email=True)
    _publish(admin_user, "EmailOnly")

    email = OutboxMessage.objects.get(topic="email.smart_invest_opportunity_match")
    assert email.payload["in_app"] is False
    assert "email.smart_invest_opportunity_match" not in _notification_titles(investor)


@pytest.mark.django_db
def test_both_off_records_the_match_and_sends_nothing(admin_user: Model, investor: Model) -> None:
    save_smart_invest_rule(_rule_command(investor))
    _set_channels(investor, in_app=False, email=False)
    loan = _publish(admin_user, "Silent")

    match = SmartInvestMatchNotification.objects.get(loan_id=loan.id)
    assert match.outbox_message_id is None
    assert not OutboxMessage.objects.filter(
        topic__endswith="smart_invest_opportunity_match"
    ).exists()
    # Matching goes on: the opportunity is still in the matches list.
    body = _client(investor).get("/api/v1/investor/smart-invest/").json()
    assert str(loan.id) in [match["loan_id"] for match in body["matches"]]
