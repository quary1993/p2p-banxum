from __future__ import annotations

from datetime import date, datetime, time
from importlib import import_module
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.platform_core.models import AuditEvent, Currency, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.secondary_market.models import (
    SecondaryMarketListingEvent,
    SecondaryMarketListingEventType,
    SecondaryMarketListingStatus,
    SecondaryMarketPurchase,
)
from backend.apps.secondary_market.services import (
    ApproveSecondaryMarketListingCommand,
    CreateSecondaryMarketListingCommand,
    PurchaseSecondaryMarketListingCommand,
    RejectSecondaryMarketListingCommand,
    SecondaryMarketAuthorizationError,
    SecondaryMarketValidationError,
    approve_secondary_market_listing,
    create_secondary_market_listing,
    list_active_secondary_market_listings,
    purchase_secondary_market_listing,
    reject_secondary_market_listing,
)


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="secondary-admin@example.test",
            password="AdminPass123!",
            full_name="Secondary Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="secondary-investor@example.test",
            full_name="Secondary Investor",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


@pytest.fixture
def other_investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="secondary-other@example.test",
            full_name="Secondary Other",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


@pytest.fixture(autouse=True)
def freeze_secondary_market_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.apps.secondary_market.services as secondary_services

    fixed_now = datetime(2026, 1, 16, 12, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr(secondary_services, "now_utc", lambda: fixed_now)


def _approve_financial_access(investor: Model) -> None:
    now = timezone.now()
    cast(Any, investor).phone_verified_at = now
    investor.save(update_fields=["phone_verified_at"])
    kyc_case_model = apps.get_model("kyc_compliance", "KycVerificationCase")
    kyc_case_model.objects.update_or_create(
        user_id=investor.pk,
        defaults={
            "subject_reference": f"user:{investor.pk}",
            "provider_environment": "test",
            "workflow_id": "test-workflow",
            "vendor_data": f"user:{investor.pk}",
            "status": "approved",
            "decision_at": now,
        },
    )


def _create_borrower(admin_user: Model) -> Model:
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    return cast(
        Model,
        borrower_model.objects.create(
            legal_name="Secondary Borrower AG",
            year_founded=2014,
            entity_type="swiss_company",
            kyb_status="approved",
            country="CH",
            created_by_admin_id=admin_user.pk,
        ),
    )


def _create_funded_loan(
    admin_user: Model,
    *,
    status: str = "funded",
    principal_minor: int = 30_000_00,
) -> Model:
    borrower = _create_borrower(admin_user)
    loan_model = apps.get_model("loans", "Loan")
    currency = Currency.objects.get(code="CHF")
    return cast(
        Model,
        loan_model.objects.create(
            borrower=borrower,
            status=status,
            title="Secondary bridge loan",
            investor_summary="Short real-estate backed bridge facility.",
            purpose="bridge_financing",
            principal_minor=principal_minor,
            currency=currency,
            interest_rate_bps=1200,
            term_months=12,
            repayment_type="equal_installments",
            funding_deadline=date(2025, 12, 31),
            first_payment_date=date(2026, 2, 1),
            collateral_type="real_estate",
            collateral_value_minor=50_000_00,
            risk_rating="BBB",
            borrower_success_fee_bps=200,
            total_scheduled_principal_minor=principal_minor,
            total_scheduled_interest_minor=2_000_00,
            committed_principal_minor=principal_minor,
            created_by_admin_id=admin_user.pk,
            published_at=timezone.now(),
        ),
    )


def _create_current_installment(loan: Model, *, due_date: date = date(2026, 1, 1)) -> Model:
    installment_model = apps.get_model("loans", "LoanInstallment")
    loan_ref = cast(Any, loan)
    return cast(
        Model,
        installment_model.objects.create(
            loan=loan,
            schedule_version=loan_ref.schedule_version,
            installment_number=1,
            due_date=due_date,
            principal_minor=2_000_00,
            interest_minor=300_00,
            total_minor=2_300_00,
            metadata={},
        ),
    )


def _create_holding(
    admin_user: Model,
    investor: Model,
    loan: Model,
    *,
    current_principal_minor: int = 10_000_00,
    idempotency_key: str = "secondary-holding-1",
) -> Model:
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    assigned_at = datetime.combine(date(2026, 1, 1), time.min, tzinfo=ZoneInfo("Europe/Zurich"))
    return cast(
        Model,
        holding_model.objects.create(
            loan=loan,
            investor_user_id=investor.pk,
            source_type="manual_admin",
            source_id=idempotency_key,
            status="active",
            original_principal_minor=current_principal_minor,
            current_principal_minor=current_principal_minor,
            currency=cast(Any, loan).currency,
            loan_share_ppm=333_333,
            assignment_effective_at=assigned_at,
            created_by_admin_id=admin_user.pk,
            metadata={},
            idempotency_key=idempotency_key,
        ),
    )


def _create_listing_acceptance(
    investor: Model,
    holding: Model,
    *,
    idempotency_key: str = "secondary-accept-1",
    category: str = "secondary_market_listing",
    context_type: str = "secondary_market_listing",
    context_id: str | None = None,
) -> Model:
    template_model = apps.get_model("documents", "DocumentTemplate")
    version_model = apps.get_model("documents", "DocumentTemplateVersion")
    acceptance_model = apps.get_model("documents", "DocumentAcceptanceEvidence")
    template = template_model.objects.create(
        category=category,
        template_key=idempotency_key[:128],
        language="en",
        name="Secondary listing terms",
        created_by_superadmin_id=investor.pk,
    )
    version = version_model.objects.create(
        template=template,
        version_number=1,
        status="published",
        title="Secondary listing terms",
        body="Terms",
        checkbox_labels=["I accept the secondary-market listing terms."],
        variable_schema={},
        content_hash="c" * 64,
        created_by_superadmin_id=investor.pk,
        published_at=timezone.now(),
    )
    template.current_published_version = version
    template.save(update_fields=["current_published_version"])
    return cast(
        Model,
        acceptance_model.objects.create(
            user_id=investor.pk,
            category=category,
            template=template,
            template_version=version,
            template_version_number=1,
            template_hash=version.content_hash,
            context_type=context_type,
            context_id=context_id or str(cast(Any, holding).id),
            accepted_checkbox_labels=["I accept the secondary-market listing terms."],
            data_snapshot={},
            idempotency_key=idempotency_key,
        ),
    )


def _create_purchase_acceptance(
    buyer: Model,
    listing: Model,
    *,
    idempotency_key: str = "secondary-purchase-accept-1",
    category: str = "secondary_market_purchase",
    context_type: str = "secondary_market_purchase",
    context_id: str | None = None,
) -> Model:
    return _create_listing_acceptance(
        buyer,
        listing,
        idempotency_key=idempotency_key,
        category=category,
        context_type=context_type,
        context_id=context_id or str(cast(Any, listing).id),
    )


def _declare_deposit(
    admin_user: Model,
    investor: Model,
    *,
    amount_minor: int = 20_000_00,
    value_date: date = date(2026, 1, 10),
    idempotency_key: str = "secondary-buyer-deposit-1",
) -> Any:
    ledger = import_module("backend.apps.ledger.services")
    return ledger.declare_lender_deposit(
        ledger.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency="CHF",
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier="GARANTA-CHF",
            payer_name="Secondary buyer",
            payer_account_identifier="CH0000000000000000002",
            bank_reference=idempotency_key,
            payment_reference=f"PAY-{idempotency_key}",
            evidence_reference="statement-2026-01-10",
            notes="Buyer balance for secondary-market purchase test.",
            idempotency_key=idempotency_key,
        )
    )


