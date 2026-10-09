from __future__ import annotations

from datetime import date, datetime, time
from importlib import import_module
from typing import Any, TypedDict, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.platform_core.domain.time import now_utc
from backend.apps.platform_core.models import AuditEvent, Currency, DomainEvent, OutboxMessage
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.services.impersonation import (
    READONLY_IMPERSONATION_HEADER,
    issue_readonly_impersonation_token,
)
from backend.apps.platform_core.tests.factories import (
    SensitiveActionCodePayload,
    issue_sensitive_action_test_code,
)
from backend.apps.platform_core.tests.qa_clock import qa_clock
from backend.apps.secondary_market.models import (
    SecondaryMarketListing,
    SecondaryMarketListingEvent,
    SecondaryMarketListingEventType,
    SecondaryMarketListingStatus,
    SecondaryMarketPurchase,
)
from backend.apps.secondary_market.services import (
    ApproveSecondaryMarketListingCommand,
    CancelSecondaryMarketListingCommand,
    CreateSecondaryMarketListingCommand,
    EditSecondaryMarketListingCommand,
    PurchaseSecondaryMarketListingCommand,
    RejectSecondaryMarketListingCommand,
    SecondaryMarketAuthorizationError,
    SecondaryMarketPriceChangedError,
    SecondaryMarketValidationError,
    approve_secondary_market_listing,
    cancel_secondary_market_listing,
    create_secondary_market_listing,
    edit_secondary_market_listing,
    get_active_secondary_market_listing_detail,
    list_active_secondary_market_listings,
    purchase_secondary_market_listing,
    refresh_open_secondary_market_listings_for_loan,
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


def _sensitive_code_payload(user: Model, action: str) -> SensitiveActionCodePayload:
    code = issue_sensitive_action_test_code(user, action)
    return {
        "sensitive_action_code_id": code.code_id,
        "sensitive_action_code": code.raw_code,
    }


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
    status: str = "active",
    principal_minor: int = 30_000_00,
    loan_start_date: date = date(2026, 1, 1),
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
            original_principal_minor=principal_minor,
            principal_minor=principal_minor,
            currency=currency,
            interest_rate_bps=1200,
            term_months=12,
            repayment_type="equal_installments",
            # Interest starts on the loan start date; the first installment is due
            # one month later (2026-02-01), as the schedule generator derives it.
            loan_start_date=loan_start_date,
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
    data_snapshot: dict[str, Any] | None = None,
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
            data_snapshot=data_snapshot or {},
            idempotency_key=idempotency_key,
        ),
    )


def _review_purchase(buyer: Model, listing: Model) -> dict[str, Any]:
    """The economics the Buy modal shows: the fresh buyer listing detail."""
    detail = get_active_secondary_market_listing_detail(
        actor=buyer,
        listing_id=str(cast(Any, listing).id),
    )
    return {
        "listing_id": detail["id"],
        "currency": detail["currency"],
        "price_bps": detail["price_bps"],
        "current_principal_minor": detail["current_principal_minor"],
        "buyer_total_cost_minor": detail["buyer_total_cost_minor"],
    }


class ExpectedPurchaseTerms(TypedDict):
    expected_buyer_total_cost_minor: int
    expected_price_bps: int
    expected_current_principal_minor: int


def _expected_terms(review: dict[str, Any]) -> ExpectedPurchaseTerms:
    return {
        "expected_buyer_total_cost_minor": int(review["buyer_total_cost_minor"]),
        "expected_price_bps": int(review["price_bps"]),
        "expected_current_principal_minor": int(review["current_principal_minor"]),
    }


def _create_purchase_acceptance(
    buyer: Model,
    listing: Model,
    *,
    idempotency_key: str = "secondary-purchase-accept-1",
    category: str = "secondary_market_purchase",
    context_type: str = "secondary_market_purchase",
    context_id: str | None = None,
    review: dict[str, Any] | None = None,
) -> Model:
    return _create_listing_acceptance(
        buyer,
        listing,
        idempotency_key=idempotency_key,
        category=category,
        context_type=context_type,
        context_id=context_id or str(cast(Any, listing).id),
        data_snapshot=review if review is not None else _review_purchase(buyer, listing),
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
            payer_account_identifier="CH9300762011623852957",
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
    listing_code = _sensitive_code_payload(investor, "secondary_market_listing")

    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-listing-create-1",
            notes="Sell full holding.",
            **listing_code,
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
    listing_email = OutboxMessage.objects.get(topic="email.secondary_market_listing_status")
    assert listing_email.payload["user_id"] == str(investor.pk)
    assert listing_email.payload["metadata"]["loan_id"] == str(loan.pk)

    replay = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-listing-create-1",
            notes="Sell full holding.",
            **listing_code,
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
                **listing_code,
            )
        )

    assert SecondaryMarketListingEvent.objects.filter(listing=listing).count() == 2
    assert AuditEvent.objects.filter(action="secondary_market.listing_created").exists()
    assert DomainEvent.objects.filter(event_type="SecondaryMarketListingCreated").exists()


@pytest.mark.django_db
def test_automatic_listing_refresh_preserves_price_and_recomputes_or_cancels(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-auto-refresh-acceptance",
    )
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=10_100,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-auto-refresh-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )

    cast(Any, holding).current_principal_minor = 8_000_00
    holding.save(update_fields=["current_principal_minor", "updated_at"])
    refreshes = refresh_open_secondary_market_listings_for_loan(
        actor=admin_user,
        loan=loan,
        as_of_date=date(2026, 1, 16),
        source_type="borrower_repayment_event",
        source_id="repayment-1",
    )
    listing.refresh_from_db()

    assert len(refreshes) == 1
    assert listing.status == SecondaryMarketListingStatus.ACTIVE
    assert listing.price_bps == 10_100
    assert listing.discount_premium_bps == 100
    assert listing.current_principal_minor == 8_000_00
    assert listing.transfer_price_minor == 8_080_00
    assert refreshes[0].principal_before_minor == 10_000_00
    assert refreshes[0].principal_after_minor == 8_000_00
    assert refreshes[0].transfer_price_after_minor == 8_080_00
    assert SecondaryMarketListingEvent.objects.filter(
        listing=listing,
        event_type=SecondaryMarketListingEventType.REPRICED,
    ).count() == 1

    replay = refresh_open_secondary_market_listings_for_loan(
        actor=admin_user,
        loan=loan,
        as_of_date=date(2026, 1, 16),
        source_type="borrower_repayment_event",
        source_id="repayment-1",
    )
    assert replay == []

    cast(Any, holding).current_principal_minor = 0
    cast(Any, holding).status = "closed"
    holding.save(update_fields=["current_principal_minor", "status", "updated_at"])
    cancellations = refresh_open_secondary_market_listings_for_loan(
        actor=admin_user,
        loan=loan,
        as_of_date=date(2026, 1, 17),
        source_type="borrower_repayment_event",
        source_id="repayment-2",
    )
    listing.refresh_from_db()

    assert len(cancellations) == 1
    assert cancellations[0].automatically_cancelled is True
    assert listing.status == SecondaryMarketListingStatus.CANCELLED
    assert SecondaryMarketListingEvent.objects.filter(
        listing=listing,
        event_type=SecondaryMarketListingEventType.AUTO_CANCELLED,
    ).count() == 1


@pytest.mark.django_db
def test_borrower_repayment_reprices_active_listing_and_notifies_seller(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    _create_current_installment(loan, due_date=date(2026, 1, 20))
    installment_model = apps.get_model("loans", "LoanInstallment")
    installment_model.objects.create(
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
    acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-repayment-refresh-acceptance",
    )
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=10_100,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-repayment-refresh-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )

    servicing = import_module("backend.apps.servicing.services")
    servicing.record_borrower_repayment(
        servicing.RecordBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=2_300_00,
            booking_date=date(2026, 1, 16),
            value_date=date(2026, 1, 16),
            collection_account_identifier="GARANTA-CHF",
            payer_name="Secondary Borrower AG",
            payer_account_identifier="CH22BORROWER",
            bank_reference="BANK-secondary-repayment-refresh",
            payment_reference=f"LOAN-{loan.pk}",
            evidence_reference="statement:secondary-repayment-refresh",
            early_regular_payment_acknowledged=True,
            idempotency_key="secondary-repayment-refresh",
        )
    )
    holding.refresh_from_db()
    listing.refresh_from_db()

    assert cast(Any, holding).current_principal_minor == 8_000_00
    assert listing.status == SecondaryMarketListingStatus.ACTIVE
    assert listing.price_bps == 10_100
    assert listing.current_principal_minor == 8_000_00
    assert listing.transfer_price_minor == 8_080_00
    # A regular installment paid early covers contractual interest through its
    # due date. Repricing must not start accruing that interest again from the
    # earlier bank date.
    assert listing.accrued_interest_minor == 0
    assert listing.accrued_interest_from_date == date(2026, 1, 20)
    repayment_email = OutboxMessage.objects.get(
        topic="email.repayment_distribution_credited",
        payload__user_id=str(investor.pk),
    )
    assert repayment_email.payload["metadata"]["secondary_listing_repriced"] is True
    assert repayment_email.payload["metadata"]["secondary_listing_id"] == str(listing.id)
    assert "automatically recalculated" in repayment_email.payload["body_text"]
    assert "1.00% premium" in repayment_email.payload["body_text"]


