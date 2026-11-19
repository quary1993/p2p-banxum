"""IP of Webby-Soft SRL. 18.5 (U33-DEC-01): an operation's email code confirms only that
operation; D-1: an investor with an authenticator app types its code instead of the PIN;
the 72-hour pause after an assisted recovery.

The codes here are requested through the API with the details the portal sends, so the
binding runs end to end (the "bound at first use" test hook never touches them).
"""

from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.platform_core.domain.operation_binding import (
    OperationBindingError,
    normalized_operation,
    operation_fingerprint,
    operation_summary,
)
from backend.apps.platform_core.tests.factories import TEST_SENSITIVE_ACTION_PIN, give_test_pin

IBAN = "CH5604835012345678009"
OTHER_IBAN = "CH9300762011623852957"


def _helpers() -> Any:
    return import_module("backend.apps.accounts_auth.tests.signin_helpers")


def test_details_are_normalized_before_the_fingerprint() -> None:
    typed = {"currency": "chf", "iban": "ch56 0483 5012 3456 7800 9"}
    clean = {"currency": "CHF", "iban": IBAN}

    assert normalized_operation("bank_account_change", typed) == clean
    assert operation_fingerprint("bank_account_change", typed) == operation_fingerprint(
        "bank_account_change", clean
    )
    assert operation_fingerprint(
        "withdrawal", {"amount_minor": 100_00, "currency": "CHF", "iban": IBAN}
    ) != operation_fingerprint(
        "withdrawal", {"amount_minor": 1_000_00, "currency": "CHF", "iban": IBAN}
    )
    # The same details for another action give another fingerprint.
    assert operation_fingerprint(
        "primary_investment", {"amount_minor": 1, "currency": "CHF", "loan_id": "a"}
    ) != operation_fingerprint(
        "secondary_market_purchase", {"amount_minor": 1, "currency": "CHF", "listing_id": "a"}
    )


@pytest.mark.parametrize(
    ("action", "details"),
    [
        ("withdrawal", {"amount_minor": 100, "currency": "CHF"}),
        ("withdrawal", {"amount_minor": 0, "currency": "CHF", "iban": IBAN}),
        ("withdrawal", {"amount_minor": 100, "currency": "CHFX", "iban": IBAN}),
        ("bank_account_change", {"currency": "CHF", "iban": "CH12"}),
        ("fx", {"amount_minor": 100, "source_currency": "CHF"}),
        ("pin_change", {"amount_minor": 100}),
    ],
)
def test_wrong_sets_of_details_are_refused(action: str, details: dict[str, object]) -> None:
    with pytest.raises(OperationBindingError):
        normalized_operation(action, details)


def test_the_email_summary_names_the_operation_without_the_full_iban() -> None:
    assert (
        operation_summary("withdrawal", {"amount_minor": 123_456, "currency": "EUR", "iban": IBAN})
        == "Withdrawal of 1,234.56 EUR to IBAN ending 8009"
    )
    assert operation_summary("secondary_market_listing", {"holding_id": "h", "price_bps": 0}) == (
        "Resale listing at 0.00% of the outstanding principal"
    )
    assert operation_summary("bank_account_change", {"instruction_id": "x"}) == (
        "Change of the default return account"
    )


@pytest.fixture
def investor() -> Model:
    user = get_user_model().objects.create_user(
        email="binding@example.test",
        full_name="Binding Investor",
        account_type="natural_person_lender",
        status="active",
    )
    _helpers().ready_investor(user)
    return cast(Model, user)