def _republish_acceptance_template(acceptance: Model) -> None:
    version_model = apps.get_model("documents", "DocumentTemplateVersion")
    acceptance_ref = cast(Any, acceptance)
    template = acceptance_ref.template
    new_version = version_model.objects.create(
        template=template,
        version_number=2,
        status="published",
        title="Secondary listing terms v2",
        body="Updated terms",
        checkbox_labels=["I accept the updated secondary-market listing terms."],
        variable_schema={},
        content_hash="d" * 64,
        created_by_superadmin_id=acceptance_ref.user_id,
        published_at=timezone.now(),
    )
    template.current_published_version = new_version
    template.save(update_fields=["current_published_version"])


@pytest.mark.django_db
def test_create_performing_listing_auto_publishes_and_calculates_pricing(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)

    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-listing-create-1",
            notes="Sell full holding.",
        )
    )

    assert listing.status == SecondaryMarketListingStatus.ACTIVE
    assert listing.publication_type == "automatic"
    assert listing.current_principal_minor == 10_000_00
    assert listing.transfer_price_minor == 9_500_00
    assert listing.discount_premium_bps == -500
    assert listing.accrued_interest_from_date == date(2026, 1, 1)
    assert listing.accrued_interest_to_date == date(2026, 1, 16)
    assert listing.accrued_interest_minor == 4_932
    assert listing.maker_fee_bps == 25
    assert listing.taker_fee_bps == 75
    assert listing.maker_fee_minor == 2_375
    assert listing.taker_fee_minor == 7_125
    assert listing.seller_net_proceeds_minor == 952_557
    assert listing.buyer_total_cost_minor == 962_057
    assert listing.risk_acknowledgement_required is False
    assert listing.listed_at is not None
    assert listing.metadata["accrual_day_count"] == "ACT/365"

    replay = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-listing-create-1",
            notes="Sell full holding.",
        )
    )
    assert replay.id == listing.id

    with pytest.raises(SecondaryMarketValidationError, match="already has an open"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9600,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="secondary-listing-create-duplicate",
            )
        )

    assert SecondaryMarketListingEvent.objects.filter(listing=listing).count() == 2
    assert AuditEvent.objects.filter(action="secondary_market.listing_created").exists()
    assert DomainEvent.objects.filter(event_type="SecondaryMarketListingCreated").exists()