@pytest.mark.django_db
def test_seller_edit_reprices_open_listing_with_fresh_evidence_and_idempotency(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    original_acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(original_acceptance.pk),
            idempotency_key="secondary-edit-source",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    revised_acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-edit-acceptance",
    )
    code = _sensitive_code_payload(investor, "secondary_market_listing")
    command = EditSecondaryMarketListingCommand(
        actor=investor,
        listing_id=str(listing.id),
        price_bps=9800,
        document_acceptance_id=str(revised_acceptance.pk),
        idempotency_key="secondary-edit-listing",
        notes="Repriced after reviewing liquidity needs.",
        **code,
    )

    edited = edit_secondary_market_listing(command)
    replay = edit_secondary_market_listing(command)
    listing.refresh_from_db()

    assert replay.id == edited.id == listing.id
    assert listing.status == SecondaryMarketListingStatus.ACTIVE
    assert listing.price_bps == 9800
    assert listing.transfer_price_minor == 9_800_00
    assert listing.document_acceptance_id == revised_acceptance.pk
    event = SecondaryMarketListingEvent.objects.get(
        listing=listing,
        event_type=SecondaryMarketListingEventType.EDITED,
    )
    assert event.idempotency_key == "secondary-edit-listing"
    assert event.metadata["previous"]["price_bps"] == 9500
    assert event.metadata["price_bps"] == 9800
    assert AuditEvent.objects.filter(action="secondary_market.listing_edited").exists()
    assert DomainEvent.objects.filter(event_type="SecondaryMarketListingEdited").exists()

    with pytest.raises(SecondaryMarketValidationError, match="different listing edit"):
        edit_secondary_market_listing(
            EditSecondaryMarketListingCommand(
                actor=investor,
                listing_id=str(listing.id),
                price_bps=9900,
                document_acceptance_id=str(revised_acceptance.pk),
                idempotency_key="secondary-edit-listing",
                **code,
            )
        )


@pytest.mark.django_db
def test_seller_can_cancel_open_listing_and_relist_holding(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-cancel-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )

    cancelled = cancel_secondary_market_listing(
        CancelSecondaryMarketListingCommand(
            actor=investor,
            listing_id=str(listing.id),
            reason="Seller changed liquidity plan.",
            idempotency_key="secondary-cancel-listing-ok",
        )
    )
    replay = cancel_secondary_market_listing(
        CancelSecondaryMarketListingCommand(
            actor=investor,
            listing_id=str(listing.id),
            reason="Seller changed liquidity plan.",
            idempotency_key="secondary-cancel-listing-ok",
        )
    )
    listing.refresh_from_db()

    assert replay.id == cancelled.id
    assert listing.status == SecondaryMarketListingStatus.CANCELLED
    assert listing.cancelled_by_user_id == investor.pk
    assert listing.cancellation_reason == "Seller changed liquidity plan."
    assert SecondaryMarketListingEvent.objects.filter(
        listing=listing,
        event_type=SecondaryMarketListingEventType.CANCELLED,
    ).exists()
    assert AuditEvent.objects.filter(action="secondary_market.listing_cancelled").exists()
    assert DomainEvent.objects.filter(event_type="SecondaryMarketListingCancelled").exists()
    with pytest.raises(SecondaryMarketValidationError, match="does not exist"):
        cancel_secondary_market_listing(
            CancelSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                reason="Not seller.",
                idempotency_key="secondary-cancel-listing-other",
            )
        )

    relist_acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-relist-after-cancel-accept",
    )
    relisted = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9600,
            document_acceptance_id=str(relist_acceptance.pk),
            idempotency_key="secondary-relist-after-cancel",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    assert relisted.status == SecondaryMarketListingStatus.ACTIVE


@pytest.mark.django_db
def test_create_listing_requires_sensitive_action_code(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-listing-missing-code-accept",
    )

    with pytest.raises(SecondaryMarketValidationError, match="Sensitive-action email code"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9500,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="secondary-listing-missing-code",
            )
        )

    assert SecondaryMarketListingEvent.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("loan_status", ["late", "defaulted"])
def test_late_or_defaulted_direct_holding_cannot_be_listed(
    admin_user: Model,
    investor: Model,
    loan_status: str,
) -> None:
    # Product rule C18: no listing and no approval request for a non-performing loan.
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user, status=loan_status)
    _create_current_installment(loan, due_date=date(2026, 1, 1))
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)

    with pytest.raises(
        SecondaryMarketValidationError,
        match="Late or defaulted loans cannot be listed on the secondary market",
    ):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9000,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key=f"secondary-listing-{loan_status}",
                **_sensitive_code_payload(investor, "secondary_market_listing"),
            )
        )

    assert not SecondaryMarketListing.objects.exists()
    assert not SecondaryMarketListingEvent.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("loan_status", ["late", "defaulted"])
def test_late_or_defaulted_originator_holding_cannot_be_listed(
    admin_user: Model,
    investor: Model,
    loan_status: str,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user, status=loan_status)
    cast(Any, loan).product_type = "originator_claim"
    cast(Any, loan).borrower = None
    loan.save(update_fields=["product_type", "borrower"])
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)

    with pytest.raises(
        SecondaryMarketValidationError,
        match="Late or defaulted Loan Originator claims cannot be transferred",
    ):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9000,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key=f"secondary-lo-listing-{loan_status}",
                **_sensitive_code_payload(investor, "secondary_market_listing"),
            )
        )

    assert not SecondaryMarketListing.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("loan_status", ["late", "defaulted"])
def test_open_listing_is_cancelled_and_seller_told_when_loan_turns_non_performing(
    admin_user: Model,
    investor: Model,
    loan_status: str,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9800,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=f"secondary-listing-turns-{loan_status}",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    assert listing.status == SecondaryMarketListingStatus.ACTIVE
    journal_model = apps.get_model("ledger", "LedgerJournalEntry")
    journals_before = journal_model.objects.count()

    cast(Any, loan).status = loan_status
    loan.save(update_fields=["status"])
    refreshes = refresh_open_secondary_market_listings_for_loan(
        actor=admin_user,
        loan=loan,
        as_of_date=date(2026, 1, 16),
        source_type="servicing_status_scan",
        source_id=f"{cast(Any, loan).pk}:{loan_status}:2026-01-16",
    )
    listing.refresh_from_db()
    holding.refresh_from_db()

    assert [refresh.automatically_cancelled for refresh in refreshes] == [True]
    assert listing.status == SecondaryMarketListingStatus.CANCELLED
    assert listing.listed_at is None
    assert listing.cancelled_by_user_id is None
    expected_reason = "the loan is late" if loan_status == "late" else "the loan is in default"
    assert expected_reason in listing.cancellation_reason
    # Nothing moved: no journal, holding unchanged, no approval request.
    assert journal_model.objects.count() == journals_before
    assert cast(Any, holding).current_principal_minor == 10_000_00
    assert cast(Any, holding).status == "active"
    assert not SecondaryMarketListingEvent.objects.filter(
        listing=listing,
        event_type=SecondaryMarketListingEventType.APPROVAL_REQUESTED,
    ).exists()
    assert SecondaryMarketListingEvent.objects.filter(
        listing=listing,
        event_type=SecondaryMarketListingEventType.AUTO_CANCELLED,
        new_status=SecondaryMarketListingStatus.CANCELLED,
    ).count() == 1
    notices = OutboxMessage.objects.filter(
        topic="email.secondary_market_listing_status",
        idempotency_key__contains=f"{listing.id}:auto-cancelled",
    )
    assert notices.count() == 1
    notice = cast(Any, notices.get()).payload
    assert notice["user_id"] == str(cast(Any, investor).pk)
    assert notice["subject"].endswith("secondary-market listing cancelled")
    assert "No money was moved" in notice["body_text"]
    assert notice["metadata"]["listing_id"] == str(listing.id)
    assert list_active_secondary_market_listings(actor=investor) == []

    replay = refresh_open_secondary_market_listings_for_loan(
        actor=admin_user,
        loan=loan,
        as_of_date=date(2026, 1, 16),
        source_type="servicing_status_scan",
        source_id=f"{cast(Any, loan).pk}:{loan_status}:2026-01-16",
    )
    assert replay == []
    assert notices.count() == 1


@pytest.mark.django_db
def test_servicing_status_scan_cancels_open_listing_of_a_loan_that_turns_late(
    admin_user: Model,
    investor: Model,
) -> None:
    servicing = import_module("backend.apps.servicing.services")
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    _create_current_installment(loan, due_date=date(2026, 1, 8))
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=10_000,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-listing-before-scan",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )

    result = servicing.scan_loan_servicing_statuses(
        servicing.ScanLoanServicingStatusesCommand(
            actor=admin_user,
            as_of_date=date(2026, 1, 16),
            loan_ids=(str(cast(Any, loan).pk),),
        )
    )
    listing.refresh_from_db()
    loan.refresh_from_db()

    assert [change.new_status for change in result.changes] == ["late"]
    assert cast(Any, loan).status == "late"
    assert listing.status == SecondaryMarketListingStatus.CANCELLED
    assert "the loan is late" in listing.cancellation_reason
    assert OutboxMessage.objects.filter(
        topic="email.secondary_market_listing_status",
        payload__user_id=str(cast(Any, investor).pk),
        payload__metadata__reason="loan_not_performing",
    ).count() == 1


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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    assert list_active_secondary_market_listings(actor=investor) == [listing]

    cast(Any, loan).status = "written_off"
    loan.save(update_fields=["status"])

    assert list_active_secondary_market_listings(actor=investor) == []


def _legacy_approval_request(admin_user: Model, investor: Model, *, key: str) -> Any:
    """An ``approval_requested`` row as the retired workflow left it, on a late loan."""
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan, idempotency_key=f"{key}-holding")
    acceptance = _create_listing_acceptance(investor, holding, idempotency_key=f"{key}-accept")
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9000,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=f"{key}-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    cast(Any, loan).status = "late"
    loan.save(update_fields=["status"])
    SecondaryMarketListing.objects.filter(pk=listing.pk).update(
        status=SecondaryMarketListingStatus.APPROVAL_REQUESTED,
        publication_type="admin_approved",
        loan_status_at_listing="late",
        risk_acknowledgement_required=True,
        listed_at=None,
    )
    listing.refresh_from_db()
    return listing


