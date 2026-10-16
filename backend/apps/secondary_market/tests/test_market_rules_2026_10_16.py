"""IP of Webby-Soft SRL. Secondary-market owner decisions of 2026-10-16.

Row 2: seller (maker) fee 2% of the price. Row 3: no buyer (taker) fee. Row 4: the sale
price is par or a discount, never a premium.
"""

from __future__ import annotations

from datetime import date, datetime
from importlib import import_module
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client

from backend.apps.platform_core.models import (
    AuditEvent,
    OutboxMessage,
    PlatformSetting,
    PlatformSettingVersion,
)
from backend.apps.secondary_market.models import (
    SecondaryMarketListing,
    SecondaryMarketListingEvent,
    SecondaryMarketListingEventType,
    SecondaryMarketListingStatus,
)
from backend.apps.secondary_market.services import (
    CreateSecondaryMarketListingCommand,
    EditSecondaryMarketListingCommand,
    PurchaseSecondaryMarketListingCommand,
    SecondaryMarketValidationError,
    create_secondary_market_listing,
    edit_secondary_market_listing,
    get_active_secondary_market_listing_detail,
    purchase_secondary_market_listing,
    refresh_open_secondary_market_listings_for_loan,
)
from backend.apps.secondary_market.tests.test_secondary_market import (
    _accept_terms,
    _approve_financial_access,
    _create_funded_loan,
    _create_holding,
    _create_listing_acceptance,
    _create_purchase_acceptance,
    _declare_deposit,
    _expected_terms,
    _list_holding_for_sale,
    _publish_terms,
    _review_purchase,
    _sensitive_code_payload,
)

ABOVE_PAR = "The sale price can be at most 100% (par)."


@pytest.fixture(autouse=True)
def freeze_market_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.apps.secondary_market.services as secondary_services

    fixed_now = datetime(2026, 1, 16, 12, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr(secondary_services, "now_utc", lambda: fixed_now)


def _user(email: str, **extra: Any) -> Model:
    defaults: dict[str, Any] = {
        "full_name": "Market Rules",
        "account_type": "natural_person_lender",
        "status": "active",
    }
    return cast(Model, get_user_model().objects.create_user(email=email, **{**defaults, **extra}))


@pytest.fixture
def ops_admin() -> Model:
    return _user(
        "rules-admin@example.test",
        password="AdminPass123!",
        account_type="admin",
        is_staff=True,
    )


@pytest.fixture
def seller() -> Model:
    return _user("rules-seller@example.test")


@pytest.fixture
def buyer() -> Model:
    return _user("rules-buyer@example.test")


def _set_fee_rows(maker_bps: int, taker_bps: int) -> None:
    for key, value in (
        ("secondary_market.maker_fee_bps", maker_bps),
        ("secondary_market.taker_fee_bps", taker_bps),
    ):
        PlatformSetting.objects.update_or_create(
            key=key, defaults={"value": value, "value_type": "integer"}
        )


def _buy(buyer: Model, listing: Any, key: str) -> Any:
    review = _review_purchase(buyer, listing)
    acceptance = _create_purchase_acceptance(
        buyer, listing, review=review, idempotency_key=f"{key}-accept"
    )
    return purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=buyer,
            listing_id=str(listing.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=key,
            **_expected_terms(review),
            **_sensitive_code_payload(buyer, "secondary_market_purchase"),
        )
    )


