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
from backend.apps.secondary_market.models import (
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
    SecondaryMarketValidationError,
    approve_secondary_market_listing,
    cancel_secondary_market_listing,
    create_secondary_market_listing,
    edit_secondary_market_listing,
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
            loan_start_date=date(2025, 12, 31),
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
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
def test_admin_secondary_listing_table_lists_and_filters(
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
    assert row["status"] == "approval_requested"
    assert row["loan_title"] == "Secondary bridge loan"
    assert row["loan_status"] == "late"
    assert row["seller_email"] == cast(Any, investor).email
    assert row["seller_full_name"]
    assert "created_at" in row

    filtered = client.get("/api/v1/marketplace/secondary/admin/listings/?status=active")
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
    purchase_acceptance = _create_purchase_acceptance(other_investor, listing)
    purchase_code = _sensitive_code_payload(other_investor, "secondary_market_purchase")

    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            idempotency_key="secondary-purchase-1",
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
    with pytest.raises(SecondaryMarketValidationError, match="Loan status changed"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(fresh_acceptance.pk),
                idempotency_key="secondary-purchase-stale-status",
                **other_purchase_code,
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
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
    purchase_code = _sensitive_code_payload(other_investor, "secondary_market_purchase")

    with pytest.raises(SecondaryMarketValidationError, match="acknowledge"):
        purchase_secondary_market_listing(
            PurchaseSecondaryMarketListingCommand(
                actor=other_investor,
                listing_id=str(listing.id),
                document_acceptance_id=str(purchase_acceptance.pk),
                idempotency_key="secondary-purchase-late-no-ack",
                **purchase_code,
            )
        )

    purchase = purchase_secondary_market_listing(
        PurchaseSecondaryMarketListingCommand(
            actor=other_investor,
            listing_id=str(listing.id),
            document_acceptance_id=str(purchase_acceptance.pk),
            risk_acknowledgement_accepted=True,
            idempotency_key="secondary-purchase-late-with-ack",
            **purchase_code,
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
            **_sensitive_code_payload(investor, "secondary_market_listing"),
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