@pytest.mark.django_db
def test_admin_cannot_approve_a_legacy_request_for_a_late_loan_but_can_reject_it(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    listing = _legacy_approval_request(admin_user, investor, key="secondary-legacy-request")

    with pytest.raises(SecondaryMarketValidationError, match="Late or defaulted loans"):
        approve_secondary_market_listing(
            ApproveSecondaryMarketListingCommand(
                actor=admin_user,
                listing_id=str(listing.id),
                reason="Disclosure reviewed.",
                disclosure_note="Loan is late.",
                idempotency_key="secondary-legacy-approve",
            )
        )
    listing.refresh_from_db()
    assert listing.status == SecondaryMarketListingStatus.APPROVAL_REQUESTED
    assert list_active_secondary_market_listings(actor=investor) == []

    rejected = reject_secondary_market_listing(
        RejectSecondaryMarketListingCommand(
            actor=admin_user,
            listing_id=str(listing.id),
            reason="Late loans cannot be listed.",
            idempotency_key="secondary-legacy-reject",
        )
    )

    assert rejected.status == SecondaryMarketListingStatus.REJECTED
    assert rejected.rejection_reason == "Late loans cannot be listed."
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
    listing_code = _sensitive_code_payload(investor, "secondary_market_listing")
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
                **listing_code,
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
                **listing_code,
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
                **listing_code,
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
                **listing_code,
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
                **_sensitive_code_payload(other_investor, "secondary_market_listing"),
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
                sensitive_action_code_id="00000000-0000-0000-0000-000000000000",
                sensitive_action_code="000000",
            )
        )


@pytest.mark.django_db
def test_secondary_market_api_refuses_late_listing_and_approve_answers_400(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    legacy = _legacy_approval_request(admin_user, investor, key="secondary-api-legacy")
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        },
        content_type="application/json",
    )
    assert create_response.status_code == 400
    assert create_response.json()["detail"] == (
        "Late or defaulted loans cannot be listed on the secondary market."
    )
    assert list(SecondaryMarketListing.objects.values_list("id", flat=True)) == [legacy.id]

    client.force_login(cast(Any, admin_user))
    approve_response = client.post(
        f"/api/v1/marketplace/secondary/admin/listings/{legacy.id}/approve/",
        {
            "reason": "Reviewed.",
            "disclosure_note": "Late loan disclosure.",
            "idempotency_key": "secondary-api-approve",
        },
        content_type="application/json",
    )
    assert approve_response.status_code == 400
    assert "Late or defaulted loans" in approve_response.json()["detail"]

    client.force_login(cast(Any, investor))
    list_response = client.get("/api/v1/marketplace/secondary/listings/")
    assert list_response.status_code == 200
    assert list_response.json() == []


@pytest.mark.django_db(transaction=True)
def test_postgres_admin_approve_runs_in_its_own_transaction(
    admin_user: Model,
    investor: Model,
) -> None:
    """SECONDARY-04: approve used select_for_update outside a transaction (HTTP 500).

    Only PostgreSQL enforces row locks; SQLite ignores select_for_update, and its flush
    cannot delete the append-only rows this test creates.
    """
    if connection.vendor != "postgresql":
        pytest.skip("Row-lock transaction check requires PostgreSQL.")
    # Transactional tests flush reference rows left by migrations/other tests.
    call_command("seed_reference_data", verbosity=0)
    _approve_financial_access(investor)
    listing = _legacy_approval_request(admin_user, investor, key="secondary-pg-approve")
    # The loan performs again, so approving the old request is allowed.
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=listing.loan_id).update(status="active")
    SecondaryMarketListing.objects.filter(pk=listing.pk).update(loan_status_at_listing="active")
    client = Client()
    client.force_login(cast(Any, admin_user))

    response = client.post(
        f"/api/v1/marketplace/secondary/admin/listings/{listing.id}/approve/",
        {
            "reason": "Reviewed.",
            "disclosure_note": "Loan performs again.",
            "idempotency_key": "secondary-pg-approve-key",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.django_db
def test_secondary_market_buyer_detail_exposes_loan_schedules_without_seller_data(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user, principal_minor=2_000_00)
    _create_current_installment(loan, due_date=date(2026, 2, 1))
    holding = _create_holding(
        admin_user,
        investor,
        loan,
        current_principal_minor=2_000_00,
        idempotency_key="secondary-detail-holding",
    )
    acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-detail-acceptance",
    )
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9_800,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-detail-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )

    client = Client()
    client.force_login(cast(Any, other_investor))
    response = client.get(
        f"/api/v1/marketplace/secondary/listings/{listing.pk}/"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["borrower_name"] == "Secondary Borrower AG"
    assert payload["borrower_country"] == "CH"
    assert payload["interest_rate_bps"] == 1_200
    assert payload["term_months"] == 12
    assert payload["ltv_bps"] == 400
    assert payload["loan_schedule"] == [
        {
            "id": str(cast(Any, loan).installments.get().pk),
            "schedule_version": 1,
            "installment_number": 1,
            "due_date": "2026-02-01",
            "principal_minor": 2_000_00,
            "interest_minor": 300_00,
            "total_minor": 2_300_00,
            "paid_principal_minor": 0,
            "paid_interest_minor": 0,
            "outstanding_principal_minor": 2_000_00,
            "outstanding_interest_minor": 300_00,
            "outstanding_total_minor": 2_300_00,
                "is_paid": False,
                "days_past_due": 0,
                "status": "upcoming",
                "row_type": "scheduled_installment",
                "label": "Installment 1",
                "payment_date": None,
            }
        ]
    assert payload["investment_schedule"] == [
        {
            "loan_installment_id": str(cast(Any, loan).installments.get().pk),
            "schedule_version": 1,
            "installment_number": 1,
            "due_date": "2026-02-01",
            "projected_principal_minor": 2_000_00,
            "projected_interest_minor": 300_00,
            "projected_total_minor": 2_300_00,
            "days_past_due": 0,
            "status": "upcoming",
        }
    ]
    private_fields = {
        "holding_id",
        "seller_user_id",
        "seller_net_proceeds_minor",
        "maker_fee_bps",
        "maker_fee_minor",
        "document_acceptance_id",
        "approved_by_admin_id",
    }
    assert private_fields.isdisjoint(payload)


@pytest.mark.django_db
def test_buyer_list_and_detail_use_current_accrued_interest_projection(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user, principal_minor=2_000_00)
    _create_current_installment(loan, due_date=date(2026, 2, 1))
    holding = _create_holding(
        admin_user,
        investor,
        loan,
        current_principal_minor=2_000_00,
        idempotency_key="secondary-current-buyer-pricing-holding",
    )
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9_800,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-current-buyer-pricing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    listing_day_cost = int(cast(Any, listing).buyer_total_cost_minor)

    secondary_services = import_module("backend.apps.secondary_market.services")
    next_day = datetime(2026, 1, 17, 12, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr(secondary_services, "now_utc", lambda: next_day)

    client = Client()
    client.force_login(cast(Any, other_investor))
    list_response = client.get("/api/v1/marketplace/secondary/listings/")
    assert list_response.status_code == 200
    buyer_listing = list_response.json()[0]
    assert buyer_listing["buyer_total_cost_minor"] > listing_day_cost
    assert buyer_listing["accrued_interest_to_date"] == "2026-01-17"

    detail_response = client.get(
        f"/api/v1/marketplace/secondary/listings/{listing.pk}/"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["buyer_total_cost_minor"] == buyer_listing["buyer_total_cost_minor"]
    assert detail["accrued_interest_minor"] == buyer_listing["accrued_interest_minor"]
    assert detail["accrued_interest_to_date"] == "2026-01-17"


@pytest.mark.django_db
def test_admin_secondary_listing_table_lists_and_filters(
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
            price_bps=9000,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-admin-table",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )

    client = Client()
    client.force_login(cast(Any, admin_user))
    response = client.get("/api/v1/marketplace/secondary/admin/listings/")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == str(listing.id)
    assert row["status"] == "active"
    assert row["loan_title"] == "Secondary bridge loan"
    assert row["loan_status"] == "active"
    assert row["seller_email"] == cast(Any, investor).email
    assert row["seller_full_name"]
    assert "created_at" in row

    filtered = client.get(
        "/api/v1/marketplace/secondary/admin/listings/?status=approval_requested"
    )
    assert filtered.status_code == 200
    assert filtered.json() == []

    bad_filter = client.get("/api/v1/marketplace/secondary/admin/listings/?status=bogus")
    assert bad_filter.status_code == 400

    client.force_login(cast(Any, investor))
    forbidden = client.get("/api/v1/marketplace/secondary/admin/listings/")
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_secondary_market_list_uses_readonly_impersonation_target(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    user_model: Any = get_user_model()
    superadmin = user_model.objects.create_superuser(
        email="secondary-superadmin@example.test",
        password="unused",
        full_name="Secondary Superadmin",
        account_type="superadmin",
        status="active",
    )
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-readonly-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    token = issue_readonly_impersonation_token(
        actor=superadmin,
        target_user_id=str(other_investor.pk),
    )["token"]
    client = Client()
    client.force_login(cast(Any, superadmin))

    response = client.get(
        "/api/v1/marketplace/secondary/listings/",
        **{f"HTTP_{READONLY_IMPERSONATION_HEADER.upper().replace('-', '_')}": token},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(listing.pk)
    assert "seller_user_id" not in response.json()[0]


@pytest.mark.django_db
def test_secondary_market_api_seller_cancel_is_owner_only(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-api-cancel-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    client = Client()

    client.force_login(cast(Any, other_investor))
    forbidden = client.post(
        f"/api/v1/marketplace/secondary/listings/{listing.id}/cancel/",
        {
            "reason": "Not the seller.",
            "idempotency_key": "secondary-api-cancel-forbidden",
        },
        content_type="application/json",
    )

    client.force_login(cast(Any, investor))
    response = client.post(
        f"/api/v1/marketplace/secondary/listings/{listing.id}/cancel/",
        {
            "reason": "Seller changed liquidity plan.",
            "idempotency_key": "secondary-api-cancel-ok",
        },
        content_type="application/json",
    )

    listing.refresh_from_db()
    assert forbidden.status_code == 400
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancellation_reason"] == "Seller changed liquidity plan."
    assert listing.status == SecondaryMarketListingStatus.CANCELLED


@pytest.mark.django_db
def test_secondary_market_api_seller_edit_is_owner_only_and_reprices_listing(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(investor, holding)
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=9500,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="secondary-api-edit-source",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    revised_acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="secondary-api-edit-acceptance",
    )
    client = Client()

    client.force_login(cast(Any, other_investor))
    forbidden = client.post(
        f"/api/v1/marketplace/secondary/listings/{listing.id}/edit/",
        {
            "price_bps": 9800,
            "document_acceptance_id": str(revised_acceptance.pk),
            "idempotency_key": "secondary-api-edit-forbidden",
            **_sensitive_code_payload(other_investor, "secondary_market_listing"),
        },
        content_type="application/json",
    )

    client.force_login(cast(Any, investor))
    response = client.post(
        f"/api/v1/marketplace/secondary/listings/{listing.id}/edit/",
        {
            "price_bps": 9800,
            "document_acceptance_id": str(revised_acceptance.pk),
            "idempotency_key": "secondary-api-edit-ok",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        },
        content_type="application/json",
    )

    listing.refresh_from_db()
    assert forbidden.status_code == 400
    assert response.status_code == 200
    assert response.json()["id"] == str(listing.id)
    assert response.json()["price_bps"] == 9800
    assert listing.price_bps == 9800
    assert SecondaryMarketListingEvent.objects.filter(
        listing=listing,
        event_type=SecondaryMarketListingEventType.EDITED,
    ).exists()


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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    deposit = _declare_deposit(
        admin_user,
        other_investor,
        amount_minor=20_000_00,
        idempotency_key="secondary-purchase-buyer-deposit",
    )
    review = _review_purchase(other_investor, listing)
    purchase_acceptance = _create_purchase_acceptance(other_investor, listing, review=review)
    purchase_code = _sensitive_code_payload(other_investor, "secondary_market_purchase")

    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            idempotency_key="secondary-purchase-1",
            **_expected_terms(review),
            **purchase_code,
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
    purchase_emails = OutboxMessage.objects.filter(
        topic__in=[
            "email.secondary_market_purchase_confirmation",
            "email.secondary_market_sale_confirmation",
        ]
    ).order_by("idempotency_key")
    assert purchase_emails.count() == 2
    assert {
        (message.topic, message.payload["user_id"]) for message in purchase_emails
    } == {
        ("email.secondary_market_sale_confirmation", str(investor.pk)),
        ("email.secondary_market_purchase_confirmation", str(other_investor.pk)),
    }

    replay = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            idempotency_key="secondary-purchase-1",
            **_expected_terms(review),
            **purchase_code,
        )
    )
    assert replay.id == purchase.id
    assert SecondaryMarketPurchase.objects.count() == 1
    assert (
        OutboxMessage.objects.filter(
            topic__in=[
                "email.secondary_market_purchase_confirmation",
                "email.secondary_market_sale_confirmation",
            ]
        ).count()
        == 2
    )
    assert SecondaryMarketListingEvent.objects.filter(
        listing=listing,
        event_type=SecondaryMarketListingEventType.SOLD,
    ).exists()
    assert AuditEvent.objects.filter(action="secondary_market.purchase_completed").exists()
    assert DomainEvent.objects.filter(event_type="SecondaryMarketPurchaseCompleted").exists()


@pytest.mark.django_db
def test_purchase_listing_requires_sensitive_action_code(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    seller_holding = _create_holding(admin_user, investor, loan)
    listing_acceptance = _create_listing_acceptance(
        investor,
        seller_holding,
        idempotency_key="secondary-purchase-missing-code-listing-accept",
    )
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, seller_holding).id),
            price_bps=9500,
            document_acceptance_id=str(listing_acceptance.pk),
            idempotency_key="secondary-purchase-missing-code-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    _declare_deposit(
        admin_user,
        other_investor,
        amount_minor=20_000_00,
        idempotency_key="secondary-purchase-missing-code-deposit",
    )
    purchase_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        idempotency_key="secondary-purchase-missing-code-accept",
    )

    with pytest.raises(SecondaryMarketValidationError, match="Sensitive-action email code"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(purchase_acceptance.pk),
                idempotency_key="secondary-purchase-missing-code",
                **_expected_terms(_review_purchase(other_investor, listing)),
            )
        )

    assert SecondaryMarketPurchase.objects.count() == 0


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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    _declare_deposit(
        admin_user,
        other_investor,
        idempotency_key="secondary-purchase-negative-deposit",
    )
    other_purchase_code = _sensitive_code_payload(
        other_investor,
        "secondary_market_purchase",
    )
    reviewed_terms = _expected_terms(_review_purchase(other_investor, listing))
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
                **reviewed_terms,
                **other_purchase_code,
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
                **reviewed_terms,
                **_sensitive_code_payload(investor, "secondary_market_purchase"),
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
                **reviewed_terms,
                **other_purchase_code,
            )
        )

    fresh_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        idempotency_key="secondary-purchase-fresh-before-stale-status",
    )
    cast(Any, loan).status = "late"
    loan.save(update_fields=["status"])
    with pytest.raises(
        SecondaryMarketValidationError,
        match="no longer available because the loan is late or in default",
    ):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(fresh_acceptance.pk),
                idempotency_key="secondary-purchase-stale-status",
                **reviewed_terms,
                **other_purchase_code,
            )
        )


