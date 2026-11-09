"""IP of Webby-Soft SRL. U33-DEC-06/07: resale price 0-102% and the capped seller fee.

Seller fee = min(rate x sale price of the principal, rate x outstanding principal), with no
minimum fee and no fee on accrued interest. A principal price of zero is allowed when the
buyer still pays the accrued interest.
"""

from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.test import Client

from backend.apps.secondary_market.models import SecondaryMarketListing
from backend.apps.secondary_market.services import (
    ZERO_TOTAL_SALE_MESSAGE,
    SecondaryMarketValidationError,
    _pricing_snapshot,
)
from backend.apps.secondary_market.tests.test_market_rules_2026_10_16 import (
    _buy,
    buyer,
    freeze_market_clock,
    ops_admin,
    seller,
)
from backend.apps.secondary_market.tests.test_secondary_market import (
    _approve_financial_access,
    _create_funded_loan,
    _create_holding,
    _declare_deposit,
    _list_holding_for_sale,
)

__all__ = ["buyer", "freeze_market_clock", "ops_admin", "seller"]

PRINCIPAL = 10_000_00
ACCRUED = 4_932


@pytest.mark.django_db
def test_premium_sale_caps_the_seller_fee_at_two_percent_of_the_principal(
    ops_admin: Model, seller: Model, buyer: Model
) -> None:
    _approve_financial_access(seller)
    _approve_financial_access(buyer)
    loan = _create_funded_loan(ops_admin)
    holding = _create_holding(ops_admin, seller, loan)
    client = Client()
    client.force_login(cast(Any, seller))
    preview = client.get(
        "/api/v1/marketplace/secondary/listings/pricing-preview/",
        {"holding_id": str(cast(Any, holding).id), "price_bps": "10150"},
    ).json()
    # 2% of 10,150 would be 203; the cap is 2% of the outstanding 10,000.
    assert preview["transfer_price_minor"] == 10_150_00
    assert preview["maker_fee_minor"] == 200_00
    assert preview["minimum_maker_fee_minor"] == 0

    listing = _list_holding_for_sale(seller, holding, price_bps=10_200, key="u33-premium")
    assert listing.transfer_price_minor == 10_200_00
    assert listing.maker_fee_minor == 200_00
    assert listing.minimum_maker_fee_minor == 0

    _declare_deposit(ops_admin, buyer, idempotency_key="u33-premium-deposit")
    purchase = _buy(buyer, listing, "u33-premium-buy")
    # The register example: the buyer pays price + interest, the seller gets that minus 200.
    assert purchase.buyer_total_cost_minor == 10_200_00 + ACCRUED
    assert purchase.maker_fee_minor == 200_00
    assert purchase.taker_fee_minor == 0
    assert purchase.seller_net_proceeds_minor == 10_200_00 + ACCRUED - 200_00


@pytest.mark.django_db
def test_discount_sale_charges_two_percent_of_the_price_and_nothing_on_interest(
    ops_admin: Model, seller: Model
) -> None:
    _approve_financial_access(seller)
    loan = _create_funded_loan(ops_admin)
    holding = _create_holding(ops_admin, seller, loan)
    listing = _list_holding_for_sale(seller, holding, price_bps=8_000, key="u33-discount")
    assert listing.transfer_price_minor == 8_000_00
    assert listing.maker_fee_minor == 160_00
    assert listing.accrued_interest_minor == ACCRUED
    assert listing.seller_net_proceeds_minor == 8_000_00 + ACCRUED - 160_00


@pytest.mark.django_db
def test_principal_price_zero_has_no_fee_and_the_buyer_pays_the_interest(
    ops_admin: Model, seller: Model, buyer: Model
) -> None:
    _approve_financial_access(seller)
    _approve_financial_access(buyer)
    loan = _create_funded_loan(ops_admin)
    holding = _create_holding(ops_admin, seller, loan)
    listing = _list_holding_for_sale(seller, holding, price_bps=0, key="u33-zero")
    assert listing.transfer_price_minor == 0
    assert listing.maker_fee_minor == 0
    assert listing.buyer_total_cost_minor == ACCRUED

    _declare_deposit(ops_admin, buyer, idempotency_key="u33-zero-deposit")
    purchase = _buy(buyer, listing, "u33-zero-buy")
    assert purchase.transfer_price_minor == 0
    assert purchase.maker_fee_minor == 0
    assert purchase.buyer_total_cost_minor == ACCRUED
    assert purchase.seller_net_proceeds_minor == ACCRUED


@pytest.mark.django_db
def test_a_sale_where_nothing_is_paid_is_refused(ops_admin: Model, seller: Model) -> None:
    _approve_financial_access(seller)
    loan = _create_funded_loan(ops_admin)
    holding = _create_holding(ops_admin, seller, loan)
    with pytest.raises(SecondaryMarketValidationError) as refused:
        _pricing_snapshot(
            holding=holding,
            loan=loan,
            price_bps=0,
            as_of_date=date(2026, 1, 16),
            interest_covered_until_override=date(2026, 1, 16),
        )
    assert str(refused.value) == ZERO_TOTAL_SALE_MESSAGE
    # With a principal price above zero the same day is fine.
    pricing = _pricing_snapshot(
        holding=holding,
        loan=loan,
        price_bps=50,
        as_of_date=date(2026, 1, 16),
        interest_covered_until_override=date(2026, 1, 16),
    )
    assert (pricing.buyer_total_cost_minor, pricing.maker_fee_minor) == (50_00, 1_00)


@pytest.mark.django_db
def test_reconciliation_migration_keeps_the_accepted_terms_of_open_listings(
    ops_admin: Model, seller: Model
) -> None:
    migration = import_module(
        "backend.apps.secondary_market.migrations.0013_reconcile_open_listings_u33_dec_06_07"
    )
    _approve_financial_access(seller)
    loan = _create_funded_loan(ops_admin)
    open_holding = _create_holding(ops_admin, seller, loan, idempotency_key="u33-rec-1")
    closed_holding = _create_holding(ops_admin, seller, loan, idempotency_key="u33-rec-2")
    open_listing = _list_holding_for_sale(seller, open_holding, price_bps=9_500, key="u33-rec-o")
    closed = _list_holding_for_sale(seller, closed_holding, price_bps=9_000, key="u33-rec-c")
    # An older listing: 0.25% with a minimum of CHF 30, as accepted then.
    SecondaryMarketListing.objects.filter(pk=open_listing.pk).update(
        maker_fee_bps=25, minimum_maker_fee_minor=30_00, maker_fee_minor=30_00
    )
    SecondaryMarketListing.objects.filter(pk=closed.pk).update(status="cancelled")
    before = SecondaryMarketListing.objects.get(pk=open_listing.pk)

    migration.reconcile_open_listings(apps, None)

    after = SecondaryMarketListing.objects.get(pk=open_listing.pk)
    entry = after.metadata["u33_dec_06_07"]
    assert entry["terms_unchanged"] is True
    assert (entry["accepted_fee_minor"], entry["capped_fee_minor"]) == (30_00, 30_00)
    # Nothing that the seller accepted changes, and the row is not shown as edited.
    assert (after.maker_fee_bps, after.minimum_maker_fee_minor, after.maker_fee_minor) == (
        25,
        30_00,
        30_00,
    )
    assert after.updated_at == before.updated_at
    assert "u33_dec_06_07" not in SecondaryMarketListing.objects.get(pk=closed.pk).metadata