@pytest.mark.django_db
def test_new_listing_and_purchase_show_a_two_percent_seller_fee_and_no_buyer_fee(
    ops_admin: Model,
    seller: Model,
    buyer: Model,
) -> None:
    _approve_financial_access(seller)
    _approve_financial_access(buyer)
    loan = _create_funded_loan(ops_admin)
    holding = _create_holding(ops_admin, seller, loan)
    client = Client()
    client.force_login(cast(Any, seller))
    preview = client.get(
        "/api/v1/marketplace/secondary/listings/pricing-preview/",
        {"holding_id": str(cast(Any, holding).id), "price_bps": "9500"},
    ).json()
    assert preview["maker_fee_bps"] == 200
    assert preview["maker_fee_minor"] == 19_000
    assert preview["taker_fee_minor"] == 0

    listing = _list_holding_for_sale(seller, holding, price_bps=9_500, key="rules-fee-list")
    assert (listing.maker_fee_bps, listing.maker_fee_minor) == (200, 19_000)
    assert (listing.taker_fee_bps, listing.taker_fee_minor) == (0, 0)

    detail = get_active_secondary_market_listing_detail(actor=buyer, listing_id=str(listing.id))
    assert detail["taker_fee_bps"] == 0
    assert detail["taker_fee_minor"] == 0
    assert detail["buyer_total_cost_minor"] == (
        detail["transfer_price_minor"] + detail["accrued_interest_minor"]
    )

    _declare_deposit(ops_admin, buyer, idempotency_key="rules-fee-deposit")
    purchase = _buy(buyer, listing, "rules-fee-buy")
    assert purchase.maker_fee_bps == 200
    assert purchase.maker_fee_minor == 19_000
    assert purchase.taker_fee_minor == 0
    assert purchase.seller_net_proceeds_minor == 9_500_00 + 4_932 - 19_000
    assert purchase.buyer_total_cost_minor == 9_500_00 + 4_932
    buyer_email = OutboxMessage.objects.get(topic="email.secondary_market_purchase_confirmation")
    assert "Taker fee: CHF 0.00." in buyer_email.payload["body_text"]


@pytest.mark.django_db
def test_open_listing_keeps_its_seller_fee_until_a_refresh_recomputes_it(
    ops_admin: Model,
    seller: Model,
    buyer: Model,
) -> None:
    _approve_financial_access(seller)
    _approve_financial_access(buyer)
    loan = _create_funded_loan(ops_admin)
    sold_holding = _create_holding(ops_admin, seller, loan, idempotency_key="rules-old-1")
    refreshed_holding = _create_holding(ops_admin, seller, loan, idempotency_key="rules-old-2")
    # Listed under the old defaults (0.25% seller, 0.75% buyer).
    _set_fee_rows(25, 75)
    sold = _list_holding_for_sale(seller, sold_holding, price_bps=9_500, key="rules-old-sold")
    assert (sold.maker_fee_bps, sold.maker_fee_minor) == (25, 2_375)

    # The data migration moves the seeded rows to the new defaults.
    migration = import_module(
        "backend.apps.secondary_market.migrations.0010_secondary_fee_defaults_2026_10_16"
    )
    migration.apply_new_fee_defaults(apps, None)
    refreshed = _list_holding_for_sale(
        seller, refreshed_holding, price_bps=9_500, key="rules-old-refreshed"
    )
    assert refreshed.maker_fee_bps == 200

    # The buyer pays the current buyer fee (none); the seller pays the fee they listed with.
    _declare_deposit(ops_admin, buyer, idempotency_key="rules-old-deposit")
    purchase = _buy(buyer, sold, "rules-old-buy")
    assert purchase.taker_fee_minor == 0
    assert purchase.maker_fee_bps == 25
    assert purchase.maker_fee_minor == 2_375
    assert purchase.seller_net_proceeds_minor == 9_500_00 + 4_932 - 2_375

    # A servicing refresh recomputes every fee with the current settings, as before.
    SecondaryMarketListing.objects.filter(pk=refreshed.pk).update(
        maker_fee_bps=25, maker_fee_minor=2_375
    )
    refresh_open_secondary_market_listings_for_loan(
        actor=ops_admin,
        loan=loan,
        as_of_date=date(2026, 1, 16),
        source_type="borrower_repayment_event",
        source_id="rules-refresh",
    )
    refreshed.refresh_from_db()
    assert refreshed.status == SecondaryMarketListingStatus.ACTIVE
    assert (refreshed.maker_fee_bps, refreshed.maker_fee_minor) == (200, 19_000)