@pytest.mark.django_db
def test_previously_approved_listing_of_a_late_loan_cannot_be_seen_or_bought(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    listing = _legacy_approval_request(admin_user, investor, key="secondary-approved-late")
    # The retired workflow could publish it with a disclosure note.
    SecondaryMarketListing.objects.filter(pk=listing.pk).update(
        status=SecondaryMarketListingStatus.ACTIVE,
        public_disclosure_note="Loan is late.",
    )
    listing.refresh_from_db()
    _declare_deposit(
        admin_user,
        other_investor,
        idempotency_key="secondary-approved-late-deposit",
    )
    acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review={
            "listing_id": str(listing.id),
            "currency": "CHF",
            "price_bps": 9000,
            "current_principal_minor": int(listing.current_principal_minor),
            "buyer_total_cost_minor": int(listing.buyer_total_cost_minor),
        },
    )

    assert list_active_secondary_market_listings(actor=other_investor) == []
    with pytest.raises(SecondaryMarketValidationError, match="not available"):
        get_active_secondary_market_listing_detail(
            actor=other_investor,
            listing_id=str(listing.id),
        )
    with pytest.raises(SecondaryMarketValidationError, match="late or in default"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(acceptance.pk),
                risk_acknowledgement_accepted=True,
                idempotency_key="secondary-approved-late-purchase",
                expected_buyer_total_cost_minor=int(listing.buyer_total_cost_minor),
                expected_price_bps=9000,
                expected_current_principal_minor=int(listing.current_principal_minor),
                **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
            )
        )
    assert not SecondaryMarketPurchase.objects.exists()


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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    _declare_deposit(
        admin_user,
        other_investor,
        idempotency_key="secondary-api-purchase-deposit",
    )
    review = _review_purchase(other_investor, listing)
    purchase_acceptance = _create_purchase_acceptance(other_investor, listing, review=review)
    client = Client()
    client.force_login(cast(Any, other_investor))

    response = client.post(
        f"/api/v1/marketplace/secondary/listings/{listing.id}/purchase/",
        {
            "document_acceptance_id": str(purchase_acceptance.pk),
            "idempotency_key": "secondary-api-purchase",
            **_expected_terms(review),
            **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
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
            **_expected_terms(_review_purchase(other_investor, listing)),
            **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
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


@pytest.mark.django_db
def test_qa_clock_direct_resale_lot_is_yours_since_the_purchase_not_activation(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # QA row 87: the bought lot carries the purchase date ("Yours since"); the seller's
    # lot and the buyer's own original lot keep their original assignment date.
    import backend.apps.secondary_market.services as secondary_services

    monkeypatch.setattr(secondary_services, "now_utc", now_utc)
    purchased_at = datetime(2026, 1, 16, 12, 0, tzinfo=ZoneInfo("Europe/Zurich"))
    original_at = datetime.combine(date(2026, 1, 1), time.min, tzinfo=ZoneInfo("Europe/Zurich"))
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    seller_lot = _create_holding(admin_user, investor, loan)
    buyer_original_lot = _create_holding(
        admin_user,
        other_investor,
        loan,
        idempotency_key="secondary-holding-buyer-original",
    )
    with qa_clock(purchased_at):
        listing = create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, seller_lot).id),
                price_bps=10_000,
                document_acceptance_id=str(_create_listing_acceptance(investor, seller_lot).pk),
                idempotency_key="secondary-r87-listing",
                **_sensitive_code_payload(investor, "secondary_market_listing"),
            )
        )
        _declare_deposit(admin_user, other_investor, idempotency_key="secondary-r87-deposit")
        purchase = purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(_create_purchase_acceptance(other_investor, listing).pk),
                idempotency_key="secondary-r87-purchase",
                **_expected_terms(_review_purchase(other_investor, listing)),
                **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
            )
        )
        portfolio = import_module("backend.apps.investor_portal.services").get_investor_portfolio(
            actor=other_investor
        )

    cast(Any, seller_lot).refresh_from_db()
    cast(Any, buyer_original_lot).refresh_from_db()
    assert purchase.purchased_at == purchased_at
    assert purchase.buyer_holding.assignment_effective_at == purchased_at
    assert cast(Any, seller_lot).assignment_effective_at == original_at
    assert cast(Any, buyer_original_lot).assignment_effective_at == original_at
    yours_since = {row["id"]: row["assignment_effective_at"] for row in portfolio["holdings"]}
    assert yours_since == {
        str(cast(Any, buyer_original_lot).id): original_at,
        str(purchase.buyer_holding.id): purchased_at,
    }


