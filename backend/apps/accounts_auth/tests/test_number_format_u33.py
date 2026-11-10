"""IP of Webby-Soft SRL. U33-DEC-32: the number format saved in the account and used in messages."""

from __future__ import annotations

from importlib import import_module
from typing import Any, cast

import pytest
from django.test import Client, override_settings

from backend.apps.accounts_auth.models import AccountStatus, AccountType, User
from backend.apps.platform_core.domain.money import (
    format_amount_minor,
    localize_number_text,
    number_format_context,
)
from backend.apps.platform_core.models import AuditEvent
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message

pytestmark = pytest.mark.django_db


@pytest.fixture
def investor() -> User:
    return User.objects.create_user(
        email="format@example.test",
        full_name="Format Investor",
        account_type=AccountType.NATURAL_PERSON_LENDER,
        status=AccountStatus.ACTIVE,
    )


def _client(user: User) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def test_european_is_the_default_and_swiss_is_saved_in_the_account(investor: User) -> None:
    client = _client(investor)
    assert client.get("/api/v1/auth/me/").json()["user"]["number_format"] == "european"

    changed = client.patch(
        "/api/v1/auth/preferences/display/",
        data={"number_format": "swiss"},
        content_type="application/json",
    )

    assert changed.status_code == 200, changed.content
    assert changed.json()["user"]["number_format"] == "swiss"
    investor.refresh_from_db()
    assert investor.number_format == "swiss"
    assert AuditEvent.objects.filter(action="account.number_format_changed").count() == 1
    refused = client.patch(
        "/api/v1/auth/preferences/display/",
        data={"number_format": "us"},
        content_type="application/json",
    )
    assert refused.status_code == 400


def test_text_and_values_follow_the_format_without_changing_the_value() -> None:
    canonical = format_amount_minor(1_234_567_89, "CHF")
    assert canonical == "CHF 1'234'567.89"
    assert localize_number_text(f"Paid {canonical} at 7.40%.", "european") == (
        "Paid CHF 1.234.567,89 at 7,40%."
    )
    assert localize_number_text(f"Paid {canonical} at 7.40%.", "swiss") == (
        "Paid CHF 1'234'567.89 at 7.40%."
    )
    # Dates and references are not numbers to format.
    assert (
        localize_number_text("Due 2026-10-09, ref A-1.2", "european") == "Due 2026-10-09, ref A-1.2"
    )
    with number_format_context("european"):
        assert format_amount_minor(-50, "EUR") == "EUR -0,50"


@override_settings(COMMUNICATIONS_EMAIL_PROVIDER="mock")
def test_emails_show_amounts_in_the_recipient_format(investor: User) -> None:
    def rendered() -> Any:
        message = enqueue_outbox_message(
            OutboxCommand(
                idempotency_key=f"format-check-{investor.number_format}",
                topic="email.investor_notice",
                payload={
                    "user_id": str(investor.pk),
                    "email": investor.email,
                    "subject": "Repayment of CHF 1'250.50",
                    "body_text": "CHF 1'250.50 was credited at 8.25%.",
                    "data_rows": [["Amount", "CHF 1'250.50"]],
                },
            )
        )
        # Through import_module: accounts_auth does not import communications (import-linter).
        communications = import_module("backend.apps.communications.services")
        return communications.render_email_for_outbox_message(message)

    european = rendered()
    assert european.subject == "Repayment of CHF 1.250,50"
    assert "CHF 1.250,50 was credited at 8,25%." in european.body_text
    assert "CHF 1.250,50" in european.body_html
    investor.number_format = "swiss"
    investor.save(update_fields=["number_format"])
    swiss = rendered()
    assert swiss.subject == "Repayment of CHF 1'250.50"
    assert "8.25%" in swiss.body_text


def test_english_is_the_default_language_and_german_is_saved_in_the_account(
    investor: User,
) -> None:
    client = _client(investor)
    assert client.get("/api/v1/auth/me/").json()["user"]["language"] == "en"

    changed = client.patch(
        "/api/v1/auth/preferences/display/",
        data={"language": "de-CH"},
        content_type="application/json",
    )

    assert changed.status_code == 200, changed.content
    assert changed.json()["user"]["language"] == "de-CH"
    # The other preference is unchanged.
    assert changed.json()["user"]["number_format"] == "european"
    assert AuditEvent.objects.filter(action="account.language_changed").count() == 1
    for data in ({"language": "fr"}, {}):
        refused = client.patch(
            "/api/v1/auth/preferences/display/", data=data, content_type="application/json"
        )
        assert refused.status_code == 400