@pytest.mark.django_db
def test_fee_default_migration_changes_only_rows_that_hold_the_old_default() -> None:
    migration = import_module(
        "backend.apps.secondary_market.migrations.0010_secondary_fee_defaults_2026_10_16"
    )
    # Nothing seeded: nothing to change.
    migration.apply_new_fee_defaults(apps, None)
    assert not PlatformSetting.objects.filter(key__startswith="secondary_market.").exists()

    PlatformSetting.objects.create(
        key="secondary_market.maker_fee_bps", value=25, value_type="integer", current_version=1
    )
    PlatformSetting.objects.create(
        key="secondary_market.taker_fee_bps", value=50, value_type="integer", current_version=3
    )
    migration.apply_new_fee_defaults(apps, None)
    migration.apply_new_fee_defaults(apps, None)

    maker = PlatformSetting.objects.get(key="secondary_market.maker_fee_bps")
    taker = PlatformSetting.objects.get(key="secondary_market.taker_fee_bps")
    assert (maker.value, maker.current_version) == (200, 2)
    assert "2%" in maker.description
    # A value someone configured on purpose is kept.
    assert (taker.value, taker.current_version) == (50, 3)
    version = PlatformSettingVersion.objects.get(key="secondary_market.maker_fee_bps")
    assert (version.version, version.value, version.changed_by_type) == (2, 200, "system")
    assert "Owner decision 2026-10-16" in version.reason
    assert not PlatformSettingVersion.objects.filter(key="secondary_market.taker_fee_bps").exists()
    audit = AuditEvent.objects.get(target_id="secondary_market.maker_fee_bps")
    assert audit.action == "platform_setting.updated"
    assert audit.metadata["previous_value"] == 25
    assert audit.metadata["value"] == 200

    PlatformSetting.objects.filter(key="secondary_market.taker_fee_bps").update(value=75)
    migration.apply_new_fee_defaults(apps, None)
    assert PlatformSetting.objects.get(key="secondary_market.taker_fee_bps").value == 0


@pytest.mark.django_db
def test_sale_price_above_par_is_refused_with_a_clear_message(
    ops_admin: Model,
    seller: Model,
    buyer: Model,
) -> None:
    superadmin = cast(
        Model,
        get_user_model().objects.create_superuser(
            email="rules-superadmin@example.test",
            password="AdminPass123!",
            full_name="Rules Superadmin",
        ),
    )
    _approve_financial_access(seller)
    _approve_financial_access(buyer)
    loan = _create_funded_loan(ops_admin)
    holding = _create_holding(ops_admin, seller, loan)
    holding_id = str(cast(Any, holding).id)
    client = Client()
    client.force_login(cast(Any, seller))

    preview = client.get(
        "/api/v1/marketplace/secondary/listings/pricing-preview/",
        {"holding_id": holding_id, "price_bps": "10001"},
    )
    assert preview.status_code == 400
    assert preview.json() == {"detail": ABOVE_PAR}

    acceptance = _create_listing_acceptance(seller, holding, idempotency_key="rules-par-accept")
    listing_code = _sensitive_code_payload(seller, "secondary_market_listing")
    created = client.post(
        "/api/v1/marketplace/secondary/listings/",
        {
            "holding_id": holding_id,
            "price_bps": 10_100,
            "document_acceptance_id": str(acceptance.pk),
            "idempotency_key": "rules-par-api",
            **listing_code,
        },
        content_type="application/json",
    )
    assert created.status_code == 400
    assert created.json() == {"detail": ABOVE_PAR}

    documents = import_module("backend.apps.documents.services")
    version = _publish_terms(superadmin, "secondary_market_listing")
    with pytest.raises(documents.DocumentValidationError, match=r"at most 100% \(par\)"):
        _accept_terms(
            seller,
            version,
            category="secondary_market_listing",
            context_type="secondary_market_listing",
            context_id=holding_id,
            snapshot={"price_bps": 10_500},
            key="rules-par-terms",
        )

    # Exactly par is allowed (with the same email code: the refusal did not use it up).
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=seller,
            holding_id=holding_id,
            price_bps=10_000,
            document_acceptance_id=str(
                _create_listing_acceptance(seller, holding, idempotency_key="rules-par-ok").pk
            ),
            idempotency_key="rules-par-list",
            **listing_code,
        )
    )
    assert listing.transfer_price_minor == listing.current_principal_minor

    # An edit above par is refused and changes nothing.
    edit_acceptance = _create_listing_acceptance(seller, holding, idempotency_key="rules-par-ed")
    with pytest.raises(SecondaryMarketValidationError, match=r"at most 100% \(par\)"):
        edit_secondary_market_listing(
            EditSecondaryMarketListingCommand(
                actor=seller,
                listing_id=str(listing.id),
                price_bps=10_050,
                document_acceptance_id=str(edit_acceptance.pk),
                idempotency_key="rules-par-edit",
                **_sensitive_code_payload(seller, "secondary_market_listing"),
            )
        )
    listing.refresh_from_db()
    assert listing.price_bps == 10_000

    # A listing priced above par before the rule can never be bought.
    SecondaryMarketListing.objects.filter(pk=listing.pk).update(price_bps=10_500)
    listing.refresh_from_db()
    _declare_deposit(ops_admin, buyer, idempotency_key="rules-par-deposit")
    acceptance_for_buyer = _create_purchase_acceptance(
        buyer,
        listing,
        review={"price_bps": 10_500},
        idempotency_key="rules-par-buy-accept",
    )
    with pytest.raises(SecondaryMarketValidationError, match=r"at most 100% \(par\)"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=buyer,
                listing_id=str(listing.id),
                document_acceptance_id=str(acceptance_for_buyer.pk),
                idempotency_key="rules-par-buy",
                expected_buyer_total_cost_minor=1,
                expected_price_bps=10_500,
                expected_current_principal_minor=10_000_00,
                **_sensitive_code_payload(buyer, "secondary_market_purchase"),
            )
        )