def _list_holding_for_sale(
    seller: Model,
    holding: Model,
    *,
    price_bps: int,
    key: str,
) -> Any:
    acceptance = _create_listing_acceptance(
        seller,
        holding,
        idempotency_key=f"{key}-acceptance",
    )
    return create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=seller,
            holding_id=str(cast(Any, holding).id),
            price_bps=price_bps,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=key,
            **_sensitive_code_payload(seller, "secondary_market_listing"),
        )
    )


def _edit_listing_price(seller: Model, listing: Any, *, price_bps: int, key: str) -> Any:
    acceptance = _create_listing_acceptance(
        seller,
        listing.holding,
        idempotency_key=f"{key}-acceptance",
    )
    return edit_secondary_market_listing(
        EditSecondaryMarketListingCommand(
            actor=seller,
            listing_id=str(listing.id),
            price_bps=price_bps,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=key,
            **_sensitive_code_payload(seller, "secondary_market_listing"),
        )
    )


def _journal_entry_count() -> int:
    return int(apps.get_model("ledger", "LedgerJournalEntry").objects.count())


@pytest.mark.django_db
def test_purchase_rejects_seller_price_edit_between_review_and_confirm(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    # Audit A-01 / SECONDARY-01 (c): the seller edited a CHF 10,000 listing to
    # 1,000,000 bps while the buyer's review was open; the buyer was charged 100x.
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="lock-edit-list")
    deposit = _declare_deposit(admin_user, other_investor, idempotency_key="lock-edit-deposit")
    review = _review_purchase(other_investor, listing)
    acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=review,
        idempotency_key="lock-edit-accept",
    )
    purchase_code = _sensitive_code_payload(other_investor, "secondary_market_purchase")
    journal_entries_before = _journal_entry_count()

    def confirm(acceptance_id: str, reviewed: dict[str, Any], key: str) -> SecondaryMarketPurchase:
        return purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=acceptance_id,
                idempotency_key=key,
                **_expected_terms(reviewed),
                **purchase_code,
            )
        )

    _edit_listing_price(investor, listing, price_bps=1_000_000, key="lock-edit-extreme")
    with pytest.raises(SecondaryMarketPriceChangedError, match="price of this listing changed"):
        confirm(str(acceptance.pk), review, "lock-edit-buy-1")

    _edit_listing_price(investor, listing, price_bps=10_500, key="lock-edit-premium")
    with pytest.raises(SecondaryMarketPriceChangedError):
        confirm(str(acceptance.pk), review, "lock-edit-buy-2")

    # Nothing moved: no purchase, no journal entry, buyer balance untouched,
    # listing still open and the seller still owns the holding.
    listing.refresh_from_db()
    cast(Any, holding).refresh_from_db()
    deposit.balance_lot.refresh_from_db()
    assert SecondaryMarketPurchase.objects.count() == 0
    assert _journal_entry_count() == journal_entries_before
    assert deposit.balance_lot.available_amount_minor == 20_000_00
    assert listing.status == SecondaryMarketListingStatus.ACTIVE
    assert cast(Any, holding).status == "active"

    # The buyer reviews the new price and confirms again. The rejection happened
    # before the email code was checked, so the same code is still usable.
    new_review = _review_purchase(other_investor, listing)
    assert new_review["price_bps"] == 10_500
    assert new_review["buyer_total_cost_minor"] != review["buyer_total_cost_minor"]
    new_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=new_review,
        idempotency_key="lock-edit-accept-2",
    )
    purchase = confirm(str(new_acceptance.pk), new_review, "lock-edit-buy-3")

    deposit.balance_lot.refresh_from_db()
    assert purchase.price_bps == 10_500
    assert purchase.current_principal_minor == 10_000_00
    assert purchase.buyer_total_cost_minor == new_review["buyer_total_cost_minor"]
    assert (
        purchase.purchase_document_acceptance.data_snapshot["buyer_total_cost_minor"]
        == purchase.buyer_total_cost_minor
    )
    assert deposit.balance_lot.available_amount_minor == (
        20_000_00 - purchase.buyer_total_cost_minor
    )


@pytest.mark.django_db
def test_purchase_rejects_acceptance_evidence_that_differs_from_the_charge(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    # The acceptance snapshot is the source of the purchase document, so it must
    # state the same total that settlement charges.
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="lock-doc-list")
    _declare_deposit(admin_user, other_investor, idempotency_key="lock-doc-deposit")
    stale_review = _review_purchase(other_investor, listing)
    stale_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=stale_review,
        idempotency_key="lock-doc-stale-accept",
    )
    _edit_listing_price(investor, listing, price_bps=9_000, key="lock-doc-edit")
    fresh_review = _review_purchase(other_investor, listing)
    purchase_code = _sensitive_code_payload(other_investor, "secondary_market_purchase")

    # Fresh expected values cannot be paired with evidence of the old total.
    with pytest.raises(SecondaryMarketPriceChangedError):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(stale_acceptance.pk),
                idempotency_key="lock-doc-buy-stale",
                **_expected_terms(fresh_review),
                **purchase_code,
            )
        )

    blank_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review={"listing_id": str(listing.id)},
        idempotency_key="lock-doc-blank-accept",
    )
    with pytest.raises(SecondaryMarketValidationError, match="record the reviewed total"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(blank_acceptance.pk),
                idempotency_key="lock-doc-buy-blank",
                **_expected_terms(fresh_review),
                **purchase_code,
            )
        )
    assert SecondaryMarketPurchase.objects.count() == 0


@pytest.mark.django_db
def test_purchase_rejects_servicing_repricing_between_review_and_confirm(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    # Audit A-01 / SECONDARY-01 (a): a repayment repriced the listing from CHF
    # 6,000 to CHF 4,019.87 principal and the buyer silently bought the new claim.
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    _create_current_installment(loan, due_date=date(2026, 1, 20))
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
    listing = _list_holding_for_sale(investor, holding, price_bps=10_100, key="lock-repay-list")
    deposit = _declare_deposit(admin_user, other_investor, idempotency_key="lock-repay-deposit")
    review = _review_purchase(other_investor, listing)
    acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=review,
        idempotency_key="lock-repay-accept",
    )
    purchase_code = _sensitive_code_payload(other_investor, "secondary_market_purchase")

    servicing = import_module("backend.apps.servicing.services")
    servicing.record_borrower_repayment(
        servicing.RecordBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=2_300_00,
            booking_date=date(2026, 1, 16),
            value_date=date(2026, 1, 16),
            collection_account_identifier="GARANTA-CHF",
            payer_name="Secondary Borrower AG",
            payer_account_identifier="CH22BORROWER",
            bank_reference="BANK-lock-repay",
            payment_reference=f"LOAN-{loan.pk}",
            evidence_reference="statement:lock-repay",
            early_regular_payment_acknowledged=True,
            idempotency_key="lock-repay-repayment",
        )
    )
    listing.refresh_from_db()
    assert listing.price_bps == 10_100
    assert listing.current_principal_minor == 8_000_00
    journal_entries_before = _journal_entry_count()

    with pytest.raises(SecondaryMarketPriceChangedError):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="lock-repay-buy-stale",
                **_expected_terms(review),
                **purchase_code,
            )
        )
    deposit.balance_lot.refresh_from_db()
    assert SecondaryMarketPurchase.objects.count() == 0
    assert _journal_entry_count() == journal_entries_before
    assert deposit.balance_lot.available_amount_minor == 20_000_00

    new_review = _review_purchase(other_investor, listing)
    new_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=new_review,
        idempotency_key="lock-repay-accept-2",
    )
    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(new_acceptance.pk),
            idempotency_key="lock-repay-buy",
            **_expected_terms(new_review),
            **purchase_code,
        )
    )
    assert purchase.current_principal_minor == 8_000_00
    assert purchase.transfer_price_minor == 8_080_00
    assert purchase.buyer_total_cost_minor == new_review["buyer_total_cost_minor"]


@pytest.mark.django_db
def test_purchase_rejects_a_price_change_that_lands_after_the_early_check(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Race: the seller's edit commits after the early check but before the
    # settlement locks are taken. The check under the locks must still reject it.
    secondary_services = import_module("backend.apps.secondary_market.services")
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="lock-race-list")
    _declare_deposit(admin_user, other_investor, idempotency_key="lock-race-deposit")
    review = _review_purchase(other_investor, listing)
    acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=review,
        idempotency_key="lock-race-accept",
    )
    real_verify = secondary_services.verify_sensitive_action_code

    def verify_then_seller_edits(command: Any) -> Any:
        result = real_verify(command)
        secondary_services.SecondaryMarketListing.objects.filter(id=listing.id).update(
            price_bps=11_000
        )
        return result

    monkeypatch.setattr(
        secondary_services,
        "verify_sensitive_action_code",
        verify_then_seller_edits,
    )
    journal_entries_before = _journal_entry_count()

    with pytest.raises(SecondaryMarketPriceChangedError):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="lock-race-buy",
                **_expected_terms(review),
                **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
            )
        )
    assert SecondaryMarketPurchase.objects.count() == 0
    assert _journal_entry_count() == journal_entries_before


