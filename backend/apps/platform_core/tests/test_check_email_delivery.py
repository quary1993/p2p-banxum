"""IP of Webby-Soft SRL. check_email_delivery: why an email to one address was or was not sent."""

from __future__ import annotations

from importlib import import_module
from io import StringIO

import pytest
from django.apps import apps
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def _run(email: str) -> str:
    out = StringIO()
    call_command("check_email_delivery", "--email", email, stdout=out)
    return out.getvalue()


def _user(email: str, account_type: str) -> object:
    user_model = apps.get_model("accounts_auth", "User")
    return user_model.objects.create_user(
        email=email, full_name="Mail Check", account_type=account_type, status="pending_kyc"
    )


def test_no_account_explains_that_nothing_is_sent() -> None:
    output = _run("Nobody@Example.test")
    assert "No account uses this email address." in output
    assert "sends nothing" in output
    assert "It never ran here" in output


def test_investor_reset_shows_the_queued_email_and_never_the_token() -> None:
    _user("investor-mail@example.test", "natural_person_lender")
    two_factor = import_module("backend.apps.accounts_auth.two_factor")
    raw = two_factor.request_password_reset(email="investor-mail@example.test")
    assert raw

    output = _run("investor-mail@example.test")
    assert "Password reset: can be sent." in output
    assert "password_reset: expires" in output
    assert "email.password_reset: pending, attempts 0" in output
    assert raw not in output


def test_staff_account_gets_no_investor_reset() -> None:
    _user("staff-mail@example.test", "superadmin")
    two_factor = import_module("backend.apps.accounts_auth.two_factor")
    assert two_factor.request_password_reset(email="staff-mail@example.test") == ""

    output = _run("staff-mail@example.test")
    assert "this is a staff account" in output
    assert "Reset requests (newest first)\n  None." in output
