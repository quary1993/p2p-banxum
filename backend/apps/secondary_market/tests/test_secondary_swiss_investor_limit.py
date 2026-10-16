# IP of Webby-Soft SRL.
"""Secondary market and the Swiss-borrower investor limit (MKT-DEC-028, 2026-10-16).

A whole-holding purchase by a new investor must not raise a Swiss-borrower loan's
investor count above the limit. The buyer takes the seller's place when the seller
sells their last holding of the loan.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.db.models import Model
from django.test import Client

from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.investor_limit import (
    SWISS_BORROWER_MAX_INVESTORS_SETTING,
    SWISS_INVESTOR_LIMIT_CODE,
)
from backend.apps.platform_core.services.settings import (
    SetPlatformSettingCommand,
    set_platform_setting,
)
from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code
from backend.apps.secondary_market import services as secondary_services
from backend.apps.secondary_market.services import (
    PurchaseSecondaryMarketListingCommand,
    SecondaryMarketSwissInvestorLimitError,
    purchase_secondary_market_listing,
)
from backend.apps.secondary_market.tests.test_secondary_market import (
    _approve_financial_access,
    _create_funded_loan,
    _create_holding,
    _create_purchase_acceptance,
    _declare_deposit,
    _expected_terms,
    _list_holding_for_sale,
    _review_purchase,
    admin_user,
    freeze_secondary_market_clock,
)

# Fixtures shared with the secondary-market tests (the clock freeze is autouse).
__all__ = ["admin_user", "freeze_secondary_market_clock"]

FULL_MESSAGE = "This loan to a Swiss company already has the maximum of {} investors."


def loan_investor_limit(loan: Model) -> Any:
    # The investor limit selectors live in a peer module: reached at run time.
    return import_module("backend.apps.marketplace_primary.investor_limit").loan_investor_limit(
        loan
    )


def _lender(name: str) -> Model:
    user_model: Any = get_user_model()
    lender = cast(
        Model,
        user_model.objects.create_user(
            email=f"secondary-swiss-{name}@example.test",
            full_name=f"Secondary Swiss {name}",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )
    _approve_financial_access(lender)
    return lender


def _set_limit(value: int) -> None:
    set_platform_setting(
        SetPlatformSettingCommand(
            actor=ActorRef.system(),
            key=SWISS_BORROWER_MAX_INVESTORS_SETTING,
            value=value,
            value_type="integer",
            reason="Swiss-borrower investor limit test.",
        )
    )


def _holding(admin_user: Model, investor: Model, loan: Model, key: str) -> Model:
    return _create_holding(
        admin_user,
        investor,
        loan,
        current_principal_minor=5_000_00,
        idempotency_key=f"secondary-swiss-{key}",
    )


def _prepared_purchase(
    admin_user: Model,
    buyer: Model,
    listing: Any,
    key: str,
) -> PurchaseSecondaryMarketListingCommand:
    _declare_deposit(
        admin_user,
        buyer,
        amount_minor=10_000_00,
        idempotency_key=f"{key}-deposit",
    )
    review = _review_purchase(buyer, listing)
    acceptance = _create_purchase_acceptance(
        buyer,
        listing,
        idempotency_key=f"{key}-acceptance",
        review=review,
    )
    code = issue_sensitive_action_test_code(buyer, "secondary_market_purchase")
    return PurchaseSecondaryMarketListingCommand(
        actor=buyer,
        listing_id=str(listing.id),
        document_acceptance_id=str(acceptance.pk),
        idempotency_key=key,
        sensitive_action_code_id=code.code_id,
        sensitive_action_code=code.raw_code,
        pin=code.pin,
        **_expected_terms(review),
    )


@pytest.mark.django_db
def test_new_buyer_takes_the_place_of_a_seller_who_sells_the_last_holding(
    admin_user: Model,
) -> None:
    loan = _create_funded_loan(admin_user)
    seller, holder, buyer = _lender("last-seller"), _lender("last-holder"), _lender("last-buyer")
    _set_limit(2)
    holding = _holding(admin_user, seller, loan, "last-seller")
    _holding(admin_user, holder, loan, "last-holder")
    listing = _list_holding_for_sale(seller, holding, price_bps=10_000, key="secondary-swiss-last")

    purchase = purchase_secondary_market_listing(
        _prepared_purchase(admin_user, buyer, listing, "secondary-swiss-last-buy")
    )

    assert str(cast(Any, purchase).buyer_user_id) == str(buyer.pk)
    limit = loan_investor_limit(loan)
    assert limit.investor_ids == {str(holder.pk), str(buyer.pk)}
    assert limit.places_left == 0


@pytest.mark.django_db
def test_new_buyer_is_refused_when_the_seller_stays_and_no_place_is_left(
    client: Client,
    admin_user: Model,
) -> None:
    loan = _create_funded_loan(admin_user)
    seller, holder, buyer = _lender("stay-seller"), _lender("stay-holder"), _lender("stay-buyer")
    _set_limit(2)
    sold = _holding(admin_user, seller, loan, "stay-seller-1")
    _holding(admin_user, seller, loan, "stay-seller-2")
    _holding(admin_user, holder, loan, "stay-holder")
    listing = _list_holding_for_sale(seller, sold, price_bps=10_000, key="secondary-swiss-stay")
    command = _prepared_purchase(admin_user, buyer, listing, "secondary-swiss-stay-buy")

    with pytest.raises(SecondaryMarketSwissInvestorLimitError) as refused:
        purchase_secondary_market_listing(command)
    assert str(refused.value) == FULL_MESSAGE.format(2)
    # The early check refused before the email code was used.
    code_model = apps.get_model("accounts_auth", "SensitiveActionCode")
    assert code_model.objects.get(id=command.sensitive_action_code_id).consumed_at is None
    # The authoritative check under the loan lock refuses too.
    with pytest.raises(SecondaryMarketSwissInvestorLimitError):
        secondary_services._purchase_secondary_market_listing_after_sensitive_code(command)

    client.force_login(cast(Any, buyer))
    response = client.post(
        f"/api/v1/marketplace/secondary/listings/{listing.id}/purchase/",
        data={
            "document_acceptance_id": command.document_acceptance_id,
            "risk_acknowledgement_accepted": False,
            "idempotency_key": "secondary-swiss-stay-api",
            "expected_buyer_total_cost_minor": command.expected_buyer_total_cost_minor,
            "expected_price_bps": command.expected_price_bps,
            "expected_current_principal_minor": command.expected_current_principal_minor,
            "sensitive_action_code_id": command.sensitive_action_code_id,
            "sensitive_action_code": command.sensitive_action_code,
            "pin": command.pin,
        },
        content_type="application/json",
    )
    assert response.status_code == 409, response.content
    assert response.json() == {"detail": FULL_MESSAGE.format(2), "code": SWISS_INVESTOR_LIMIT_CODE}

    # An existing investor of the loan needs no new place.
    purchase_secondary_market_listing(
        _prepared_purchase(admin_user, holder, listing, "secondary-swiss-holder")
    )
    assert loan_investor_limit(loan).investors_count == 2


@pytest.mark.django_db
def test_setting_zero_and_other_borrowers_do_not_limit_secondary_buyers(
    admin_user: Model,
) -> None:
    loan = _create_funded_loan(admin_user)
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    other_loan = _create_funded_loan(admin_user)
    borrower_model.objects.filter(pk=cast(Any, other_loan).borrower_id).update(country="Austria")
    seller, buyer = _lender("off-seller"), _lender("off-buyer")
    _set_limit(1)
    sold = _holding(admin_user, seller, loan, "off-1")
    _holding(admin_user, seller, loan, "off-2")
    other_sold = _holding(admin_user, seller, other_loan, "off-3")
    _holding(admin_user, seller, other_loan, "off-4")

    other_listing = _list_holding_for_sale(
        seller, other_sold, price_bps=10_000, key="secondary-swiss-off-other"
    )
    purchase_secondary_market_listing(
        _prepared_purchase(admin_user, buyer, other_listing, "secondary-swiss-off-other-buy")
    )

    _set_limit(0)
    listing = _list_holding_for_sale(seller, sold, price_bps=10_000, key="secondary-swiss-off")
    purchase_secondary_market_listing(
        _prepared_purchase(admin_user, buyer, listing, "secondary-swiss-off-buy")
    )
    assert loan_investor_limit(loan).max_investors is None


def _race_setup(admin_user: Model) -> tuple[Model, list[PurchaseSecondaryMarketListingCommand]]:
    """Two sellers who keep another holding each; one place left; two new buyers."""
    loan = _create_funded_loan(admin_user)
    _set_limit(3)
    commands: list[PurchaseSecondaryMarketListingCommand] = []
    for index in range(2):
        seller = _lender(f"race-seller-{index}")
        sold = _holding(admin_user, seller, loan, f"race-{index}-sold")
        _holding(admin_user, seller, loan, f"race-{index}-kept")
        listing = _list_holding_for_sale(
            seller, sold, price_bps=10_000, key=f"secondary-swiss-race-{index}"
        )
        buyer = _lender(f"race-buyer-{index}")
        commands.append(
            _prepared_purchase(admin_user, buyer, listing, f"secondary-swiss-race-buy-{index}")
        )
    assert loan_investor_limit(loan).places_left == 1
    return loan, commands


@pytest.mark.django_db
def test_two_new_buyers_for_the_last_place_one_after_the_other(admin_user: Model) -> None:
    loan, commands = _race_setup(admin_user)

    purchase_secondary_market_listing(commands[0])
    with pytest.raises(SecondaryMarketSwissInvestorLimitError):
        purchase_secondary_market_listing(commands[1])

    assert loan_investor_limit(loan).investors_count == 3


@pytest.mark.django_db(transaction=True)
def test_postgres_two_new_buyers_racing_for_the_last_place_cannot_both_get_in() -> None:
    """Both purchases count under the loan row lock, so only one buyer gets in.

    Only PostgreSQL enforces row locks; SQLite ignores select_for_update.
    """
    if connection.vendor != "postgresql":
        pytest.skip("Row-lock race check requires PostgreSQL.")
    # Transactional tests flush reference rows left by migrations/other tests.
    call_command("seed_reference_data", verbosity=0)
    user_model: Any = get_user_model()
    admin = user_model.objects.create_user(
        email="secondary-admin@example.test",
        password="AdminPass123!",
        full_name="Secondary Admin",
        account_type="admin",
        status="active",
        is_staff=True,
    )
    loan, commands = _race_setup(admin)
    barrier = threading.Barrier(2)

    def buy(command: PurchaseSecondaryMarketListingCommand) -> str:
        close_old_connections()
        try:
            actor = user_model.objects.get(pk=command.actor.pk)
            barrier.wait(timeout=10)
            # Both buyers pass the early check; the settlement repeats it under the lock.
            secondary_services._purchase_secondary_market_listing_after_sensitive_code(
                replace(command, actor=actor)
            )
            return "bought"
        except SecondaryMarketSwissInvestorLimitError:
            return "refused"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(buy, commands))

    assert results == ["bought", "refused"]
    assert loan_investor_limit(loan).investors_count == 3
