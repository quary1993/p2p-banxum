# IP of Webby-Soft SRL.
"""C03 (Vlad, 2026-11-17): a loan with a due, unpaid installment is closed to new buyers.

From the due date itself until the payment is recorded, other investors do not see the loan's
resale listings and cannot buy them; the seller still sees his listing, marked as paused
("Pending"), and cannot list again. The listings return when the payment is recorded.
"""

from __future__ import annotations

from datetime import date, datetime
from importlib import import_module
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps
from django.db.models import Model

import backend.apps.secondary_market.services as secondary_services
from backend.apps.secondary_market.services import (
    DUE_INSTALLMENT_LISTING_MESSAGE,
    DUE_INSTALLMENT_PURCHASE_MESSAGE,
    PurchaseSecondaryMarketListingCommand,
    SecondaryMarketValidationError,
    get_active_secondary_market_listing_detail,
    list_active_secondary_market_listings,
    preview_secondary_market_listing_pricing,
    purchase_secondary_market_listing,
)
from backend.apps.secondary_market.tests.test_secondary_market import (  # noqa: F401
    _approve_financial_access,
    _create_current_installment,
    _create_funded_loan,
    _create_holding,
    _create_purchase_acceptance,
    _expected_terms,
    _list_holding_for_sale,
    _review_purchase,
    _sensitive_code_payload,
    investor,
    other_investor,
)

DUE_DATE = date(2026, 1, 20)


def _set_clock(monkeypatch: pytest.MonkeyPatch, day: date) -> None:
    moment = datetime(day.year, day.month, day.day, 12, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr(secondary_services, "now_utc", lambda: moment)
    portal = import_module("backend.apps.investor_portal.services")
    monkeypatch.setattr(portal, "now_utc", lambda: moment)


def _record_installment_payment(admin_user: Model, loan: Model) -> None:
    servicing = import_module("backend.apps.servicing.services")
    servicing.record_borrower_repayment(
        servicing.RecordBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(cast(Any, loan).pk),
            amount_minor=2_300_00,
            booking_date=DUE_DATE,
            value_date=DUE_DATE,
            collection_account_identifier="GARANTA-CHF",
            payer_name="Secondary Borrower AG",
            payer_account_identifier="CH22BORROWER",
            bank_reference="BANK-c03-installment",
            payment_reference=f"LOAN-{cast(Any, loan).pk}",
            evidence_reference="statement:c03-installment",
            idempotency_key="c03-installment-payment",
        )
    )


@pytest.mark.django_db
def test_listings_pause_from_the_due_date_until_the_payment_is_recorded(
    admin_user: Model,
    investor: Model,  # noqa: F811
    other_investor: Model,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    _create_current_installment(loan, due_date=DUE_DATE)
    apps.get_model("loans", "LoanInstallment").objects.create(
        loan=loan,
        schedule_version=cast(Any, loan).schedule_version,
        installment_number=2,
        due_date=date(2026, 2, 16),
        principal_minor=28_000_00,
        interest_minor=280_00,
        total_minor=28_280_00,
        metadata={},
    )
    holding = _create_holding(admin_user, investor, loan)

    # The day before the due date the listing is made and buyers see it.
    _set_clock(monkeypatch, date(2026, 1, 19))
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="c03-listing")
    review = _review_purchase(other_investor, listing)
    purchase_acceptance = _create_purchase_acceptance(
        other_investor, listing, idempotency_key="c03-purchase-acceptance", review=review
    )
    buyer_view = list_active_secondary_market_listings(actor=other_investor)
    assert [str(row.pk) for row in buyer_view] == [str(listing.pk)]
    assert cast(Any, buyer_view[0]).paused_for_due_installment is False

    # On the due date, before the payment is recorded: closed to new buyers.
    _set_clock(monkeypatch, DUE_DATE)
    assert list_active_secondary_market_listings(actor=other_investor) == []
    with pytest.raises(SecondaryMarketValidationError, match="not available"):
        get_active_secondary_market_listing_detail(
            actor=other_investor, listing_id=str(listing.pk)
        )
    with pytest.raises(SecondaryMarketValidationError) as refused:
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.pk),
                document_acceptance_id=str(purchase_acceptance.pk),
                idempotency_key="c03-purchase",
                **_expected_terms(review),
                **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
            )
        )
    assert str(refused.value) == DUE_INSTALLMENT_PURCHASE_MESSAGE

    # The seller still sees his listing, paused, and cannot list or price a new sale.
    seller_view = list_active_secondary_market_listings(actor=investor)
    assert [str(row.pk) for row in seller_view] == [str(listing.pk)]
    assert cast(Any, seller_view[0]).paused_for_due_installment is True
    seller_detail = get_active_secondary_market_listing_detail(
        actor=investor, listing_id=str(listing.pk)
    )
    assert seller_detail["paused_for_due_installment"] is True
    with pytest.raises(SecondaryMarketValidationError) as preview_refused:
        preview_secondary_market_listing_pricing(
            actor=investor, holding_id=str(cast(Any, holding).pk), price_bps=10_000
        )
    assert str(preview_refused.value) == DUE_INSTALLMENT_LISTING_MESSAGE
    portal = import_module("backend.apps.investor_portal.services")
    activity = portal.get_secondary_market_activity(actor=investor)
    assert activity["listings"][0]["paused_for_due_installment"] is True

    # The payment is recorded: the listing is back for buyers.
    _record_installment_payment(admin_user, loan)
    buyer_view = list_active_secondary_market_listings(actor=other_investor)
    assert [str(row.pk) for row in buyer_view] == [str(listing.pk)]
    assert cast(Any, buyer_view[0]).paused_for_due_installment is False
    activity = portal.get_secondary_market_activity(actor=investor)
    assert activity["listings"][0]["paused_for_due_installment"] is False