@pytest.mark.django_db
def test_nonstandard_listing_requires_admin_approval_and_disclosure(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user, status="late")
    _create_current_installment(loan, due_date=date(2026, 1, 1))
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)

    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9000,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-listing-late",
        )
    )

    assert listing.status == SecondaryMarketListingStatus.APPROVAL_REQUESTED
    assert listing.publication_type == "admin_approved"
    assert listing.risk_acknowledgement_required is True
    assert listing.listed_at is None
    assert listing.days_past_due == 15
    assert list_active_secondary_market_listings(actor=investor) == []

    approved = approve_secondary_market_listing(
        ApproveSecondaryMarketListingCommand(
            actor=admin_user,
            listing_id=str(listing.id),
            reason="Disclosure reviewed.",
            disclosure_note="Loan is late. Buyer must acknowledge the current status.",
            idempotency_key="secondary-listing-approve",
        )
    )
    assert approved.status == SecondaryMarketListingStatus.ACTIVE
    assert approved.public_disclosure_note == (
        "Loan is late. Buyer must acknowledge the current status."
    )
    assert approved.approved_by_admin_id == admin_user.pk
    assert list_active_secondary_market_listings(actor=investor) == [approved]

    approval_replay = approve_secondary_market_listing(
        ApproveSecondaryMarketListingCommand(
            actor=admin_user,
            listing_id=str(listing.id),
            reason="Disclosure reviewed.",
            disclosure_note="Loan is late. Buyer must acknowledge the current status.",
            idempotency_key="secondary-listing-approve",
        )
    )
    assert approval_replay.id == approved.id


@pytest.mark.django_db
def test_active_browse_excludes_listing_when_current_loan_status_changed(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-listing-stale-status",
        )
    )
    assert list_active_secondary_market_listings(actor=investor) == [listing]

    cast(Any, loan).status = "written_off"
    loan.save(update_fields=["status"])

    assert list_active_secondary_market_listings(actor=investor) == []


@pytest.mark.django_db
def test_admin_can_reject_nonstandard_listing(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user, status="defaulted")
    _create_current_installment(loan, due_date=date(2026, 1, 1))
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=8000,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-listing-default",
        )
    )

    rejected = reject_secondary_market_listing(
        RejectSecondaryMarketListingCommand(
            actor=admin_user,
            listing_id=str(listing.id),
            reason="Disclosure package incomplete.",
            idempotency_key="secondary-listing-reject",
        )
    )

    assert rejected.status == SecondaryMarketListingStatus.REJECTED
    assert rejected.rejection_reason == "Disclosure package incomplete."
    assert SecondaryMarketListingEvent.objects.filter(
        listing=rejected,
        event_type=SecondaryMarketListingEventType.REJECTED,
    ).exists()


@pytest.mark.django_db
def test_listing_terms_acceptance_must_match_category_context_owner_and_current_version(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    wrong_category = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-wrong-category",
        category="primary_market_investment",
    )
    with pytest.raises(SecondaryMarketValidationError, match="category"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9500,
                document_acceptance_id=str(wrong_category.pk),
                idempotency_key="secondary-wrong-category-listing",
            )
        )

    wrong_context = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-wrong-context",
        context_id="different-holding",
    )
    with pytest.raises(SecondaryMarketValidationError, match="does not match"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9500,
                document_acceptance_id=str(wrong_context.pk),
                idempotency_key="secondary-wrong-context-listing",
            )
        )

    other_owner_acceptance = _create_listing_acceptance(
        other_investor,
        holding,
        idempotency_key="secondary-other-owner",
    )
    with pytest.raises(SecondaryMarketValidationError, match="does not exist"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9500,
                document_acceptance_id=str(other_owner_acceptance.pk),
                idempotency_key="secondary-other-owner-listing",
            )
        )

    stale = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-stale",
    )
    _republish_acceptance_template(stale)
    with pytest.raises(SecondaryMarketValidationError, match="no longer current"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9500,
                document_acceptance_id=str(stale.pk),
                idempotency_key="secondary-stale-listing",
            )
        )