def _client(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def _request_code(client: Client, action: str, operation: dict[str, object] | None) -> Any:
    body: dict[str, object] = {"action": action}
    if operation is not None:
        body["operation"] = operation
    return client.post(
        "/api/v1/auth/sensitive-action-code/request/", data=body, content_type="application/json"
    )


def _raw_code(code_id: str) -> str:
    services: Any = import_module("backend.apps.accounts_auth.services")
    record = apps.get_model("accounts_auth", "SensitiveActionCode").objects.get(id=code_id)
    return str(services.delivery_secret_for_sensitive_action_code(record))


def _add_account(client: Client, iban: str, code_id: str, pin: str) -> Any:
    return client.post(
        "/api/v1/ledger/payout-instructions/",
        data={
            "currency": "CHF",
            "destination_iban": iban,
            "destination_account_name": "Binding Investor",
            "sensitive_action_code_id": code_id,
            "sensitive_action_code": _raw_code(code_id),
            "pin": pin,
        },
        content_type="application/json",
    )


@pytest.mark.django_db
def test_an_operation_code_needs_valid_details_and_the_email_shows_them(investor: Model) -> None:
    client = _client(investor)

    missing = _request_code(client, "withdrawal", None)
    wrong_shape = _request_code(client, "withdrawal", {"amount_minor": 100})
    issued = _request_code(
        client, "withdrawal", {"amount_minor": 250_00, "currency": "CHF", "iban": IBAN}
    )

    assert missing.status_code == 400
    assert missing.json()["code"] == "operation_details_invalid"
    assert wrong_shape.status_code == 400
    assert issued.status_code == 202
    assert issued.json()["operation_summary"] == "Withdrawal of 250.00 CHF to IBAN ending 8009"
    # A PIN code is not an operation and takes no details.
    assert _request_code(client, "pin_change", {"amount_minor": 1}).status_code == 400
    assert _request_code(client, "pin_change", None).status_code == 202


@pytest.mark.django_db
def test_a_code_for_one_bank_account_cannot_add_another(investor: Model) -> None:
    give_test_pin(investor)
    client = _client(investor)
    code_for_a = _request_code(
        client, "bank_account_change", {"currency": "CHF", "iban": OTHER_IBAN}
    ).json()["code_id"]

    refused = _add_account(client, IBAN, code_for_a, TEST_SENSITIVE_ACTION_PIN)

    assert refused.status_code == 400
    assert "other operation details" in refused.json()["detail"]
    code_model = apps.get_model("accounts_auth", "SensitiveActionCode")
    # The right code for other details is spent: it cannot be tried again.
    assert code_model.objects.get(id=code_for_a).superseded_at is not None
    assert (
        not apps.get_model("ledger", "InvestorPayoutInstruction")
        .objects.filter(investor_user_id=investor.pk)
        .exists()
    )

    # Same account, typed the way people type it, binds to the same fingerprint.
    code_model.objects.filter(user_id=investor.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    code_for_b = _request_code(
        client, "bank_account_change", {"currency": "chf", "iban": "ch56 0483 5012 3456 7800 9"}
    ).json()["code_id"]
    added = _add_account(client, IBAN, code_for_b, TEST_SENSITIVE_ACTION_PIN)
    assert added.status_code == 201, added.content


@pytest.mark.django_db
def test_an_investor_with_the_app_confirms_with_the_app_code_not_a_pin(investor: Model) -> None:
    """D-1 (Vlad, 2026-11-19): the email code + the authenticator code; no PIN."""
    helpers = _helpers()
    helpers.give_authenticator(investor)
    client = _client(investor)
    code_id = _request_code(
        client, "bank_account_change", {"currency": "CHF", "iban": IBAN}
    ).json()["code_id"]

    with_pin = _add_account(client, IBAN, code_id, TEST_SENSITIVE_ACTION_PIN)

    assert with_pin.status_code == 400
    assert with_pin.json()["code"] == "authenticator_code_invalid"
    assert with_pin.json()["attempts_left"] == 4
    # The email code is untouched by a wrong second factor.
    record = apps.get_model("accounts_auth", "SensitiveActionCode").objects.get(id=code_id)
    assert record.attempts == 0 and record.consumed_at is None

    added = _add_account(client, IBAN, code_id, helpers.app_code(investor))

    assert added.status_code == 201, added.content
    assert (
        not apps.get_model("accounts_auth", "SensitiveActionPin")
        .objects.filter(user_id=investor.pk)
        .exists()
    )


@pytest.mark.django_db
def test_no_new_bank_account_or_default_return_account_for_72_hours_after_a_recovery(
    investor: Model,
) -> None:
    give_test_pin(investor)
    apps.get_model("accounts_auth", "SecurityRestriction").objects.create(
        user_id=investor.pk,
        reason="assisted_recovery",
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(hours=72),
    )
    client = _client(investor)
    code_id = _request_code(
        client, "bank_account_change", {"currency": "CHF", "iban": IBAN}
    ).json()["code_id"]

    refused = _add_account(client, IBAN, code_id, TEST_SENSITIVE_ACTION_PIN)

    assert refused.status_code == 400
    assert "72 hours" in refused.json()["detail"]
    # Checked before the email code: the code is still usable after the pause.
    record = apps.get_model("accounts_auth", "SensitiveActionCode").objects.get(id=code_id)
    assert record.consumed_at is None and record.attempts == 0
    ledger: Any = import_module("backend.apps.ledger.services")
    with pytest.raises(ledger.LedgerValidationError, match="72 hours"):
        ledger.set_investor_default_return_account(
            ledger.SetInvestorDefaultReturnAccountCommand(actor=investor, instruction_id="x")
        )


@pytest.mark.django_db
def test_new_operation_details_get_a_new_code_at_once(investor: Model) -> None:
    """A price that moved (or a new amount) needs a new code; the cooldown holds only a
    repeated request for the same details."""
    client = _client(investor)
    first = _request_code(
        client, "withdrawal", {"amount_minor": 100_00, "currency": "CHF", "iban": IBAN}
    )
    same = _request_code(
        client, "withdrawal", {"amount_minor": 100_00, "currency": "CHF", "iban": IBAN}
    )
    changed = _request_code(
        client, "withdrawal", {"amount_minor": 200_00, "currency": "CHF", "iban": IBAN}
    )

    assert first.status_code == 202
    assert same.status_code == 429
    assert changed.status_code == 202
    code_model = apps.get_model("accounts_auth", "SensitiveActionCode")
    assert code_model.objects.get(id=first.json()["code_id"]).superseded_at is not None