@pytest.mark.django_db
def test_refresh_after_a_repayment_keeps_a_par_price_valid(
    ops_admin: Model,
    seller: Model,
) -> None:
    _approve_financial_access(seller)
    loan = _create_funded_loan(ops_admin)
    holding = _create_holding(ops_admin, seller, loan)
    listing = _list_holding_for_sale(seller, holding, price_bps=10_000, key="rules-par-refresh")
    cast(Any, holding).current_principal_minor = 7_500_00
    holding.save(update_fields=["current_principal_minor", "updated_at"])

    refresh_open_secondary_market_listings_for_loan(
        actor=ops_admin,
        loan=loan,
        as_of_date=date(2026, 1, 16),
        source_type="borrower_repayment_event",
        source_id="rules-par-repayment",
    )
    listing.refresh_from_db()
    assert listing.status == SecondaryMarketListingStatus.ACTIVE
    assert listing.price_bps == 10_000
    assert listing.transfer_price_minor == listing.current_principal_minor == 7_500_00


@pytest.mark.django_db
def test_par_rule_migration_cancels_open_listings_above_par_with_a_seller_notice(
    ops_admin: Model,
    seller: Model,
) -> None:
    migration = import_module(
        "backend.apps.secondary_market.migrations.0011_cancel_listings_above_par"
    )
    _approve_financial_access(seller)
    loan = _create_funded_loan(ops_admin)
    holdings = [
        _create_holding(ops_admin, seller, loan, idempotency_key=f"rules-mig-{index}")
        for index in range(3)
    ]
    at_par = _list_holding_for_sale(seller, holdings[0], price_bps=10_000, key="rules-mig-par")
    discount = _list_holding_for_sale(seller, holdings[1], price_bps=9_000, key="rules-mig-disc")
    premium = _list_holding_for_sale(seller, holdings[2], price_bps=10_000, key="rules-mig-prem")
    # Listed at a premium before the rule.
    SecondaryMarketListing.objects.filter(pk=premium.pk).update(price_bps=10_250)
    journal_model = apps.get_model("ledger", "LedgerJournalEntry")
    journals_before = journal_model.objects.count()

    migration.cancel_listings_above_par(apps, None)
    migration.cancel_listings_above_par(apps, None)

    for listing in (at_par, discount, premium):
        listing.refresh_from_db()
    assert at_par.status == SecondaryMarketListingStatus.ACTIVE
    assert discount.status == SecondaryMarketListingStatus.ACTIVE
    assert premium.status == SecondaryMarketListingStatus.CANCELLED
    assert premium.cancelled_by_user_id is None
    assert premium.listed_at is None
    assert "above par" in premium.cancellation_reason
    assert premium.metadata["par_rule_migration"]["price_bps"] == 10_250
    assert journal_model.objects.count() == journals_before
    holdings[2].refresh_from_db()
    assert cast(Any, holdings[2]).status == "active"
    event = SecondaryMarketListingEvent.objects.get(
        listing=premium,
        event_type=SecondaryMarketListingEventType.AUTO_CANCELLED,
    )
    assert event.actor_account_type == "system"
    assert event.note == premium.cancellation_reason
    notices = OutboxMessage.objects.filter(
        topic="email.secondary_market_listing_status",
        idempotency_key__endswith=":par-rule-migration",
    )
    assert [cast(Any, notice).payload["metadata"]["listing_id"] for notice in notices] == [
        str(premium.id)
    ]
    assert cast(Any, notices.get()).payload["email"] == "rules-seller@example.test"