@pytest.mark.django_db
def test_non_owner_and_non_financial_actor_cannot_list(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)

    with pytest.raises(SecondaryMarketValidationError, match="does not exist"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=other_investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9500,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="secondary-non-owner",
            )
        )

    user_model: Any = get_user_model()
    blocked = cast(
        Model,
        user_model.objects.create_user(
            email="secondary-blocked@example.test",
            full_name="Blocked Investor",
            account_type="natural_person_lender",
            status="pending_kyc",
        ),
    )
    with pytest.raises(SecondaryMarketAuthorizationError):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=blocked,
                holding_id=str(cast(Any, holding).id),
                price_bps=9500,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="secondary-blocked",
            )
        )


@pytest.mark.django_db
def test_secondary_market_api_create_list_and_approve(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user, status="late")
    _create_current_installment(loan, due_date=date(2026, 1, 1))
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    client = Client()
    client.force_login(cast(Any, investor))

    create_response = client.post(
        "/api/v1/marketplace/secondary/listings/",
        {
            "holding_id": str(cast(Any, holding).id),
            "price_bps": 9000,
            "document_acceptance_id": str(acceptance.pk),
            "idempotency_key": "secondary-api-create",
        },
        content_type="application/json",
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["status"] == "approval_requested"
    assert payload["risk_acknowledgement_required"] is True

    list_response = client.get("/api/v1/marketplace/secondary/listings/")
    assert list_response.status_code == 200
    assert list_response.json() == []

    client.force_login(cast(Any, admin_user))
    approve_response = client.post(
        f"/api/v1/marketplace/secondary/admin/listings/{payload['id']}/approve/",
        {
            "reason": "Reviewed.",
            "disclosure_note": "Late loan disclosure.",
            "idempotency_key": "secondary-api-approve",
        },
        content_type="application/json",
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "active"

    client.force_login(cast(Any, investor))
    list_response = client.get("/api/v1/marketplace/secondary/listings/")
    assert list_response.status_code == 200
    buyer_listing = list_response.json()[0]
    assert buyer_listing["public_disclosure_note"] == "Late loan disclosure."
    assert buyer_listing["loan_title"] == "Secondary bridge loan"
    assert buyer_listing["buyer_total_cost_minor"] > 0
    assert buyer_listing["taker_fee_minor"] > 0
    assert buyer_listing["risk_acknowledgement_required"] is True
    private_fields = {
        "holding_id",
        "seller_user_id",
        "created_by_user_id",
        "seller_net_proceeds_minor",
        "maker_fee_bps",
        "maker_fee_minor",
        "minimum_maker_fee_minor",
        "document_acceptance_id",
        "approved_by_admin_id",
        "approval_reason",
        "rejected_by_admin_id",
        "rejection_reason",
        "removed_by_admin_id",
        "removal_reason",
    }
    assert private_fields.isdisjoint(buyer_listing)


@pytest.mark.django_db
def test_purchase_listing_settles_ledger_transfers_holding_and_is_idempotent(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    seller_holding = _create_holding(admin_user, investor, loan)
    listing_acceptance = _create_listing_acceptance(investor, seller_holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, seller_holding).id),
            price_bps=9500,
            document_acceptance_id=str(listing_acceptance.pk),
            idempotency_key="secondary-purchase-listing",
        )
    )
    deposit = _declare_deposit(
        admin_user,
        other_investor,
        amount_minor=20_000_00,
        idempotency_key="secondary-purchase-buyer-deposit",
    )
    purchase_acceptance = _create_purchase_acceptance(other_investor, listing)

    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            idempotency_key="secondary-purchase-1",
        )
    )

    listing.refresh_from_db()
    cast(Any, seller_holding).refresh_from_db()
    deposit.balance_lot.refresh_from_db()
    buyer_holding = purchase.buyer_holding
    seller_balance_lot = purchase.seller_balance_lot
    assert listing.status == SecondaryMarketListingStatus.SOLD
    assert listing.sold_to_user_id == other_investor.pk
    assert cast(Any, seller_holding).status == "transferred"
    assert cast(Any, seller_holding).current_principal_minor == 0
    assert str(buyer_holding.investor_user_id) == str(other_investor.pk)
    assert buyer_holding.status == "active"
    assert buyer_holding.source_type == "secondary_market"
    assert buyer_holding.current_principal_minor == 10_000_00
    assert purchase.transfer_price_minor == 9_500_00
    assert purchase.accrued_interest_minor == 4_932
    assert purchase.maker_fee_minor == 2_375
    assert purchase.taker_fee_minor == 7_125
    assert purchase.seller_net_proceeds_minor == 952_557
    assert purchase.buyer_total_cost_minor == 962_057
    assert str(seller_balance_lot.investor_user_id) == str(investor.pk)
    assert seller_balance_lot.source_type == "secondary_market_proceeds"
    assert seller_balance_lot.available_amount_minor == 952_557
    assert deposit.balance_lot.available_amount_minor == 1_037_943
    assert deposit.balance_lot.invested_amount_minor == 962_057

    postings = {
        (posting.account.account_type, posting.account.owner_id, posting.side): (
            posting.amount_minor
        )
        for posting in purchase.ledger_journal_entry.postings.select_related("account")
    }
    assert postings[("investor_balance_liability", str(other_investor.pk), "debit")] == 962_057
    assert postings[("investor_balance_liability", str(investor.pk), "credit")] == 952_557
    assert postings[("platform_fee_revenue", "platform", "credit")] == 9_500

    replay = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            idempotency_key="secondary-purchase-1",
        )
    )
    assert replay.id == purchase.id
    assert SecondaryMarketPurchase.objects.count() == 1
    assert SecondaryMarketListingEvent.objects.filter(
        listing=listing,
        event_type=SecondaryMarketListingEventType.SOLD,
    ).exists()
    assert AuditEvent.objects.filter(action="secondary_market.purchase_completed").exists()
    assert DomainEvent.objects.filter(event_type="SecondaryMarketPurchaseCompleted").exists()


