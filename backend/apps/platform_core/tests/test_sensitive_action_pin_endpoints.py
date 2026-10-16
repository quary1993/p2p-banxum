"""IP of Webby-Soft SRL. Every sensitive investor endpoint takes the PIN (ACC-DEC-009).

The PIN check itself (lock, wrong PIN, no PIN) runs end to end in each module's tests
through ``assert_pin_guards_sensitive_action``; here every endpoint refuses a request
that leaves the PIN out, before anything else happens.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client

from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code

_ID = str(uuid4())
SENSITIVE_ENDPOINTS = [
    pytest.param(
        "/api/v1/ledger/withdrawal-requests/",
        "withdrawal",
        {
            "amount_minor": 100,
            "currency": "CHF",
            "destination_iban": "CH9300762011623852957",
            "destination_account_name": "Investor",
            "idempotency_key": "pin-missing-withdrawal",
        },
        id="withdrawal",
    ),
    pytest.param(
        "/api/v1/ledger/payout-instructions/",
        "bank_account_change",
        {
            "currency": "CHF",
            "destination_iban": "CH9300762011623852957",
            "destination_account_name": "Investor",
        },
        id="bank_account_change",
    ),
    pytest.param(
        f"/api/v1/fx/quotes/{_ID}/execute/",
        "fx",
        {"idempotency_key": "pin-missing-fx"},
        id="fx",
    ),
    pytest.param(
        f"/api/v1/marketplace/primary/orders/{_ID}/allocate-balance/",
        "primary_investment",
        {"document_acceptance_id": _ID, "idempotency_key": "pin-missing-allocate"},
        id="primary_investment",
    ),
    pytest.param(
        "/api/v1/marketplace/primary/orders/batch/",
        "primary_investment",
        {
            "items": [{"loan_id": _ID, "amount_minor": 100}],
            "document_acceptance_id": _ID,
            "idempotency_key": "pin-missing-batch",
        },
        id="primary_batch",
    ),
    pytest.param(
        f"/api/v1/originator-claims/quotes/{_ID}/purchase/",
        "primary_investment",
        {"document_acceptance_id": _ID, "idempotency_key": "pin-missing-claim"},
        id="originator_claim_purchase",
    ),
    pytest.param(
        "/api/v1/marketplace/secondary/listings/",
        "secondary_market_listing",
        {
            "holding_id": _ID,
            "price_bps": 10_000,
            "document_acceptance_id": _ID,
            "idempotency_key": "pin-missing-listing",
        },
        id="secondary_listing",
    ),
    pytest.param(
        f"/api/v1/marketplace/secondary/listings/{_ID}/edit/",
        "secondary_market_listing",
        {
            "price_bps": 10_000,
            "document_acceptance_id": _ID,
            "idempotency_key": "pin-missing-edit",
        },
        id="secondary_listing_edit",
    ),
    pytest.param(
        f"/api/v1/marketplace/secondary/listings/{_ID}/purchase/",
        "secondary_market_purchase",
        {
            "document_acceptance_id": _ID,
            "risk_acknowledgement_accepted": True,
            "idempotency_key": "pin-missing-purchase",
            "expected_buyer_total_cost_minor": 100,
            "expected_price_bps": 10_000,
            "expected_current_principal_minor": 100,
        },
        id="secondary_purchase",
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("path", "action", "body"), SENSITIVE_ENDPOINTS)
@pytest.mark.parametrize("pin", [None, "", "12345", "abcdef"])
def test_every_sensitive_endpoint_refuses_a_request_without_a_valid_pin(
    path: str,
    action: str,
    body: dict[str, Any],
    pin: str | None,
) -> None:
    investor = get_user_model().objects.create_user(
        email=f"pin-endpoint-{uuid4().hex[:8]}@example.test",
        full_name="Pin Endpoint Investor",
        account_type="natural_person_lender",
        status="active",
    )
    code = issue_sensitive_action_test_code(investor, action)
    payload = {
        **body,
        "sensitive_action_code_id": code.code_id,
        "sensitive_action_code": code.raw_code,
    }
    if pin is not None:
        payload["pin"] = pin
    client = Client()
    client.force_login(investor)

    response = client.post(path, data=payload, content_type="application/json")

    assert response.status_code == 400, response.content
    assert response.json()["pin"] == ["Enter your 6-digit PIN."]
    code_record = apps.get_model("accounts_auth", "SensitiveActionCode").objects.get(
        id=code.code_id
    )
    assert code_record.consumed_at is None
    assert code_record.attempts == 0
