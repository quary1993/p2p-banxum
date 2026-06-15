from __future__ import annotations

from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.admin_ops.tests.factories import create_user
from backend.apps.platform_core.models import Currency


@pytest.fixture
def admin_user() -> Model:
    return create_user(email="lookup-admin@example.test")


@pytest.fixture
def investor() -> Model:
    return create_user(
        email="alice.lender@example.test",
        account_type="natural_person_lender",
        status="active",
        is_staff=False,
    )


@pytest.mark.django_db
def test_lender_accounts_receive_short_unique_investor_reference(investor: Model) -> None:
    reference = str(cast(Any, investor).investor_reference)

    assert reference.startswith("L")
    assert 8 <= len(reference) <= 10
    assert "-" not in reference


@pytest.mark.django_db
def test_admin_investor_lookup_searches_by_reference_name_email_and_iban(
    admin_user: Model,
    investor: Model,
) -> None:
    chf = Currency.objects.get(code="CHF")
    payout_model = apps.get_model("ledger", "InvestorPayoutInstruction")
    payout_model.objects.create(
        investor_user_id=investor.pk,
        currency=chf,
        destination_iban="CH9300762011623852957",
        destination_account_name="Alice Lender",
        is_verified_usable=True,
        verified_by_admin_id=admin_user.pk,
        verified_at=timezone.now(),
        created_by_admin_id=admin_user.pk,
    )

    client = Client()
    client.force_login(cast(Any, admin_user))

    by_reference = client.get(
        "/api/v1/admin-ops/lookups/investors/",
        {"q": cast(Any, investor).investor_reference},
    )
    assert by_reference.status_code == 200
    assert by_reference.json()[0]["id"] == str(investor.pk)
    assert (
        by_reference.json()[0]["payload"]["investor_reference"]
        == cast(Any, investor).investor_reference
    )

    by_name = client.get("/api/v1/admin-ops/lookups/investors/", {"q": "alice lender"})
    assert by_name.status_code == 200
    assert by_name.json()[0]["id"] == str(investor.pk)

    by_email = client.get("/api/v1/admin-ops/lookups/investors/", {"q": "lender@example"})
    assert by_email.status_code == 200
    assert by_email.json()[0]["id"] == str(investor.pk)

    by_iban = client.get("/api/v1/admin-ops/lookups/investors/", {"iban": "3852957"})
    assert by_iban.status_code == 200
    assert by_iban.json()[0]["id"] == str(investor.pk)
    assert by_iban.json()[0]["payload"]["matched_iban_suffix"] == "623852957"[-8:]


@pytest.mark.django_db
def test_admin_withdrawal_lookup_returns_human_readable_context(
    admin_user: Model,
    investor: Model,
) -> None:
    chf = Currency.objects.get(code="CHF")
    withdrawal_model = apps.get_model("ledger", "InvestorWithdrawalRequest")
    withdrawal = withdrawal_model.objects.create(
        investor_user_id=investor.pk,
        status="requested",
        amount_minor=2500000,
        currency=chf,
        destination_iban="CH5604835012345678009",
        destination_account_name="Alice Lender",
        requested_by_user_id=investor.pk,
        requested_at=timezone.now(),
        idempotency_key="lookup-withdrawal",
    )

    client = Client()
    client.force_login(cast(Any, admin_user))

    response = client.get(
        "/api/v1/admin-ops/lookups/withdrawal-requests/",
        {"q": "alice", "status": "requested"},
    )

    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["id"] == str(withdrawal.pk)
    assert "Alice" in payload["label"]
    assert payload["payload"]["iban_suffix"] == "345678009"[-8:]
    assert payload["payload"]["amount_minor"] == 2500000