@pytest.mark.django_db
def test_purchase_requires_current_terms_and_rejects_own_or_stale_listing(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    seller_holding = _create_holding(admin_user, investor, loan)
    listing_acceptance = _create_listing_acceptance(investor, seller_holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, seller_holding).id),
            price_bps=9500,
            document_acceptance_id=str(listing_acceptance.pk),
            idempotency_key="secondary-purchase-negative-listing",
        )
    )
    _declare_deposit(
        admin_user,
        other_investor,
        idempotency_key="secondary-purchase-negative-deposit",
    )
    wrong_context = _create_purchase_acceptance(
        other_investor,
        listing,
        idempotency_key="secondary-purchase-wrong-context",
        context_id="different-listing",
    )
    with pytest.raises(SecondaryMarketValidationError, match="does not match"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(wrong_context.pk),
                idempotency_key="secondary-purchase-wrong-context-key",
            )
        )

    own_acceptance = _create_purchase_acceptance(
        investor,
        listing,
        idempotency_key="secondary-purchase-own-acceptance",
    )
    with pytest.raises(SecondaryMarketValidationError, match="own listing"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(own_acceptance.pk),
                idempotency_key="secondary-purchase-own-listing",
            )
        )

    stale_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        idempotency_key="secondary-purchase-stale-acceptance",
    )
    _republish_acceptance_template(stale_acceptance)
    with pytest.raises(SecondaryMarketValidationError, match="no longer current"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(stale_acceptance.pk),
                idempotency_key="secondary-purchase-stale-terms",
            )
        )

    fresh_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        idempotency_key="secondary-purchase-fresh-before-stale-status",
    )
    cast(Any, loan).status = "late"
    loan.save(update_fields=["status"])
    with pytest.raises(SecondaryMarketValidationError, match="Loan status changed"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(fresh_acceptance.pk),
                idempotency_key="secondary-purchase-stale-status",
            )
        )