@pytest.mark.django_db
def test_purchase_review_from_an_earlier_business_day_is_rejected_when_accrual_changed(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Accrued interest grows every business day. A buyer who reviewed yesterday
    # must review today's total; the platform never charges an unseen amount.
    secondary_services = import_module("backend.apps.secondary_market.services")
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="lock-day-list")
    _declare_deposit(admin_user, other_investor, idempotency_key="lock-day-deposit")
    review = _review_purchase(other_investor, listing)
    acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=review,
        idempotency_key="lock-day-accept",
    )
    purchase_code = _sensitive_code_payload(other_investor, "secondary_market_purchase")

    next_day = datetime(2026, 1, 17, 12, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr(secondary_services, "now_utc", lambda: next_day)
    with pytest.raises(SecondaryMarketPriceChangedError):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="lock-day-buy-stale",
                **_expected_terms(review),
                **purchase_code,
            )
        )

    todays_review = _review_purchase(other_investor, listing)
    assert todays_review["buyer_total_cost_minor"] > review["buyer_total_cost_minor"]
    todays_acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=todays_review,
        idempotency_key="lock-day-accept-2",
    )
    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(todays_acceptance.pk),
            idempotency_key="lock-day-buy",
            **_expected_terms(todays_review),
            **purchase_code,
        )
    )
    assert purchase.accrued_interest_to_date == date(2026, 1, 17)
    assert purchase.buyer_total_cost_minor == todays_review["buyer_total_cost_minor"]


@pytest.mark.django_db
def test_purchase_replay_returns_the_original_and_rejects_other_economics(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secondary_services = import_module("backend.apps.secondary_market.services")
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=9_900, key="lock-replay-list")
    _declare_deposit(admin_user, other_investor, idempotency_key="lock-replay-deposit")
    review = _review_purchase(other_investor, listing)
    acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review=review,
        idempotency_key="lock-replay-accept",
    )
    purchase_code = _sensitive_code_payload(other_investor, "secondary_market_purchase")

    def buy(terms: ExpectedPurchaseTerms) -> SecondaryMarketPurchase:
        return purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="lock-replay-buy",
                **terms,
                **purchase_code,
            )
        )

    purchase = buy(_expected_terms(review))
    journal_entries_after_purchase = _journal_entry_count()

    # A client retry with the same key and the same reviewed values gets the
    # original purchase back, even on a later business day.
    monkeypatch.setattr(
        secondary_services,
        "now_utc",
        lambda: datetime(2026, 1, 18, 9, 0, tzinfo=ZoneInfo("UTC")),
    )
    assert buy(_expected_terms(review)).id == purchase.id

    # The same key with different economics is a different request.
    other_terms = _expected_terms(review)
    other_terms["expected_buyer_total_cost_minor"] += 1
    with pytest.raises(SecondaryMarketValidationError, match="different purchase request"):
        buy(other_terms)
    assert SecondaryMarketPurchase.objects.count() == 1
    assert _journal_entry_count() == journal_entries_after_purchase


@pytest.mark.django_db
def test_secondary_market_api_purchase_price_change_returns_conflict_code(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="lock-api-list")
    _declare_deposit(admin_user, other_investor, idempotency_key="lock-api-deposit")
    client = Client()
    client.force_login(cast(Any, other_investor))
    review = client.get(f"/api/v1/marketplace/secondary/listings/{listing.id}/").json()
    acceptance = _create_purchase_acceptance(
        other_investor,
        listing,
        review={
            "listing_id": review["id"],
            "buyer_total_cost_minor": review["buyer_total_cost_minor"],
            "currency": review["currency"],
            "price_bps": review["price_bps"],
            "current_principal_minor": review["current_principal_minor"],
        },
        idempotency_key="lock-api-accept",
    )
    body = {
        "document_acceptance_id": str(acceptance.pk),
        "idempotency_key": "lock-api-buy",
        "expected_buyer_total_cost_minor": review["buyer_total_cost_minor"],
        "expected_price_bps": review["price_bps"],
        "expected_current_principal_minor": review["current_principal_minor"],
        **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
    }
    purchase_url = f"/api/v1/marketplace/secondary/listings/{listing.id}/purchase/"

    missing = client.post(
        purchase_url,
        {key: value for key, value in body.items() if key != "expected_buyer_total_cost_minor"},
        content_type="application/json",
    )
    assert missing.status_code == 400
    assert "expected_buyer_total_cost_minor" in missing.json()

    _edit_listing_price(investor, listing, price_bps=1_000_000, key="lock-api-edit")
    conflict = client.post(purchase_url, body, content_type="application/json")
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": "The price of this listing changed. Review the new price and confirm again.",
        "code": "secondary_price_changed",
    }
    assert SecondaryMarketPurchase.objects.count() == 0


@pytest.mark.django_db
def test_direct_first_sale_accrues_from_the_loan_start_not_the_holding_assignment(
    admin_user: Model,
    investor: Model,
) -> None:
    # The schedule charges the borrower interest from the loan start date, and
    # the holder at the first installment receives all of it. A holding assigned
    # one day after the loan start (funding closed the next day) therefore sells
    # with accrued interest from the loan start.
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user, loan_start_date=date(2025, 12, 31))
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="accrual-start")

    assert listing.accrued_interest_from_date == date(2025, 12, 31)
    assert listing.accrued_interest_to_date == date(2026, 1, 16)
    # 10,000.00 x 12% x 16 / 365 = 52.60
    assert listing.accrued_interest_minor == 52_60


@pytest.mark.django_db
def test_direct_resale_chain_charges_the_next_buyer_accrued_interest_from_the_interest_start(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Audit A-02 / SECONDARY-02 / FINCODE-03: A sells to B mid-period, B sells to
    # C in the same period. C receives the whole next installment interest, so C
    # must pay accrued interest from the interest start, not from B's purchase.
    import backend.apps.secondary_market.services as secondary_services

    monkeypatch.setattr(secondary_services, "now_utc", now_utc)
    user_model: Any = get_user_model()
    third_investor = cast(
        Model,
        user_model.objects.create_user(
            email="secondary-third@example.test",
            full_name="Secondary Third",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )
    seller_a, buyer_b, buyer_c = investor, other_investor, third_investor
    for user in (seller_a, buyer_b, buyer_c):
        _approve_financial_access(user)
    loan = _create_funded_loan(admin_user, principal_minor=10_000_00)
    installment_model = apps.get_model("loans", "LoanInstallment")
    installment_model.objects.create(
        loan=loan,
        schedule_version=cast(Any, loan).schedule_version,
        installment_number=1,
        due_date=date(2026, 2, 1),
        principal_minor=0,
        interest_minor=100_00,
        total_minor=100_00,
        metadata={},
    )
    installment_model.objects.create(
        loan=loan,
        schedule_version=cast(Any, loan).schedule_version,
        installment_number=2,
        due_date=date(2026, 3, 1),
        principal_minor=10_000_00,
        interest_minor=100_00,
        total_minor=10_100_00,
        metadata={},
    )
    holding_a = _create_holding(admin_user, seller_a, loan, current_principal_minor=10_000_00)
    zurich = ZoneInfo("Europe/Zurich")

    def sell(seller: Model, holding: Model, buyer: Model, key: str) -> SecondaryMarketPurchase:
        listing = _list_holding_for_sale(seller, holding, price_bps=10_000, key=f"{key}-list")
        review = _review_purchase(buyer, listing)
        return purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=buyer,
                listing_id=str(listing.id),
                document_acceptance_id=str(
                    _create_purchase_acceptance(
                        buyer,
                        listing,
                        review=review,
                        idempotency_key=f"{key}-accept",
                    ).pk
                ),
                idempotency_key=f"{key}-buy",
                **_expected_terms(review),
                **_sensitive_code_payload(buyer, "secondary_market_purchase"),
            )
        )

    with qa_clock(datetime(2026, 1, 11, 10, 0, tzinfo=zurich)):
        _declare_deposit(admin_user, buyer_b, idempotency_key="chain-deposit-b")
        _declare_deposit(admin_user, buyer_c, idempotency_key="chain-deposit-c")
        a_to_b = sell(seller_a, holding_a, buyer_b, "chain-ab")
    with qa_clock(datetime(2026, 1, 21, 10, 0, tzinfo=zurich)):
        b_to_c = sell(buyer_b, a_to_b.buyer_holding, buyer_c, "chain-bc")

    # A -> B: 10 days from the loan start (2026-01-01). 10,000 x 12% x 10/365.
    assert a_to_b.accrued_interest_from_date == date(2026, 1, 1)
    assert a_to_b.accrued_interest_minor == 32_88
    # B -> C: C pays the full 20 days from the loan start, not 10 days from B's
    # purchase (the bug charged 32.88 here and B lost what B paid A).
    assert b_to_c.accrued_interest_from_date == date(2026, 1, 1)
    assert b_to_c.accrued_interest_to_date == date(2026, 1, 21)
    assert b_to_c.accrued_interest_minor == 65_75
    # B keeps exactly the interest for B's own 10 days (rounding to the cent).
    b_interest_net = b_to_c.accrued_interest_minor - a_to_b.accrued_interest_minor
    assert abs(b_interest_net - 32_88) <= 1

    servicing = import_module("backend.apps.servicing.services")
    with qa_clock(datetime(2026, 2, 1, 10, 0, tzinfo=zurich)):
        repayment = servicing.record_borrower_repayment(
            servicing.RecordBorrowerRepaymentCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                amount_minor=100_00,
                booking_date=date(2026, 2, 1),
                value_date=date(2026, 2, 1),
                collection_account_identifier="GARANTA-CHF",
                payer_name="Secondary Borrower AG",
                payer_account_identifier="CH22BORROWER",
                bank_reference="BANK-chain-installment-1",
                payment_reference=f"LOAN-{loan.pk}",
                evidence_reference="statement:chain-installment-1",
                idempotency_key="chain-installment-1",
            )
        )
    # C, the holder on the due date, receives the whole installment interest.
    assert [
        (str(line.investor_user_id), line.interest_minor)
        for line in repayment.distribution_lines
    ] == [(str(buyer_c.pk), 100_00)]
    # Interest for the period splits by holding days: A 10, B 10, C 11 days.
    a_interest = a_to_b.accrued_interest_minor
    c_interest_net = 100_00 - b_to_c.accrued_interest_minor
    assert a_interest + b_interest_net + c_interest_net == 100_00
    assert c_interest_net == 34_25