@pytest.mark.django_db
def test_nonstandard_purchase_requires_buyer_risk_acknowledgement(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user, status="late")
    _create_current_installment(loan, due_date=date(2026, 1, 1))
    seller_holding = _create_holding(admin_user, investor, loan)
    listing_acceptance = _create_listing_acceptance(investor, seller_holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, seller_holding).id),
            price_bps=9000,
            document_acceptance_id=str(listing_acceptance.pk),
            idempotency_key="secondary-purchase-late-listing",
        )
    )
    listing = approve_secondary_market_listing(
        ApproveSecondaryMarketListingCommand(
            actor=admin_user,
            listing_id=str(listing.id),
            reason="Approved with disclosure.",
            disclosure_note="Loan is late.",
            idempotency_key="secondary-purchase-late-approve",
        )
    )
    _declare_deposit(
        admin_user,
        other_investor,
        idempotency_key="secondary-purchase-late-deposit",
    )
    purchase_acceptance = _create_purchase_acceptance(other_investor, listing)

    with pytest.raises(SecondaryMarketValidationError, match="acknowledge"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(purchase_acceptance.pk),
                idempotency_key="secondary-purchase-late-no-ack",
            )
        )

    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            risk_acknowledgement_accepted=True,
            idempotency_key="secondary-purchase-late-with-ack",
        )
    )
    assert purchase.risk_acknowledgement_accepted is True
    assert purchase.loan_status_at_purchase == "late"
    assert purchase.accrued_interest_minor == 0


@pytest.mark.django_db
def test_secondary_market_api_purchase_response_hides_seller_economics(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    seller_holding = _create_holding(admin_user, investor, loan)
    listing_acceptance = _create_listing_acceptance(investor, seller_holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, seller_holding).id),
            price_bps=9500,
            document_acceptance_id=str(listing_acceptance.pk),
            idempotency_key="secondary-api-purchase-listing",
        )
    )
    _declare_deposit(
        admin_user,
        other_investor,
        idempotency_key="secondary-api-purchase-deposit",
    )
    purchase_acceptance = _create_purchase_acceptance(other_investor, listing)
    client = Client()
    client.force_login(cast(Any, other_investor))

    response = client.post(
        f"/api/v1/marketplace/secondary/listings/{listing.id}/purchase/",
        {
            "document_acceptance_id": str(purchase_acceptance.pk),
            "idempotency_key": "secondary-api-purchase",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["listing_id"] == str(listing.id)
    assert payload["buyer_total_cost_minor"] == 962_057
    private_fields = {
        "seller_user_id",
        "seller_holding_id",
        "seller_net_proceeds_minor",
        "maker_fee_bps",
        "maker_fee_minor",
        "minimum_maker_fee_minor",
        "ledger_journal_entry_id",
        "seller_balance_lot_id",
        "purchase_document_acceptance_id",
        "idempotency_key",
        "metadata",
    }
    assert private_fields.isdisjoint(payload)


@pytest.mark.django_db
def test_secondary_market_listing_event_has_app_and_db_append_only_guards(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-event-guard",
        )
    )
    event = SecondaryMarketListingEvent.objects.filter(listing=listing).first()
    assert event is not None

    with pytest.raises(AppendOnlyViolation):
        event.save()
    with pytest.raises(AppendOnlyViolation):
        event.delete()
    with pytest.raises(AppendOnlyViolation):
        SecondaryMarketListingEvent.objects.filter(id=event.id).update(note="mutated")

    db_record_id = event.pk.hex
    with pytest.raises(DatabaseError) as update_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE secondary_market_secondarymarketlistingevent "
                "SET note = %s WHERE id = %s",
                ["mutated", db_record_id],
            )
    assert "append-only" in str(update_error.value)


@pytest.mark.django_db
def test_secondary_market_purchase_has_app_and_db_append_only_guards(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    seller_holding = _create_holding(admin_user, investor, loan)
    listing_acceptance = _create_listing_acceptance(investor, seller_holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, seller_holding).id),
            price_bps=9500,
            document_acceptance_id=str(listing_acceptance.pk),
            idempotency_key="secondary-purchase-guard-listing",
        )
    )
    _declare_deposit(
        admin_user,
        other_investor,
        idempotency_key="secondary-purchase-guard-deposit",
    )
    purchase_acceptance = _create_purchase_acceptance(other_investor, listing)
    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            idempotency_key="secondary-purchase-guard",
        )
    )

    with pytest.raises(AppendOnlyViolation):
        purchase.save()
    with pytest.raises(AppendOnlyViolation):
        purchase.delete()
    with pytest.raises(AppendOnlyViolation):
        SecondaryMarketPurchase.objects.filter(id=purchase.id).update(days_past_due=1)

    db_record_id = purchase.pk.hex
    with pytest.raises(DatabaseError) as update_error, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE secondary_market_secondarymarketpurchase "
                "SET days_past_due = %s WHERE id = %s",
                [1, db_record_id],
            )
    assert "append-only" in str(update_error.value)