def _put_investor_in_penalty_mode(admin_user: Model, investor: Model) -> None:
    ledger = import_module("backend.apps.ledger.services")
    deposit = _declare_deposit(
        admin_user,
        investor,
        amount_minor=500_00,
        value_date=date(2025, 10, 1),
        idempotency_key="penalty-mode-old-deposit",
    )
    # No usable IBAN at day 60: the deposit's IBAN was revoked.
    ledger.revoke_investor_payout_instruction(
        ledger.RevokeInvestorPayoutInstructionCommand(
            actor=admin_user,
            instruction_id=str(deposit.payout_instruction.pk),
            reason="Returned by the bank.",
        )
    )
    ledger.run_balance_ageing_scan(
        ledger.RunBalanceAgeingScanCommand(
            actor=admin_user,
            as_of=datetime(2026, 1, 16, 12, 0, tzinfo=ZoneInfo("UTC")),
        )
    )
    assert ledger.investor_has_penalty_mode_balance(str(investor.pk))


@pytest.mark.django_db
def test_penalty_mode_seller_cannot_list_or_change_a_listing_but_can_cancel(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="penalty-listed")
    other_loan = _create_funded_loan(admin_user)
    other_holding = _create_holding(
        admin_user,
        investor,
        other_loan,
        idempotency_key="secondary-holding-penalty-2",
    )
    _put_investor_in_penalty_mode(admin_user, investor)

    # The freeze is checked before the email code, so no code is spent.
    unused_code = {"sensitive_action_code_id": str(uuid4()), "sensitive_action_code": "000000"}
    other_acceptance = _create_listing_acceptance(
        investor,
        other_holding,
        idempotency_key="penalty-new-acceptance",
    )
    with pytest.raises(SecondaryMarketValidationError, match="Listing a holding for sale"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, other_holding).id),
                price_bps=10_000,
                document_acceptance_id=str(other_acceptance.pk),
                idempotency_key="penalty-new",
                **unused_code,
            )
        )
    edit_acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="penalty-edit-acceptance",
    )
    with pytest.raises(SecondaryMarketValidationError, match="Changing a listing"):
        edit_secondary_market_listing(
            EditSecondaryMarketListingCommand(
                actor=investor,
                listing_id=str(listing.id),
                price_bps=9_900,
                document_acceptance_id=str(edit_acceptance.pk),
                idempotency_key="penalty-edit",
                **unused_code,
            )
        )
    cancelled = cancel_secondary_market_listing(
        CancelSecondaryMarketListingCommand(
            actor=investor,
            listing_id=str(listing.id),
            reason="Frozen account.",
            idempotency_key="penalty-cancel",
        )
    )
    assert cancelled.status == SecondaryMarketListingStatus.CANCELLED

@pytest.mark.django_db
def test_c18_migration_cancels_approval_requests_and_non_performing_open_listings(
    admin_user: Model,
    investor: Model,
) -> None:
    migration = import_module(
        "backend.apps.secondary_market.migrations.0009_cancel_late_or_defaulted_listings"
    )
    _approve_financial_access(investor)
    requested = _legacy_approval_request(admin_user, investor, key="c18-requested")
    approved = _legacy_approval_request(admin_user, investor, key="c18-approved")
    SecondaryMarketListing.objects.filter(pk=approved.pk).update(
        status=SecondaryMarketListingStatus.ACTIVE
    )
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=approved.loan_id).update(status="defaulted")
    performing_loan = _create_funded_loan(admin_user)
    performing_holding = _create_holding(
        admin_user, investor, performing_loan, idempotency_key="c18-performing-holding"
    )
    performing_acceptance = _create_listing_acceptance(
        investor, performing_holding, idempotency_key="c18-performing-accept"
    )
    performing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, performing_holding).id),
            price_bps=10_000,
            document_acceptance_id=str(performing_acceptance.pk),
            idempotency_key="c18-performing-listing",
            **_sensitive_code_payload(investor, "secondary_market_listing"),
        )
    )
    journal_model = apps.get_model("ledger", "LedgerJournalEntry")
    journals_before = journal_model.objects.count()

    migration.cancel_late_or_defaulted_listings(apps, None)
    migration.cancel_late_or_defaulted_listings(apps, None)

    requested.refresh_from_db()
    approved.refresh_from_db()
    performing.refresh_from_db()
    assert requested.status == SecondaryMarketListingStatus.CANCELLED
    assert "the loan is late" in requested.cancellation_reason
    assert approved.status == SecondaryMarketListingStatus.CANCELLED
    assert "the loan is in default" in approved.cancellation_reason
    assert performing.status == SecondaryMarketListingStatus.ACTIVE
    assert journal_model.objects.count() == journals_before
    for cancelled in (requested, approved):
        assert cancelled.listed_at is None
        assert cancelled.metadata["c18_rule_migration"]["loan_status"] in {"late", "defaulted"}
        events = SecondaryMarketListingEvent.objects.filter(
            listing=cancelled,
            event_type=SecondaryMarketListingEventType.AUTO_CANCELLED,
        )
        assert events.count() == 1
        event = events.get()
        assert str(event.actor_user_id) == "00000000-0000-0000-0000-000000000000"
        assert event.actor_account_type == "system"
        assert event.note == cancelled.cancellation_reason
    notices = OutboxMessage.objects.filter(
        topic="email.secondary_market_listing_status",
        idempotency_key__endswith=":c18-rule-migration",
    )
    assert sorted(cast(Any, notice).payload["metadata"]["listing_id"] for notice in notices) == (
        sorted([str(requested.id), str(approved.id)])
    )
    assert all(
        "No money was moved" in cast(Any, notice).payload["body_text"] for notice in notices
    )


@pytest.fixture
def superadmin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_superuser(
            email="secondary-superadmin@example.test",
            password="AdminPass123!",
            full_name="Secondary Superadmin",
        ),
    )


def _documents() -> Any:
    return import_module("backend.apps.documents.services")


def _publish_terms(superadmin_user: Model, category: str) -> Any:
    documents = _documents()
    return documents.create_document_template_version(
        documents.CreateDocumentTemplateVersionCommand(
            actor=superadmin_user,
            category=category,
            name=f"{category} terms",
            title=f"{category} terms",
            body="Terms of {{platform.name}} operated by {{operator.name}}.",
            checkbox_labels=["I accept these terms."],
            publish_now=True,
            legal_review_reference="legal-review-test",
        )
    )


def _accept_terms(
    actor: Model,
    version: Any,
    *,
    category: str,
    context_type: str,
    context_id: str,
    snapshot: dict[str, Any],
    key: str,
) -> Any:
    documents = _documents()
    return documents.accept_document_terms(
        documents.AcceptDocumentTermsCommand(
            actor=actor,
            category=category,
            expected_template_version_id=str(version.id),
            accepted_checkbox_labels=["I accept these terms."],
            context_type=context_type,
            context_id=context_id,
            data_snapshot=snapshot,
            idempotency_key=key,
        )
    )


@pytest.mark.django_db
def test_purchase_acceptance_snapshot_is_built_from_the_real_listing(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    """SECCODE-11: the buyer cannot write the money terms or the seller into the evidence."""
    documents = _documents()
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    holding = _create_holding(admin_user, investor, _create_funded_loan(admin_user))
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="server-snapshot")
    version = _publish_terms(superadmin_user, "secondary_market_purchase")
    review = _review_purchase(other_investor, listing)
    forged = {
        **review,
        "buyer_total_cost_minor": 1,
        "seller": {"full_name": "Forged Seller AG"},
        "listing": {"price_bps": 1},
    }

    # A forged total is a price the platform never offered: refused, nothing recorded.
    with pytest.raises(documents.DocumentConflictError) as conflict:
        _accept_terms(
            other_investor,
            version,
            category="secondary_market_purchase",
            context_type="secondary_market_purchase",
            context_id=str(listing.id),
            snapshot=forged,
            key="forged-total",
        )
    assert conflict.value.code == "secondary_price_changed"
    # Unknown, foreign-context and own listings are refused.
    with pytest.raises(documents.DocumentValidationError, match="does not exist"):
        _accept_terms(
            other_investor,
            version,
            category="secondary_market_purchase",
            context_type="secondary_market_purchase",
            context_id="00000000-0000-0000-0000-000000000001",
            snapshot=review,
            key="unknown-listing",
        )
    with pytest.raises(documents.DocumentValidationError, match="must reference the listing"):
        _accept_terms(
            other_investor,
            version,
            category="secondary_market_purchase",
            context_type="primary_order",
            context_id=str(listing.id),
            snapshot=review,
            key="wrong-context-type",
        )
    with pytest.raises(documents.DocumentValidationError, match="own listing"):
        _accept_terms(
            investor,
            version,
            category="secondary_market_purchase",
            context_type="secondary_market_purchase",
            context_id=str(listing.id),
            snapshot=review,
            key="own-listing",
        )
    acceptance_model = apps.get_model("documents", "DocumentAcceptanceEvidence")
    assert not acceptance_model.objects.filter(category="secondary_market_purchase").exists()

    # Client extras (a seller name, a nested listing price) never reach the evidence.
    acceptance = _accept_terms(
        other_investor,
        version,
        category="secondary_market_purchase",
        context_type="secondary_market_purchase",
        context_id=str(listing.id),
        snapshot={**review, "seller": {"full_name": "Forged Seller AG"}, "listing": {}},
        key="real-purchase-terms",
    )
    snapshot = acceptance.data_snapshot
    assert "seller" not in snapshot
    assert snapshot["buyer_total_cost_minor"] == review["buyer_total_cost_minor"]
    assert snapshot["listing"]["price_bps"] == 10_000
    assert snapshot["listing"]["buyer_total_cost_minor"] == review["buyer_total_cost_minor"]
    assert snapshot["loan"]["title"] == "Secondary bridge loan"
    assert snapshot["user"]["id"] == str(cast(Any, other_investor).pk)

    # Round-1 behaviour holds: the purchase charges exactly the recorded total.
    _declare_deposit(admin_user, other_investor, idempotency_key="server-snapshot-deposit")
    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="server-snapshot-purchase",
            **_expected_terms(review),
            **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
        )
    )
    assert purchase.buyer_total_cost_minor == snapshot["buyer_total_cost_minor"]


@pytest.mark.django_db
def test_listing_acceptance_snapshot_is_built_from_the_sellers_own_holding(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    documents = _documents()
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    version = _publish_terms(superadmin_user, "secondary_market_listing")

    with pytest.raises(documents.DocumentValidationError, match="Holding does not exist"):
        _accept_terms(
            other_investor,
            version,
            category="secondary_market_listing",
            context_type="secondary_market_listing",
            context_id=str(cast(Any, holding).id),
            snapshot={"price_bps": 10_000},
            key="foreign-holding",
        )
    with pytest.raises(documents.DocumentValidationError, match="Holding does not exist"):
        _accept_terms(
            investor,
            version,
            category="secondary_market_listing",
            context_type="secondary_market_listing",
            context_id="00000000-0000-0000-0000-000000000002",
            snapshot={"price_bps": 10_000},
            key="unknown-holding",
        )
    with pytest.raises(documents.DocumentValidationError, match="listing does not exist"):
        _accept_terms(
            investor,
            version,
            category="secondary_market_listing",
            context_type="secondary_market_listing",
            context_id=str(cast(Any, holding).id),
            snapshot={"price_bps": 10_000, "listing_id": "00000000-0000-0000-0000-000000000003"},
            key="unknown-listing-edit",
        )

    acceptance = _accept_terms(
        investor,
        version,
        category="secondary_market_listing",
        context_type="secondary_market_listing",
        context_id=str(cast(Any, holding).id),
        snapshot={
            "price_bps": 10_100,
            "current_principal_minor": 1,
            "currency": "EUR",
            "listing": {"seller_net_proceeds_minor": 999_999_999},
        },
        key="real-listing-terms",
    )
    snapshot = acceptance.data_snapshot
    assert snapshot["price_bps"] == 10_100
    assert snapshot["current_principal_minor"] == 10_000_00
    assert snapshot["currency"] == "CHF"
    assert snapshot["listing"]["transfer_price_minor"] == 10_100_00
    assert snapshot["listing"]["seller_net_proceeds_minor"] < 999_999_999
    assert snapshot["action"] == "create"

    # The listing must use the accepted price.
    with pytest.raises(SecondaryMarketValidationError, match="different price"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=10_200,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="listing-other-price",
                **_sensitive_code_payload(investor, "secondary_market_listing"),
            )
        )

    # A late loan cannot even get listing terms (rule C18).
    cast(Any, loan).status = "late"
    loan.save(update_fields=["status"])
    with pytest.raises(documents.DocumentValidationError, match="Late or defaulted loans"):
        _accept_terms(
            investor,
            version,
            category="secondary_market_listing",
            context_type="secondary_market_listing",
            context_id=str(cast(Any, holding).id),
            snapshot={"price_bps": 10_000},
            key="late-listing-terms",
        )


@pytest.mark.django_db
def test_acceptance_api_answers_409_when_the_reviewed_price_is_stale(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    holding = _create_holding(admin_user, investor, _create_funded_loan(admin_user))
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="api-stale-review")
    version = _publish_terms(superadmin_user, "secondary_market_purchase")
    review = _review_purchase(other_investor, listing)
    stale_total = review["buyer_total_cost_minor"] - 1
    client = Client()
    client.force_login(cast(Any, other_investor))

    response = client.post(
        "/api/v1/documents/acceptances/",
        {
            "category": "secondary_market_purchase",
            "expected_template_version_id": str(version.id),
            "accepted_checkbox_labels": ["I accept these terms."],
            "context_type": "secondary_market_purchase",
            "context_id": str(listing.id),
            "data_snapshot": {**review, "buyer_total_cost_minor": stale_total},
            "idempotency_key": "api-stale-review",
        },
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "secondary_price_changed"


@pytest.mark.django_db
def test_purchase_without_money_names_the_missing_balance_not_the_60_day_rule(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    """SECONDARY-08: a buyer with no CHF is told so; a purchase has no funding window."""
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    holding = _create_holding(admin_user, investor, _create_funded_loan(admin_user))
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="no-money")
    review = _review_purchase(other_investor, listing)
    acceptance = _create_purchase_acceptance(other_investor, listing, review=review)

    with pytest.raises(SecondaryMarketValidationError) as error:
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="no-money-purchase",
                **_expected_terms(review),
                **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
            )
        )

    assert str(error.value) == (
        "You have no available CHF balance. Add funds or exchange currency first."
    )
    assert not SecondaryMarketPurchase.objects.exists()


@pytest.mark.django_db
def test_seller_pricing_preview_matches_listing_and_same_day_sale_credit(
    client: Client,
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    # Audit A-34 / SECONDARY-07: the listing form shows the server's seller net
    # (transfer price + accrued interest - configured maker fee), not a browser
    # estimate without accrued interest and with a fixed 0.25 % fee.
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    client.force_login(cast(Any, investor))
    response = client.get(
        "/api/v1/marketplace/secondary/listings/pricing-preview/",
        {"holding_id": str(cast(Any, holding).id), "price_bps": "9500"},
    )
    assert response.status_code == 200
    preview = response.json()
    assert preview["transfer_price_minor"] == 9_500_00
    assert preview["accrued_interest_minor"] == 4_932
    assert preview["maker_fee_minor"] == 2_375
    assert preview["seller_net_proceeds_minor"] == 9_500_00 + 4_932 - 2_375
    assert preview["pricing_date"] == "2026-01-16"

    listing = _list_holding_for_sale(investor, holding, price_bps=9500, key="preview-listing")
    assert listing.seller_net_proceeds_minor == preview["seller_net_proceeds_minor"]
    assert listing.maker_fee_minor == preview["maker_fee_minor"]
    assert listing.accrued_interest_minor == preview["accrued_interest_minor"]

    _declare_deposit(admin_user, other_investor, idempotency_key="preview-buyer-deposit")
    review = _review_purchase(other_investor, listing)
    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(
                _create_purchase_acceptance(other_investor, listing, review=review).pk
            ),
            idempotency_key="preview-purchase",
            **_expected_terms(review),
            **_sensitive_code_payload(other_investor, "secondary_market_purchase"),
        )
    )
    assert purchase.seller_balance_lot.available_amount_minor == preview[
        "seller_net_proceeds_minor"
    ]

    client.force_login(cast(Any, other_investor))
    not_owner = client.get(
        "/api/v1/marketplace/secondary/listings/pricing-preview/",
        {"holding_id": str(cast(Any, holding).id), "price_bps": "9500"},
    )
    assert not_owner.status_code == 400


@pytest.mark.django_db
def test_buyer_listing_payloads_mark_the_viewers_own_listing(
    client: Client,
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    # Audit A-35 / SECONDARY-10: the seller's own listing is shown without Buy.
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    listing = _list_holding_for_sale(investor, holding, price_bps=10_000, key="own-listing")

    client.force_login(cast(Any, investor))
    seller_list = client.get("/api/v1/marketplace/secondary/listings/").json()
    seller_detail = client.get(f"/api/v1/marketplace/secondary/listings/{listing.pk}/").json()
    client.force_login(cast(Any, other_investor))
    buyer_list = client.get("/api/v1/marketplace/secondary/listings/").json()
    buyer_detail = client.get(f"/api/v1/marketplace/secondary/listings/{listing.pk}/").json()

    assert seller_list[0]["is_own_listing"] is True
    assert seller_detail["is_own_listing"] is True
    assert buyer_list[0]["is_own_listing"] is False
    assert buyer_detail["is_own_listing"] is False
    assert "seller_user_id" not in buyer_list[0]


@pytest.mark.django_db
def test_listing_terms_accepted_for_another_price_are_rejected(
    admin_user: Model,
    investor: Model,
) -> None:
    # Audit A-36 / FRONTCODE-05: the acceptance evidence records the reviewed price.
    _approve_financial_access(investor)
    loan = _create_funded_loan(admin_user)
    holding = _create_holding(admin_user, investor, loan)
    acceptance = _create_listing_acceptance(
        investor,
        holding,
        idempotency_key="listing-accept-par",
        data_snapshot={"holding_id": str(cast(Any, holding).id), "price_bps": 10_000},
    )
    code = _sensitive_code_payload(investor, "secondary_market_listing")
    with pytest.raises(SecondaryMarketValidationError, match="accepted for a different price"):
        create_secondary_market_listing(
            CreateSecondaryMarketListingCommand(
                actor=investor,
                holding_id=str(cast(Any, holding).id),
                price_bps=9_500,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="listing-other-price",
                **code,
            )
        )
    # Refused before the email code is checked, so the same code still works.
    listing = create_secondary_market_listing(
        CreateSecondaryMarketListingCommand(
            actor=investor,
            holding_id=str(cast(Any, holding).id),
            price_bps=10_000,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="listing-reviewed-price",
            **code,
        )
    )
    assert listing.price_bps == 10_000
