from __future__ import annotations

from datetime import date, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryInvestmentOrderBatch,
    PrimaryInvestmentOrderEvent,
    PrimaryInvestmentOrderStatus,
    PrimaryLoanCancellation,
    PrimaryLoanClose,
    PrimaryLoanCloseType,
)
from backend.apps.marketplace_primary.services import (
    AllocatePrimaryInvestmentOrderCommand,
    CancelPrimaryLoanFundingCommand,
    ClosePrimaryLoanFundingCommand,
    CreatePrimaryInvestmentOrderCommand,
    MarketplacePrimaryAuthorizationError,
    MarketplacePrimaryValidationError,
    PlacePrimaryOrderBatchCommand,
    PrimaryOrderBatchItemCommand,
    ReleasePrimaryInvestmentOrderCommand,
    ScanExpiredPrimaryFundingCommand,
    allocate_primary_order_from_balance,
    cancel_primary_loan_funding,
    close_primary_loan_funding,
    create_primary_investment_order,
    get_full_marketplace_loan,
    place_primary_order_batch,
    release_primary_order_balance,
    scan_expired_primary_loan_funding,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import AuditEvent, Currency, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.platform_core.services.impersonation import (
    READONLY_IMPERSONATION_HEADER,
    issue_readonly_impersonation_token,
)
from backend.apps.platform_core.tests.factories import (
    SensitiveActionCodePayload,
    issue_sensitive_action_test_code,
)


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="market-admin@example.test",
            password="AdminPass123!",
            full_name="Market Admin",
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
            email="market-investor@example.test",
            full_name="Market Investor",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


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
            legal_name="Marketplace Borrower AG",
            year_founded=2010,
            entity_type="swiss_company",
            kyb_status="approved",
            country="CH",
            created_by_admin_id=admin_user.pk,
        ),
    )


def _create_published_loan(
    admin_user: Model,
    *,
    principal_minor: int = 100_000_00,
    funding_deadline: date = date(2030, 1, 10),
    minimum_subscription_bps: int = 5_000,
    currency_code: str = "CHF",
) -> Model:
    borrower = _create_borrower(admin_user)
    loan_model = apps.get_model("loans", "Loan")
    currency = Currency.objects.get(code=currency_code)
    return cast(
        Model,
        loan_model.objects.create(
            borrower=borrower,
            minimum_subscription_bps=minimum_subscription_bps,
            status="published",
            title="Real estate bridge loan",
            investor_summary="Short real-estate backed bridge facility.",
            purpose="bridge_financing",
            original_principal_minor=principal_minor,
            principal_minor=principal_minor,
            currency=currency,
            interest_rate_bps=1000,
            term_months=12,
            repayment_type="equal_installments",
            loan_start_date=funding_deadline,
            funding_deadline=funding_deadline,
            first_payment_date=date(2030, 2, 10),
            collateral_type="real_estate",
            collateral_value_minor=150_000_00,
            risk_rating="BBB",
            borrower_success_fee_bps=200,
            total_scheduled_principal_minor=principal_minor,
            total_scheduled_interest_minor=5_000_00,
            created_by_admin_id=admin_user.pk,
            published_at=timezone.now(),
        ),
    )


def _declare_deposit(
    admin_user: Model,
    investor: Model,
    *,
    amount_minor: int = 50_000_00,
    value_date: date | None = None,
    idempotency_key: str = "market-deposit-1",
    currency: str = "CHF",
) -> Any:
    if value_date is None:
        # Relative to the real clock: allocation checks the lot's 30-day
        # investment window against now, so a fixed date goes stale.
        value_date = business_date(timezone.now())
    ledger = import_module("backend.apps.ledger.services")
    return ledger.declare_lender_deposit(
        ledger.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency=currency,
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier="CH00GARANTAMARKET",
            payer_name="Market Investor",
            payer_account_identifier="CH9300762011623852957",
            bank_reference=f"BANK-{idempotency_key}",
            payment_reference=f"INV-{investor.pk}",
            evidence_reference=f"statement:{idempotency_key}",
            idempotency_key=idempotency_key,
        )
    )


def _create_primary_acceptance(
    investor: Model,
    *,
    order_id: str,
    idempotency_key: str = "market-accept-1",
    category: str = "primary_market_investment",
    context_type: str = "primary_order",
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
        name="Primary terms",
        created_by_superadmin_id=investor.pk,
    )
    version = version_model.objects.create(
        template=template,
        version_number=1,
        status="published",
        title="Primary terms",
        body="Terms",
        checkbox_labels=["I accept the primary-market terms."],
        variable_schema={},
        content_hash="a" * 64,
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
            context_id=context_id or order_id,
            accepted_checkbox_labels=["I accept the primary-market terms."],
            data_snapshot=data_snapshot or {},
            idempotency_key=idempotency_key,
        ),
    )


def _republish_acceptance_template(acceptance: Model) -> None:
    version_model = apps.get_model("documents", "DocumentTemplateVersion")
    acceptance_ref = cast(Any, acceptance)
    template = acceptance_ref.template
    new_version = version_model.objects.create(
        template=template,
        version_number=2,
        status="published",
        title="Primary terms v2",
        body="Updated terms",
        checkbox_labels=["I accept the updated primary-market terms."],
        variable_schema={},
        content_hash="b" * 64,
        created_by_superadmin_id=acceptance_ref.user_id,
        published_at=timezone.now(),
    )
    template.current_published_version = new_version
    template.save(update_fields=["current_published_version"])


def _create_and_allocate_order(
    *,
    investor: Model,
    loan: Model,
    amount_minor: int,
    idempotency_prefix: str,
) -> PrimaryInvestmentOrder:
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=amount_minor,
            idempotency_key=f"{idempotency_prefix}-order",
        )
    )
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key=f"{idempotency_prefix}-accept",
    )
    return allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=f"{idempotency_prefix}-allocate",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )


@pytest.mark.django_db
def test_full_marketplace_loan_includes_selected_borrower_disclosure(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    borrower = cast(Any, loan).borrower
    borrower.business_classification = "Real-estate project finance"
    borrower.business_classification_public = True
    borrower.registered_address = "Zugerstrasse 18, 6300 Zug"
    borrower.registered_address_public = True
    borrower.contact_info = "borrower-relations@example.test"
    borrower.contact_info_public = False
    borrower.ownership_structure = "Internal ownership notes."
    borrower.bank_account_details = {"notes": "Internal borrower account notes."}
    borrower.kyb_aml_observations = "Internal KYB observations."
    borrower.financial_risk = "Internal financial risk notes."
    borrower.save()

    payload = get_full_marketplace_loan(actor=investor, loan_id=str(cast(Any, loan).id))
    disclosure = payload["borrower_disclosure"]

    assert disclosure["legal_name"] == "Marketplace Borrower AG"
    assert disclosure["business_classification"] == "Real-estate project finance"
    assert disclosure["registered_address"] == "Zugerstrasse 18, 6300 Zug"
    assert "contact_info" not in disclosure
    assert "ownership_structure" not in disclosure
    assert "bank_account_details" not in disclosure
    assert "kyb_aml_observations" not in disclosure
    assert "financial_risk" not in disclosure


@pytest.mark.django_db
def test_primary_order_requires_financial_access(admin_user: Model, investor: Model) -> None:
    loan = _create_published_loan(admin_user)

    with pytest.raises(MarketplacePrimaryAuthorizationError):
        create_primary_investment_order(
            CreatePrimaryInvestmentOrderCommand(
                actor=investor,
                loan_id=str(loan.pk),
                amount_minor=10_000_00,
                idempotency_key="market-order-no-kyc",
            )
        )


@pytest.mark.django_db
def test_primary_order_create_enforces_minimum_and_capacity(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)

    with pytest.raises(MarketplacePrimaryValidationError, match="below the launch minimum"):
        create_primary_investment_order(
            CreatePrimaryInvestmentOrderCommand(
                actor=investor,
                loan_id=str(loan.pk),
                amount_minor=999_00,
                idempotency_key="market-order-below-min",
            )
        )

    with pytest.raises(MarketplacePrimaryValidationError, match="remaining loan capacity"):
        create_primary_investment_order(
            CreatePrimaryInvestmentOrderCommand(
                actor=investor,
                loan_id=str(loan.pk),
                amount_minor=11_000_00,
                idempotency_key="market-order-over-capacity",
            )
        )


@pytest.mark.django_db
def test_balance_allocation_reserves_lots_and_updates_loan_commitment(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    deposit = _declare_deposit(admin_user, investor)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=25_000_00,
            idempotency_key="market-order-1",
        )
    )
    acceptance = _create_primary_acceptance(investor, order_id=str(order.id))

    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-1",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )
    deposit.balance_lot.refresh_from_db()
    loan.refresh_from_db()

    assert allocated.status == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
    assert allocated.allocated_amount_minor == 25_000_00
    assert allocated.reservation_journal_entry_id is not None
    assert allocated.lot_allocations[0]["lot_id"] == str(deposit.balance_lot.id)
    assert deposit.balance_lot.available_amount_minor == 25_000_00
    assert deposit.balance_lot.invested_amount_minor == 25_000_00
    assert cast(Any, loan).committed_principal_minor == 25_000_00
    assert AuditEvent.objects.filter(action="marketplace_primary.order_balance_allocated").exists()
    assert DomainEvent.objects.filter(event_type="PrimaryInvestmentOrderBalanceAllocated").exists()


@pytest.mark.django_db
def test_balance_allocation_requires_sensitive_action_code(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    _declare_deposit(admin_user, investor)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=25_000_00,
            idempotency_key="market-order-missing-sensitive-code",
        )
    )
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-missing-sensitive-code",
    )

    with pytest.raises(MarketplacePrimaryValidationError, match="Sensitive-action email code"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="market-allocate-missing-sensitive-code",
            )
        )

    order.refresh_from_db()
    loan.refresh_from_db()
    assert order.status == PrimaryInvestmentOrderStatus.PENDING
    assert cast(Any, loan).committed_principal_minor == 0


@pytest.mark.django_db
def test_balance_allocation_is_idempotent_and_rejects_conflicting_replay(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    _declare_deposit(admin_user, investor)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=20_000_00,
            idempotency_key="market-order-idempotent-allocate",
        )
    )
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-idempotent-allocate",
    )
    allocation_code = _sensitive_code_payload(investor, "primary_investment")

    first = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-idempotent",
            **allocation_code,
        )
    )
    second = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-idempotent",
            **allocation_code,
        )
    )

    assert second.id == first.id
    assert second.reservation_journal_entry_id == first.reservation_journal_entry_id
    with pytest.raises(MarketplacePrimaryValidationError, match="already allocated"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="market-allocate-conflict",
                **allocation_code,
            )
        )


@pytest.mark.django_db
def test_balance_allocation_allows_pledge_before_lot_investment_deadline(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    today = business_date(timezone.now())
    # Lot investment deadline (value date + 30d) falls BEFORE the loan funding
    # deadline; the pledge must still be accepted while the lot window is open.
    loan = _create_published_loan(admin_user, funding_deadline=today + timedelta(days=14))
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=25_000_00,
        value_date=today - timedelta(days=25),
        idempotency_key="market-deposit-expiring",
    )
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=25_000_00,
            idempotency_key="market-order-expiring",
        )
    )
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-expiring",
    )

    result = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-before-lot-deadline",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )

    assert result.status == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
    assert result.allocated_amount_minor == 25_000_00
    assert result.lot_allocations[0]["amount_minor"] == 25_000_00


@pytest.mark.django_db
def test_allocation_accepts_subminimum_final_capacity_fill(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_500_00)
    _declare_deposit(admin_user, investor, amount_minor=2_000_00)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=1_000_00,
            idempotency_key="market-order-final-fill",
        )
    )
    cast(Any, loan).committed_principal_minor = 10_000_00
    loan.save(update_fields=["committed_principal_minor"])
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-final-fill",
    )

    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-final-fill",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )

    assert allocated.status == PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED
    assert allocated.allocated_amount_minor == 500_00


@pytest.mark.django_db
def test_allocation_uses_remaining_capacity_and_leaves_excess_balance_available(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    deposit = _declare_deposit(admin_user, investor, amount_minor=30_000_00)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=20_000_00,
            idempotency_key="market-order-partial",
        )
    )
    cast(Any, loan).committed_principal_minor = 20_000_00
    loan.save(update_fields=["committed_principal_minor"])
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-partial",
    )

    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-partial",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )
    deposit.balance_lot.refresh_from_db()
    loan.refresh_from_db()

    assert allocated.status == PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED
    assert allocated.allocated_amount_minor == 10_000_00
    assert deposit.balance_lot.available_amount_minor == 20_000_00
    assert cast(Any, loan).committed_principal_minor == 30_000_00


@pytest.mark.django_db
def test_allocation_requires_bound_current_acceptance_and_owner(
    admin_user: Model,
    investor: Model,
) -> None:
    user_model: Any = get_user_model()
    other_investor = cast(
        Model,
        user_model.objects.create_user(
            email="other-market-investor@example.test",
            full_name="Other Market Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_published_loan(admin_user)
    _declare_deposit(admin_user, investor, amount_minor=20_000_00)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=10_000_00,
            idempotency_key="market-order-acceptance-negative",
        )
    )
    allocation_code = _sensitive_code_payload(investor, "primary_investment")

    wrong_category = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-wrong-category",
        category="registration",
    )
    with pytest.raises(MarketplacePrimaryValidationError, match="category"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                document_acceptance_id=str(wrong_category.pk),
                idempotency_key="market-allocate-wrong-category",
                **allocation_code,
            )
        )

    wrong_context = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-wrong-context",
        context_id="other-order",
    )
    with pytest.raises(MarketplacePrimaryValidationError, match="does not match"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                document_acceptance_id=str(wrong_context.pk),
                idempotency_key="market-allocate-wrong-context",
                **allocation_code,
            )
        )

    other_acceptance = _create_primary_acceptance(
        other_investor,
        order_id=str(order.id),
        idempotency_key="market-accept-other-user",
    )
    with pytest.raises(MarketplacePrimaryValidationError, match="does not exist"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                document_acceptance_id=str(other_acceptance.pk),
                idempotency_key="market-allocate-other-user-acceptance",
                **allocation_code,
            )
        )

    stale_acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-stale",
    )
    _republish_acceptance_template(stale_acceptance)
    with pytest.raises(MarketplacePrimaryValidationError, match="no longer current"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                document_acceptance_id=str(stale_acceptance.pk),
                idempotency_key="market-allocate-stale-acceptance",
                **allocation_code,
            )
        )


@pytest.mark.django_db
def test_allocation_blocks_other_investor_order_access(
    admin_user: Model,
    investor: Model,
) -> None:
    user_model: Any = get_user_model()
    other_investor = cast(
        Model,
        user_model.objects.create_user(
            email="allocating-other-investor@example.test",
            full_name="Allocating Other Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_published_loan(admin_user)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=10_000_00,
            idempotency_key="market-order-idor",
        )
    )
    other_acceptance = _create_primary_acceptance(
        other_investor,
        order_id=str(order.id),
        idempotency_key="market-accept-idor",
    )

    with pytest.raises(MarketplacePrimaryValidationError, match="does not exist"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=other_investor,
                order_id=str(order.id),
                document_acceptance_id=str(other_acceptance.pk),
                idempotency_key="market-allocate-idor",
                **_sensitive_code_payload(other_investor, "primary_investment"),
            )
        )


@pytest.mark.django_db
def test_allocation_closes_not_invested_when_no_capacity_remains(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=1_000_00,
            idempotency_key="market-order-no-capacity-at-allocation",
        )
    )
    cast(Any, loan).committed_principal_minor = 10_000_00
    loan.save(update_fields=["committed_principal_minor"])
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-no-capacity",
    )

    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-no-capacity",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )

    assert allocated.status == PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
    assert allocated.allocated_amount_minor == 0


@pytest.mark.django_db
def test_admin_release_restores_lots_and_loan_commitment(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    deposit = _declare_deposit(admin_user, investor, amount_minor=40_000_00)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=20_000_00,
            idempotency_key="market-order-release",
        )
    )
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-release",
    )
    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-release",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )

    released = release_primary_order_balance(
        ReleasePrimaryInvestmentOrderCommand(
            actor=admin_user,
            order_id=str(allocated.id),
            reason="Campaign cancelled by operations.",
            idempotency_key="market-release-1",
        )
    )
    deposit.balance_lot.refresh_from_db()
    loan.refresh_from_db()

    assert released.status == PrimaryInvestmentOrderStatus.BALANCE_RELEASED
    assert released.release_journal_entry_id is not None
    assert deposit.balance_lot.available_amount_minor == 40_000_00
    assert deposit.balance_lot.invested_amount_minor == 0
    assert cast(Any, loan).committed_principal_minor == 0
    assert AuditEvent.objects.filter(action="marketplace_primary.order_balance_released").exists()


@pytest.mark.django_db
def test_admin_release_is_idempotent_and_rejects_double_release(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    _declare_deposit(admin_user, investor, amount_minor=40_000_00)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=20_000_00,
            idempotency_key="market-order-double-release",
        )
    )
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-double-release",
    )
    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-double-release",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )

    first = release_primary_order_balance(
        ReleasePrimaryInvestmentOrderCommand(
            actor=admin_user,
            order_id=str(allocated.id),
            reason="Campaign cancelled.",
            idempotency_key="market-release-double",
        )
    )
    second = release_primary_order_balance(
        ReleasePrimaryInvestmentOrderCommand(
            actor=admin_user,
            order_id=str(allocated.id),
            reason="Campaign cancelled.",
            idempotency_key="market-release-double",
        )
    )

    assert second.id == first.id
    assert second.release_journal_entry_id == first.release_journal_entry_id
    with pytest.raises(MarketplacePrimaryValidationError, match="already released"):
        release_primary_order_balance(
            ReleasePrimaryInvestmentOrderCommand(
                actor=admin_user,
                order_id=str(allocated.id),
                reason="Campaign cancelled.",
                idempotency_key="market-release-conflict",
            )
        )


@pytest.mark.django_db
def test_release_fails_loud_on_committed_principal_underflow(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    _declare_deposit(admin_user, investor, amount_minor=40_000_00)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=20_000_00,
            idempotency_key="market-order-underflow",
        )
    )
    acceptance = _create_primary_acceptance(
        investor,
        order_id=str(order.id),
        idempotency_key="market-accept-underflow",
    )
    allocated = allocate_primary_order_from_balance(
        AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="market-allocate-underflow",
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )
    cast(Any, loan).committed_principal_minor = 1_00
    loan.save(update_fields=["committed_principal_minor"])

    with pytest.raises(MarketplacePrimaryValidationError, match="underflow"):
        release_primary_order_balance(
            ReleasePrimaryInvestmentOrderCommand(
                actor=admin_user,
                order_id=str(allocated.id),
                reason="Underflow test.",
                idempotency_key="market-release-underflow",
            )
        )


@pytest.mark.django_db
def test_admin_release_of_pending_order_closes_not_invested(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=10_000_00,
            idempotency_key="market-order-release-pending",
        )
    )

    released = release_primary_order_balance(
        ReleasePrimaryInvestmentOrderCommand(
            actor=admin_user,
            order_id=str(order.id),
            reason="Campaign closed before funding.",
            idempotency_key="market-release-pending",
        )
    )

    assert released.status == PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
    assert released.allocated_amount_minor == 0


@pytest.mark.django_db
def test_release_requires_admin(admin_user: Model, investor: Model) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=10_000_00,
            idempotency_key="market-order-release-non-admin",
        )
    )

    with pytest.raises(MarketplacePrimaryAuthorizationError):
        release_primary_order_balance(
            ReleasePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                reason="Investor cannot release.",
                idempotency_key="market-release-non-admin",
            )
        )


@pytest.mark.django_db
def test_close_full_funding_creates_holdings_and_moves_escrow(
    admin_user: Model,
    investor: Model,
) -> None:
    user_model: Any = get_user_model()
    other_investor = cast(
        Model,
        user_model.objects.create_user(
            email="market-close-other@example.test",
            full_name="Market Close Other",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=20_000_00,
        idempotency_key="market-close-deposit-1",
    )
    _declare_deposit(
        admin_user,
        other_investor,
        amount_minor=10_000_00,
        idempotency_key="market-close-deposit-2",
    )
    pending_order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=1_000_00,
            idempotency_key="market-close-pending-order",
        )
    )
    first_order = _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=20_000_00,
        idempotency_prefix="market-close-first",
    )
    second_order = _create_and_allocate_order(
        investor=other_investor,
        loan=loan,
        amount_minor=10_000_00,
        idempotency_prefix="market-close-second",
    )

    close = close_primary_loan_funding(
        ClosePrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Funding target reached.",
            investor_message="Funding target reached.",
            idempotency_key="market-close-full",
            as_of_date=date(2030, 1, 11),
        )
    )
    loan.refresh_from_db()
    first_order.refresh_from_db()
    second_order.refresh_from_db()
    pending_order.refresh_from_db()
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holdings = list(holding_model.objects.filter(loan_id=loan.pk).order_by("source_id"))
    posting_model = apps.get_model("ledger", "LedgerPosting")
    postings = list(
        posting_model.objects.filter(journal_entry=close.funding_close_journal_entry).order_by(
            "side",
            "amount_minor",
        )
    )

    assert close.close_type == PrimaryLoanCloseType.FULL
    assert close.accepted_principal_minor == 30_000_00
    # The fee recorded at close is the planned default; it is booked as revenue
    # at borrower disbursement, so the payable carries the full funded amount.
    assert close.borrower_success_fee_minor == 600_00
    assert close.borrower_disbursement_payable_minor == 30_000_00
    assert close.allocated_order_count == 2
    assert close.closed_not_invested_order_count == 1
    assert cast(Any, loan).status == "funded"
    assert cast(Any, loan).principal_minor == 30_000_00
    assert first_order.status == PrimaryInvestmentOrderStatus.CLOSED_INVESTED
    assert second_order.status == PrimaryInvestmentOrderStatus.CLOSED_INVESTED
    assert pending_order.status == PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
    assert len(holdings) == 2
    assert {holding.original_principal_minor for holding in holdings} == {20_000_00, 10_000_00}
    assert {holding.current_principal_minor for holding in holdings} == {20_000_00, 10_000_00}
    assert sum(holding.loan_share_ppm for holding in holdings) == 1_000_000
    assert close.funding_close_journal_entry.event_type == "primary_loan_funding_closed"
    assert sum(posting.amount_minor for posting in postings if posting.side == "debit") == 30_000_00
    assert (
        sum(posting.amount_minor for posting in postings if posting.side == "credit") == 30_000_00
    )
    assert AuditEvent.objects.filter(action="marketplace_primary.loan_funding_closed").exists()
    assert DomainEvent.objects.filter(event_type="PrimaryLoanFundingClosed").exists()

    with pytest.raises(MarketplacePrimaryValidationError, match="Closed loan"):
        release_primary_order_balance(
            ReleasePrimaryInvestmentOrderCommand(
                actor=admin_user,
                order_id=str(first_order.id),
                reason="Should not release after close.",
                idempotency_key="market-close-release-after-close",
            )
        )


@pytest.mark.django_db
def test_close_reconciles_holding_share_ppm_with_largest_remainder(
    admin_user: Model,
    investor: Model,
) -> None:
    user_model: Any = get_user_model()
    second_investor = cast(
        Model,
        user_model.objects.create_user(
            email="market-share-second@example.test",
            full_name="Market Share Second",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    third_investor = cast(
        Model,
        user_model.objects.create_user(
            email="market-share-third@example.test",
            full_name="Market Share Third",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    for user in (investor, second_investor, third_investor):
        _approve_financial_access(user)
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    for index, user in enumerate((investor, second_investor, third_investor), start=1):
        _declare_deposit(
            admin_user,
            user,
            amount_minor=10_000_00,
            idempotency_key=f"market-share-deposit-{index}",
        )
        _create_and_allocate_order(
            investor=user,
            loan=loan,
            amount_minor=10_000_00,
            idempotency_prefix=f"market-share-{index}",
        )

    close = close_primary_loan_funding(
        ClosePrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Funding target reached.",
            investor_message="Funding target reached.",
            idempotency_key="market-share-close",
            as_of_date=date(2030, 1, 11),
        )
    )
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holdings = list(holding_model.objects.filter(loan_id=loan.pk))

    assert close.metadata["holding_share_ppm_total"] == 1_000_000
    assert sum(holding.loan_share_ppm for holding in holdings) == 1_000_000
    assert sorted(holding.loan_share_ppm for holding in holdings) == [333_333, 333_333, 333_334]


@pytest.mark.django_db
def test_close_partial_funding_regenerates_schedule_and_requires_message(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(
        admin_user,
        principal_minor=100_000_00,
        minimum_subscription_bps=4_000,
    )
    _declare_deposit(admin_user, investor, amount_minor=40_000_00, idempotency_key="partial-dep")
    _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=40_000_00,
        idempotency_prefix="market-close-partial",
    )

    with pytest.raises(MarketplacePrimaryValidationError, match="Investor message"):
        close_primary_loan_funding(
            ClosePrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="Partial close approved.",
                investor_message="",
                idempotency_key="market-close-partial-missing-message",
                as_of_date=date(2030, 1, 11),
            )
        )

    close = close_primary_loan_funding(
        ClosePrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Partial close approved.",
            investor_message="The loan is closing at the accepted funded amount.",
            idempotency_key="market-close-partial-ok",
            as_of_date=date(2030, 1, 11),
        )
    )
    loan.refresh_from_db()
    installment_model = apps.get_model("loans", "LoanInstallment")
    principal_sum = sum(
        installment.principal_minor
        for installment in installment_model.objects.filter(
            loan_id=loan.pk,
            schedule_version=cast(Any, loan).schedule_version,
        )
    )

    assert close.close_type == PrimaryLoanCloseType.PARTIAL
    assert close.accepted_principal_minor == 40_000_00
    assert cast(Any, loan).status == "funded"
    assert cast(Any, loan).principal_minor == 40_000_00
    assert cast(Any, loan).schedule_version == 2
    assert principal_sum == 40_000_00


@pytest.mark.django_db
def test_close_rejects_allocated_order_and_committed_principal_drift(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    _declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="drift-dep")
    _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=10_000_00,
        idempotency_prefix="market-close-drift",
    )
    cast(Any, loan).committed_principal_minor = 9_000_00
    loan.save(update_fields=["committed_principal_minor"])

    with pytest.raises(MarketplacePrimaryValidationError, match="committed principal"):
        close_primary_loan_funding(
            ClosePrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="Drift should block close.",
                investor_message="Drift should block close.",
                idempotency_key="market-close-drift",
                as_of_date=date(2030, 1, 11),
            )
        )


@pytest.mark.django_db
def test_close_is_idempotent_and_rejects_conflicting_replay(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    _declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="idem-dep")
    _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=10_000_00,
        idempotency_prefix="market-close-idem",
    )

    first = close_primary_loan_funding(
        ClosePrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Funding target reached.",
            investor_message="Funding target reached.",
            idempotency_key="market-close-idem",
            as_of_date=date(2030, 1, 11),
        )
    )
    second = close_primary_loan_funding(
        ClosePrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Funding target reached.",
            investor_message="Funding target reached.",
            idempotency_key="market-close-idem",
            as_of_date=date(2030, 1, 11),
        )
    )

    assert second.id == first.id
    with pytest.raises(MarketplacePrimaryValidationError, match="different close request"):
        close_primary_loan_funding(
            ClosePrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="Different reason.",
                investor_message="Funding target reached.",
                idempotency_key="market-close-idem",
                as_of_date=date(2030, 1, 11),
            )
        )


@pytest.mark.django_db
def test_close_requires_admin_allocated_orders_and_borrower_clearance(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(
        admin_user,
        principal_minor=10_000_00,
        minimum_subscription_bps=0,
    )

    with pytest.raises(MarketplacePrimaryAuthorizationError):
        close_primary_loan_funding(
            ClosePrimaryLoanFundingCommand(
                actor=investor,
                loan_id=str(loan.pk),
                reason="Investor cannot close.",
                investor_message="",
                idempotency_key="market-close-non-admin",
                as_of_date=date(2030, 1, 11),
            )
        )
    with pytest.raises(MarketplacePrimaryValidationError, match="no allocated"):
        close_primary_loan_funding(
            ClosePrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="No allocations.",
                investor_message="",
                idempotency_key="market-close-no-allocations",
                as_of_date=date(2030, 1, 11),
            )
        )

    cast(Any, loan).borrower.compliance_hold = True
    cast(Any, loan).borrower.save(update_fields=["compliance_hold"])
    _declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="clearance-dep")
    _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=10_000_00,
        idempotency_prefix="market-close-clearance",
    )

    with pytest.raises(MarketplacePrimaryValidationError, match="compliance hold"):
        close_primary_loan_funding(
            ClosePrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="Borrower blocked.",
                investor_message="Borrower blocked.",
                idempotency_key="market-close-borrower-blocked",
                as_of_date=date(2030, 1, 11),
            )
        )


@pytest.mark.django_db
def test_cancel_funding_releases_allocations_closes_pending_and_cancels_loan(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    deposit = _declare_deposit(
        admin_user,
        investor,
        amount_minor=25_000_00,
        idempotency_key="cancel-deposit",
    )
    pending_order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=1_000_00,
            idempotency_key="cancel-pending-order",
        )
    )
    allocated_order = _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=20_000_00,
        idempotency_prefix="market-cancel-allocated",
    )

    cancellation = cancel_primary_loan_funding(
        CancelPrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Campaign expired below target.",
            investor_message=(
                "The campaign expired below target and your reserved balance was released."
            ),
            idempotency_key="market-cancel-funding",
        )
    )
    loan.refresh_from_db()
    allocated_order.refresh_from_db()
    pending_order.refresh_from_db()
    deposit.balance_lot.refresh_from_db()

    assert cast(Any, loan).status == "cancelled"
    assert cast(Any, loan).committed_principal_minor == 0
    assert cancellation.released_order_count == 1
    assert cancellation.closed_not_invested_order_count == 1
    assert cancellation.released_principal_minor == 20_000_00
    assert cancellation.investor_message
    assert allocated_order.status == PrimaryInvestmentOrderStatus.BALANCE_RELEASED
    assert allocated_order.release_journal_entry_id is not None
    assert pending_order.status == PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
    assert deposit.balance_lot.available_amount_minor == 25_000_00
    assert deposit.balance_lot.invested_amount_minor == 0
    assert AuditEvent.objects.filter(action="marketplace_primary.loan_funding_cancelled").exists()
    assert AuditEvent.objects.filter(action="loan.funding_cancelled").exists()
    assert DomainEvent.objects.filter(event_type="PrimaryLoanFundingCancelled").exists()
    assert DomainEvent.objects.filter(event_type="LoanFundingCancelled").exists()

    with pytest.raises(MarketplacePrimaryValidationError, match="expired published"):
        close_primary_loan_funding(
            ClosePrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="Cannot close a cancelled campaign.",
                investor_message="Cannot close.",
                idempotency_key="market-cancel-then-close",
                as_of_date=date(2030, 1, 11),
            )
        )


@pytest.mark.django_db
def test_cancel_funding_requires_investor_message_when_orders_exist(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)
    create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=1_000_00,
            idempotency_key="cancel-message-pending-order",
        )
    )

    with pytest.raises(MarketplacePrimaryValidationError, match="Investor message"):
        cancel_primary_loan_funding(
            CancelPrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="Campaign expired below target.",
                idempotency_key="market-cancel-missing-message",
            )
        )


@pytest.mark.django_db
def test_cancel_funding_is_idempotent_and_rejects_conflicting_replay(
    admin_user: Model,
) -> None:
    loan = _create_published_loan(admin_user, principal_minor=30_000_00)

    first = cancel_primary_loan_funding(
        CancelPrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Campaign expired without orders.",
            idempotency_key="market-cancel-idem",
        )
    )
    second = cancel_primary_loan_funding(
        CancelPrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Campaign expired without orders.",
            idempotency_key="market-cancel-idem",
        )
    )

    assert second.id == first.id
    assert PrimaryLoanCancellation.objects.count() == 1
    with pytest.raises(MarketplacePrimaryValidationError, match="different cancellation request"):
        cancel_primary_loan_funding(
            CancelPrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="Different cancellation reason.",
                idempotency_key="market-cancel-idem",
            )
        )


@pytest.mark.django_db
def test_cancel_funding_rejects_closed_or_non_admin(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)

    with pytest.raises(MarketplacePrimaryAuthorizationError):
        cancel_primary_loan_funding(
            CancelPrimaryLoanFundingCommand(
                actor=investor,
                loan_id=str(loan.pk),
                reason="Investor cannot cancel.",
                idempotency_key="market-cancel-non-admin",
            )
        )

    _declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="close-cancel")
    _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=10_000_00,
        idempotency_prefix="market-close-before-cancel",
    )
    close_primary_loan_funding(
        ClosePrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Funding target reached.",
            investor_message="Funding target reached.",
            idempotency_key="market-close-before-cancel",
            as_of_date=date(2030, 1, 11),
        )
    )

    with pytest.raises(MarketplacePrimaryValidationError, match="Closed loan funding"):
        cancel_primary_loan_funding(
            CancelPrimaryLoanFundingCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                reason="Cannot cancel after close.",
                idempotency_key="market-cancel-after-close",
            )
        )


@pytest.mark.django_db
def test_expiry_scan_closes_at_minimum_and_cancels_below(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    expired_at_minimum = _create_published_loan(
        admin_user,
        principal_minor=10_000_00,
        funding_deadline=date(2030, 1, 10),
    )
    expired_below_minimum = _create_published_loan(
        admin_user,
        principal_minor=10_000_00,
        funding_deadline=date(2030, 1, 10),
    )
    expired_pending = _create_published_loan(
        admin_user,
        principal_minor=10_000_00,
        funding_deadline=date(2030, 1, 10),
    )
    deadline_today = _create_published_loan(
        admin_user,
        principal_minor=10_000_00,
        funding_deadline=date(2030, 1, 11),
    )
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=10_000_00,
        value_date=date(2029, 12, 15),
        idempotency_key="expiry-scan-deposit",
    )
    # Exactly the 50% default minimum: the loan is made at the subscribed amount.
    at_minimum_order = _create_and_allocate_order(
        investor=investor,
        loan=expired_at_minimum,
        amount_minor=5_000_00,
        idempotency_prefix="expiry-scan-allocated",
    )
    # 20% subscribed is below the minimum: cancelled and refunded.
    below_minimum_order = _create_and_allocate_order(
        investor=investor,
        loan=expired_below_minimum,
        amount_minor=2_000_00,
        idempotency_prefix="expiry-scan-below",
    )
    pending_order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(expired_pending.pk),
            amount_minor=1_000_00,
            idempotency_key="expiry-scan-pending",
        )
    )

    result = scan_expired_primary_loan_funding(
        ScanExpiredPrimaryFundingCommand(
            actor=admin_user,
            as_of_date=date(2030, 1, 11),
        )
    )
    expired_at_minimum.refresh_from_db()
    expired_below_minimum.refresh_from_db()
    expired_pending.refresh_from_db()
    deadline_today.refresh_from_db()
    at_minimum_order.refresh_from_db()
    below_minimum_order.refresh_from_db()
    pending_order.refresh_from_db()

    assert result["scanned_count"] == 3
    assert result["closed_count"] == 1
    assert result["cancelled_count"] == 2
    assert result["skipped_count"] == 0
    assert cast(Any, expired_at_minimum).status == "funded"
    assert cast(Any, expired_at_minimum).principal_minor == 5_000_00
    assert cast(Any, expired_below_minimum).status == "cancelled"
    assert cast(Any, expired_pending).status == "cancelled"
    assert cast(Any, deadline_today).status == "published"
    assert at_minimum_order.status == PrimaryInvestmentOrderStatus.CLOSED_INVESTED
    assert below_minimum_order.status == PrimaryInvestmentOrderStatus.BALANCE_RELEASED
    assert pending_order.status == PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
    assert PrimaryLoanCancellation.objects.count() == 2

    rerun = scan_expired_primary_loan_funding(
        ScanExpiredPrimaryFundingCommand(
            actor=admin_user,
            as_of_date=date(2030, 1, 11),
        )
    )
    assert rerun["scanned_count"] == 0
    assert PrimaryLoanCancellation.objects.count() == 2


@pytest.mark.django_db
def test_expiry_resolution_uses_exact_minor_unit_threshold_and_allows_kyb_expiry(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    below_threshold = _create_published_loan(
        admin_user,
        principal_minor=10_000_01,
        funding_deadline=date(2030, 1, 10),
    )
    exact_threshold = _create_published_loan(
        admin_user,
        principal_minor=10_000_01,
        funding_deadline=date(2030, 1, 10),
    )
    cast(Any, exact_threshold).borrower.kyb_status = "expired"
    cast(Any, exact_threshold).borrower.save(update_fields=["kyb_status"])
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=10_000_01,
        value_date=date(2029, 12, 15),
        idempotency_key="exact-threshold-deposit",
    )
    below_order = _create_and_allocate_order(
        investor=investor,
        loan=below_threshold,
        amount_minor=5_000_00,
        idempotency_prefix="exact-threshold-below",
    )
    exact_order = _create_and_allocate_order(
        investor=investor,
        loan=exact_threshold,
        amount_minor=5_000_01,
        idempotency_prefix="exact-threshold-met",
    )

    result = scan_expired_primary_loan_funding(
        ScanExpiredPrimaryFundingCommand(
            actor=admin_user,
            as_of_date=date(2030, 1, 11),
            loan_ids=(str(below_threshold.pk), str(exact_threshold.pk)),
        )
    )

    below_threshold.refresh_from_db()
    exact_threshold.refresh_from_db()
    below_order.refresh_from_db()
    exact_order.refresh_from_db()
    assert result["cancelled_count"] == 1
    assert result["closed_count"] == 1
    assert cast(Any, below_threshold).status == "cancelled"
    assert cast(Any, exact_threshold).status == "funded"
    assert below_order.status == PrimaryInvestmentOrderStatus.BALANCE_RELEASED
    assert exact_order.status == PrimaryInvestmentOrderStatus.CLOSED_INVESTED


@pytest.mark.django_db
def test_expiry_close_failure_unpublishes_preserves_reservations_and_escalates(
    admin_user: Model,
    investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(
        admin_user,
        principal_minor=10_000_00,
        funding_deadline=date(2030, 1, 10),
    )
    deposit = _declare_deposit(
        admin_user,
        investor,
        amount_minor=5_000_00,
        value_date=date(2029, 12, 15),
        idempotency_key="failed-close-deposit",
    )
    order = _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=5_000_00,
        idempotency_prefix="failed-close-order",
    )
    marketplace_services = import_module("backend.apps.marketplace_primary.services")

    def fail_holding_plan(**_kwargs: Any) -> dict[str, int]:
        raise RuntimeError("simulated holding conversion failure")

    with monkeypatch.context() as patch:
        patch.setattr(marketplace_services, "_holding_share_ppm_by_order", fail_holding_plan)
        failed = scan_expired_primary_loan_funding(
            ScanExpiredPrimaryFundingCommand(
                actor=admin_user,
                as_of_date=date(2030, 1, 11),
                loan_ids=(str(loan.pk),),
            )
        )

    loan.refresh_from_db()
    order.refresh_from_db()
    deposit.balance_lot.refresh_from_db()
    admin_task_model = apps.get_model("admin_ops", "AdminTask")
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    task = admin_task_model.objects.get(
        related_object_type="LoanFundingCloseFailure",
        related_object_id=str(loan.pk),
    )
    alert = outbox_model.objects.get(topic="email.loan_funding_close_failed")

    assert failed["failed_count"] == 1
    assert cast(Any, loan).status == "funding_close_failed"
    assert cast(Any, loan).committed_principal_minor == 5_000_00
    assert order.status == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
    assert deposit.balance_lot.available_amount_minor == 0
    assert deposit.balance_lot.invested_amount_minor == 5_000_00
    assert not PrimaryLoanClose.objects.filter(loan_id=loan.pk).exists()
    assert task.status == "open"
    assert alert.payload["email"] == "hq@banxum.com"
    assert all(
        row["loan_id"] != str(loan.pk)
        for row in marketplace_services.list_public_marketplace_loans()
    )

    admin_ops_services = import_module("backend.apps.admin_ops.services")

    def fail_task_resolution(**_kwargs: Any) -> None:
        raise RuntimeError("simulated task resolution failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            admin_ops_services,
            "resolve_loan_funding_close_failure_task",
            fail_task_resolution,
        )
        failed_retry = scan_expired_primary_loan_funding(
            ScanExpiredPrimaryFundingCommand(
                actor=admin_user,
                as_of_date=date(2030, 1, 11),
                loan_ids=(str(loan.pk),),
            )
        )

    loan.refresh_from_db()
    order.refresh_from_db()
    assert failed_retry["failed_count"] == 1
    assert cast(Any, loan).status == "funding_close_failed"
    assert order.status == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
    assert not PrimaryLoanClose.objects.filter(loan_id=loan.pk).exists()

    retried = scan_expired_primary_loan_funding(
        ScanExpiredPrimaryFundingCommand(
            actor=admin_user,
            as_of_date=date(2030, 1, 11),
            loan_ids=(str(loan.pk),),
        )
    )
    loan.refresh_from_db()
    order.refresh_from_db()
    task.refresh_from_db()
    assert retried["closed_count"] == 1
    assert cast(Any, loan).status == "funded"
    assert order.status == PrimaryInvestmentOrderStatus.CLOSED_INVESTED
    assert task.status == "resolved"


@pytest.mark.django_db
def test_expiry_scan_rejects_non_admin(admin_user: Model, investor: Model) -> None:
    _approve_financial_access(investor)
    _create_published_loan(
        admin_user,
        funding_deadline=date(2030, 1, 10),
    )

    with pytest.raises(MarketplacePrimaryAuthorizationError):
        scan_expired_primary_loan_funding(
            ScanExpiredPrimaryFundingCommand(
                actor=investor,
                as_of_date=date(2030, 1, 11),
            )
        )


@pytest.mark.django_db
def test_primary_close_and_holding_events_have_append_only_guards(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    _declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="guard-dep")
    _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=10_000_00,
        idempotency_prefix="market-close-guard",
    )
    close = close_primary_loan_funding(
        ClosePrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Funding target reached.",
            investor_message="Funding target reached.",
            idempotency_key="market-close-guard",
            as_of_date=date(2030, 1, 11),
        )
    )
    holding_event_model = apps.get_model("holdings", "InvestorLoanHoldingEvent")
    holding_event = holding_event_model.objects.get()

    with pytest.raises(AppendOnlyViolation):
        close.save()
    with pytest.raises(AppendOnlyViolation):
        close.delete()
    with pytest.raises(AppendOnlyViolation):
        PrimaryLoanClose.objects.filter(id=close.id).update(reason="mutated")
    with pytest.raises(AppendOnlyViolation):
        holding_event.save()
    with pytest.raises(AppendOnlyViolation):
        holding_event.delete()
    with pytest.raises(AppendOnlyViolation):
        holding_event_model.objects.filter(id=holding_event.id).update(note="mutated")
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE marketplace_primary_primaryloanclose SET reason = %s WHERE id = %s",
                ["mutated", close.id],
            )
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE holdings_investorloanholdingevent SET note = %s WHERE id = %s",
                ["mutated", holding_event.id],
            )


@pytest.mark.django_db
def test_primary_cancellation_has_append_only_guards(
    admin_user: Model,
) -> None:
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    cancellation = cancel_primary_loan_funding(
        CancelPrimaryLoanFundingCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            reason="Campaign expired without orders.",
            idempotency_key="market-cancel-guard",
        )
    )

    with pytest.raises(AppendOnlyViolation):
        cancellation.save()
    with pytest.raises(AppendOnlyViolation):
        cancellation.delete()
    with pytest.raises(AppendOnlyViolation):
        PrimaryLoanCancellation.objects.filter(id=cancellation.id).update(reason="mutated")
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE marketplace_primary_primaryloancancellation SET reason = %s WHERE id = %s",
                ["mutated", cancellation.id],
            )


@pytest.mark.django_db
def test_loan_committed_principal_constraint_is_db_enforced(
    admin_user: Model,
) -> None:
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    loan_model = apps.get_model("loans", "Loan")

    with pytest.raises(DatabaseError), transaction.atomic():
        loan_model.objects.filter(id=loan.pk).update(committed_principal_minor=10_000_01)


@pytest.mark.django_db
def test_primary_order_event_has_app_and_db_append_only_guards(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    order = create_primary_investment_order(
        CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=10_000_00,
            idempotency_key="market-order-event-guard",
        )
    )
    event = PrimaryInvestmentOrderEvent.objects.get(order=order)

    with pytest.raises(AppendOnlyViolation):
        event.save()
    with pytest.raises(AppendOnlyViolation):
        event.delete()
    with pytest.raises(AppendOnlyViolation):
        PrimaryInvestmentOrderEvent.objects.filter(id=event.id).update(note="mutated")
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE marketplace_primary_primaryinvestmentorderevent "
                "SET note = %s WHERE id = %s",
                ["mutated", event.id],
            )


@pytest.mark.django_db
def test_primary_marketplace_api_flow(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    _declare_deposit(admin_user, investor, amount_minor=50_000_00)

    preview_response = client.get("/api/v1/marketplace/primary/loans/")
    client.force_login(cast(Any, investor))
    detail_response = client.get(f"/api/v1/marketplace/primary/loans/{loan.pk}/")
    order_response = client.post(
        "/api/v1/marketplace/primary/orders/",
        data={
            "loan_id": str(loan.pk),
            "amount_minor": 50_000_00,
            "idempotency_key": "api-market-order-1",
        },
        content_type="application/json",
    )
    acceptance = _create_primary_acceptance(
        investor,
        order_id=order_response.json()["id"],
        idempotency_key="api-market-accept-1",
    )
    allocation_response = client.post(
        f"/api/v1/marketplace/primary/orders/{order_response.json()['id']}/allocate-balance/",
        data={
            "document_acceptance_id": str(acceptance.pk),
            "idempotency_key": "api-market-allocate-1",
            **_sensitive_code_payload(investor, "primary_investment"),
        },
        content_type="application/json",
    )

    assert preview_response.status_code == 200
    assert preview_response.json()[0]["loan_id"] == str(loan.pk)
    assert preview_response.json()[0]["minimum_investment_minor"] == 100000
    assert preview_response.json()[0]["ltv_bps"] == 6667
    assert detail_response.status_code == 200
    assert detail_response.json()["investor_summary"]
    assert order_response.status_code == 201
    assert allocation_response.status_code == 200
    assert "idempotency_key" not in allocation_response.json()
    assert "metadata" not in allocation_response.json()
    assert allocation_response.json()["status"] == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
    assert PrimaryInvestmentOrder.objects.count() == 1

    client.force_login(cast(Any, admin_user))
    manual_close_response = client.post(
        f"/api/v1/marketplace/primary/admin/loans/{loan.pk}/close-funding/",
        data={
            "reason": "An admin must not put a published loan into effect manually.",
            "investor_message": "",
            "idempotency_key": "api-market-manual-close-rejected",
        },
        content_type="application/json",
    )
    close_response = client.post(
        "/api/v1/marketplace/primary/admin/loans/expiry-scan/",
        data={
            "as_of_date": "2030-01-11",
            "loan_ids": [str(loan.pk)],
            "idempotency_key": "api-market-close-1",
        },
        content_type="application/json",
    )

    assert manual_close_response.status_code == 400
    assert "automatically" in manual_close_response.json()["detail"]
    assert close_response.status_code == 200
    assert close_response.json()["closed_count"] == 1
    assert close_response.json()["closes"][0]["close_type"] == PrimaryLoanCloseType.PARTIAL
    assert close_response.json()["closes"][0]["accepted_principal_minor"] == 50_000_00


@pytest.mark.django_db
def test_primary_loan_detail_uses_readonly_impersonation_target(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    user_model: Any = get_user_model()
    superadmin = user_model.objects.create_superuser(
        email="market-superadmin@example.test",
        password="unused",
        full_name="Market Superadmin",
        account_type="superadmin",
        status="active",
    )
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)
    token = issue_readonly_impersonation_token(actor=superadmin, target_user_id=str(investor.pk))[
        "token"
    ]
    client.force_login(cast(Any, superadmin))

    response = client.get(
        f"/api/v1/marketplace/primary/loans/{loan.pk}/",
        **{f"HTTP_{READONLY_IMPERSONATION_HEADER.upper().replace('-', '_')}": token},
    )

    assert response.status_code == 200
    assert response.json()["investor_summary"]
    assert response.json()["loan_id"] == str(loan.pk)


@pytest.mark.django_db
def test_primary_loan_cancel_api_is_admin_only(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user)

    client.force_login(cast(Any, investor))
    forbidden = client.post(
        f"/api/v1/marketplace/primary/admin/loans/{loan.pk}/cancel-funding/",
        data={
            "reason": "Campaign expired.",
            "investor_message": "The campaign expired.",
            "idempotency_key": "api-market-cancel-forbidden",
        },
        content_type="application/json",
    )

    client.force_login(cast(Any, admin_user))
    response = client.post(
        f"/api/v1/marketplace/primary/admin/loans/{loan.pk}/cancel-funding/",
        data={
            "reason": "Campaign expired without sufficient funding.",
            "investor_message": "The campaign expired without sufficient funding.",
            "idempotency_key": "api-market-cancel-ok",
        },
        content_type="application/json",
    )

    loan.refresh_from_db()
    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert response.json()["released_order_count"] == 0
    assert response.json()["closed_not_invested_order_count"] == 0
    assert cast(Any, loan).status == "cancelled"


@pytest.mark.django_db
def test_primary_loan_expiry_scan_api_is_admin_only(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, funding_deadline=date(2030, 1, 10))

    client.force_login(cast(Any, investor))
    forbidden = client.post(
        "/api/v1/marketplace/primary/admin/loans/expiry-scan/",
        data={"as_of_date": "2030-01-11"},
        content_type="application/json",
    )

    client.force_login(cast(Any, admin_user))
    response = client.post(
        "/api/v1/marketplace/primary/admin/loans/expiry-scan/",
        data={
            "as_of_date": "2030-01-11",
            "loan_ids": [str(loan.pk)],
            "idempotency_key": "api-market-expiry-scan",
        },
        content_type="application/json",
    )

    loan.refresh_from_db()
    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert response.json()["cancelled_count"] == 1
    assert response.json()["cancellations"][0]["loan_id"] == str(loan.pk)
    assert cast(Any, loan).status == "cancelled"


@pytest.mark.django_db
def test_primary_order_batch_places_all_orders_behind_one_code(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan_a = _create_published_loan(admin_user, principal_minor=10_000_00)
    loan_b = _create_published_loan(admin_user, principal_minor=10_000_00)
    _declare_deposit(admin_user, investor, amount_minor=10_000_00, idempotency_key="batch-deposit")
    batch_key = "primary-batch-1"
    batch_items = [
        PrimaryOrderBatchItemCommand(loan_id=str(loan_a.pk), amount_minor=2_000_00),
        PrimaryOrderBatchItemCommand(loan_id=str(loan_b.pk), amount_minor=3_000_00),
    ]
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key="batch-accept",
        context_type="primary_order_batch",
        context_id=batch_key,
        data_snapshot={
            "currency": "CHF",
            "items": [
                {"loan_id": item.loan_id, "amount_minor": item.amount_minor} for item in batch_items
            ],
        },
    )
    result = place_primary_order_batch(
        PlacePrimaryOrderBatchCommand(
            actor=investor,
            items=batch_items,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=batch_key,
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )
    orders = result.orders
    loan_a.refresh_from_db()
    loan_b.refresh_from_db()
    assert len(orders) == 2
    assert all(order.status == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED for order in orders)
    assert cast(Any, loan_a).committed_principal_minor == 2_000_00
    assert cast(Any, loan_b).committed_principal_minor == 3_000_00
    assert result.batch.total_amount_minor == 5_000_00
    assert result.batch.currency_id == "CHF"
    assert result.batch.currency_totals == [{"currency": "CHF", "amount_minor": 5_000_00}]
    assert PrimaryInvestmentOrderBatch.objects.count() == 1
    assert all(
        cast(Any, order.document_acceptance).context_type == "primary_order" for order in orders
    )
    assert all(
        cast(Any, order.document_acceptance).data_snapshot["loan"]["id"] == str(order.loan_id)
        for order in orders
    )


@pytest.mark.django_db
def test_primary_order_batch_is_all_or_nothing(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan_a = _create_published_loan(admin_user, principal_minor=10_000_00)
    loan_b = _create_published_loan(admin_user, principal_minor=10_000_00)
    loan_b_ref = cast(Any, loan_b)
    loan_b_ref.status = "draft"
    loan_b_ref.published_at = None
    loan_b_ref.save(update_fields=["status", "published_at"])
    _declare_deposit(
        admin_user, investor, amount_minor=10_000_00, idempotency_key="batch-deposit-2"
    )
    batch_key = "primary-batch-2"
    batch_items = [
        PrimaryOrderBatchItemCommand(loan_id=str(loan_a.pk), amount_minor=2_000_00),
        PrimaryOrderBatchItemCommand(loan_id=str(loan_b.pk), amount_minor=3_000_00),
    ]
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key="batch-accept-2",
        context_type="primary_order_batch",
        context_id=batch_key,
        data_snapshot={
            "currency": "CHF",
            "items": [
                {"loan_id": item.loan_id, "amount_minor": item.amount_minor} for item in batch_items
            ],
        },
    )
    with pytest.raises(MarketplacePrimaryValidationError):
        place_primary_order_batch(
            PlacePrimaryOrderBatchCommand(
                actor=investor,
                items=batch_items,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key=batch_key,
                **_sensitive_code_payload(investor, "primary_investment"),
            )
        )
    loan_a.refresh_from_db()
    assert cast(Any, loan_a).committed_principal_minor == 0
    assert PrimaryInvestmentOrder.objects.filter(investor_user_id=investor.pk).count() == 0
    assert PrimaryInvestmentOrderBatch.objects.count() == 0


@pytest.mark.django_db
def test_primary_order_batch_replay_returns_existing_without_reusing_code(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan_a = _create_published_loan(admin_user, principal_minor=10_000_00)
    loan_b = _create_published_loan(admin_user, principal_minor=10_000_00)
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=10_000_00,
        idempotency_key="batch-replay-deposit",
    )
    items = [
        PrimaryOrderBatchItemCommand(loan_id=str(loan_b.pk), amount_minor=2_000_00),
        PrimaryOrderBatchItemCommand(loan_id=str(loan_a.pk), amount_minor=1_500_00),
    ]
    batch_key = "primary-batch-replay"
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key="batch-replay-accept",
        context_type="primary_order_batch",
        context_id=batch_key,
        data_snapshot={
            "currency": "CHF",
            "items": [
                {"loan_id": item.loan_id, "amount_minor": item.amount_minor}
                for item in reversed(items)
            ],
        },
    )
    command = PlacePrimaryOrderBatchCommand(
        actor=investor,
        items=items,
        document_acceptance_id=str(acceptance.pk),
        idempotency_key=batch_key,
        **_sensitive_code_payload(investor, "primary_investment"),
    )

    first = place_primary_order_batch(command)
    replay = place_primary_order_batch(command)

    assert replay.batch.id == first.batch.id
    assert [order.id for order in replay.orders] == [order.id for order in first.orders]
    assert PrimaryInvestmentOrderBatch.objects.count() == 1
    assert PrimaryInvestmentOrder.objects.count() == 2


@pytest.mark.django_db
def test_primary_order_batch_rejects_acceptance_payload_mismatch(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    batch_key = "primary-batch-mismatched-terms"
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key="batch-mismatch-accept",
        context_type="primary_order_batch",
        context_id=batch_key,
        data_snapshot={
            "currency": "CHF",
            "items": [{"loan_id": str(loan.pk), "amount_minor": 1_000_00}],
        },
    )

    with pytest.raises(
        MarketplacePrimaryValidationError,
        match="does not match the requested loans and amounts",
    ):
        place_primary_order_batch(
            PlacePrimaryOrderBatchCommand(
                actor=investor,
                items=[
                    PrimaryOrderBatchItemCommand(
                        loan_id=str(loan.pk),
                        amount_minor=2_000_00,
                    )
                ],
                document_acceptance_id=str(acceptance.pk),
                idempotency_key=batch_key,
                **_sensitive_code_payload(investor, "primary_investment"),
            )
        )

    assert PrimaryInvestmentOrder.objects.count() == 0
    assert PrimaryInvestmentOrderBatch.objects.count() == 0


@pytest.mark.django_db
def test_primary_order_batch_places_mixed_currencies_atomically(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan_chf = _create_published_loan(admin_user, principal_minor=10_000_00)
    loan_eur = _create_published_loan(
        admin_user,
        principal_minor=10_000_00,
        currency_code="EUR",
    )
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=3_000_00,
        currency="CHF",
        idempotency_key="batch-mixed-chf-deposit",
    )
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=4_000_00,
        currency="EUR",
        idempotency_key="batch-mixed-eur-deposit",
    )
    batch_key = "primary-batch-mixed-currency"
    items = [
        PrimaryOrderBatchItemCommand(loan_id=str(loan_chf.pk), amount_minor=2_000_00),
        PrimaryOrderBatchItemCommand(loan_id=str(loan_eur.pk), amount_minor=3_000_00),
    ]
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key="batch-mixed-accept",
        context_type="primary_order_batch",
        context_id=batch_key,
        data_snapshot={
            "items": [
                {
                    "loan_id": item.loan_id,
                    "amount_minor": item.amount_minor,
                    "currency": "CHF" if item.loan_id == str(loan_chf.pk) else "EUR",
                }
                for item in items
            ],
        },
    )

    result = place_primary_order_batch(
        PlacePrimaryOrderBatchCommand(
            actor=investor,
            items=items,
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=batch_key,
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )

    loan_chf.refresh_from_db()
    loan_eur.refresh_from_db()
    assert len(result.orders) == 2
    assert result.batch.currency_id is None
    assert result.batch.total_amount_minor is None
    assert result.batch.currency_totals == [
        {"currency": "CHF", "amount_minor": 2_000_00},
        {"currency": "EUR", "amount_minor": 3_000_00},
    ]
    assert cast(Any, loan_chf).committed_principal_minor == 2_000_00
    assert cast(Any, loan_eur).committed_principal_minor == 3_000_00
    assert PrimaryInvestmentOrder.objects.count() == 2
    assert PrimaryInvestmentOrderBatch.objects.count() == 1


@pytest.mark.django_db
def test_primary_order_batch_rolls_back_both_currencies_when_one_balance_is_short(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan_chf = _create_published_loan(admin_user, principal_minor=10_000_00)
    loan_eur = _create_published_loan(
        admin_user,
        principal_minor=10_000_00,
        currency_code="EUR",
    )
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=3_000_00,
        currency="CHF",
        idempotency_key="batch-mixed-rollback-chf-deposit",
    )
    batch_key = "primary-batch-mixed-rollback"
    items = [
        PrimaryOrderBatchItemCommand(loan_id=str(loan_chf.pk), amount_minor=2_000_00),
        PrimaryOrderBatchItemCommand(loan_id=str(loan_eur.pk), amount_minor=2_000_00),
    ]
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key="batch-mixed-rollback-accept",
        context_type="primary_order_batch",
        context_id=batch_key,
        data_snapshot={
            "items": [
                {
                    "loan_id": str(loan_chf.pk),
                    "amount_minor": 2_000_00,
                    "currency": "CHF",
                },
                {
                    "loan_id": str(loan_eur.pk),
                    "amount_minor": 2_000_00,
                    "currency": "EUR",
                },
            ],
        },
    )

    with pytest.raises(MarketplacePrimaryValidationError, match="Insufficient eligible balance"):
        place_primary_order_batch(
            PlacePrimaryOrderBatchCommand(
                actor=investor,
                items=items,
                document_acceptance_id=str(acceptance.pk),
                idempotency_key=batch_key,
                **_sensitive_code_payload(investor, "primary_investment"),
            )
        )

    loan_chf.refresh_from_db()
    loan_eur.refresh_from_db()
    assert cast(Any, loan_chf).committed_principal_minor == 0
    assert cast(Any, loan_eur).committed_principal_minor == 0
    assert PrimaryInvestmentOrder.objects.count() == 0
    assert PrimaryInvestmentOrderBatch.objects.count() == 0


@pytest.mark.django_db
def test_primary_order_batch_api_returns_committed_amount_and_currency(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=5_000_00,
        idempotency_key="batch-api-deposit",
    )
    batch_key = "primary-batch-api"
    amount_minor = 2_000_00
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key="batch-api-accept",
        context_type="primary_order_batch",
        context_id=batch_key,
        data_snapshot={
            "currency": "CHF",
            "items": [{"loan_id": str(loan.pk), "amount_minor": amount_minor}],
        },
    )
    code = _sensitive_code_payload(investor, "primary_investment")
    client.force_login(cast(Any, investor))

    response = client.post(
        "/api/v1/marketplace/primary/orders/batch/",
        data={
            "items": [{"loan_id": str(loan.pk), "amount_minor": amount_minor}],
            "document_acceptance_id": str(acceptance.pk),
            "idempotency_key": batch_key,
            **code,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["currency"] == "CHF"
    assert payload["currency_totals"] == [{"currency": "CHF", "amount_minor": amount_minor}]
    assert payload["order_count"] == 1
    assert payload["total_amount_minor"] == amount_minor
    assert payload["orders"][0]["allocated_amount_minor"] == amount_minor


@pytest.mark.django_db
def test_primary_order_batch_has_app_and_db_append_only_guards(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, principal_minor=10_000_00)
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=5_000_00,
        idempotency_key="batch-append-only-deposit",
    )
    batch_key = "primary-batch-append-only"
    amount_minor = 1_000_00
    acceptance = _create_primary_acceptance(
        investor,
        order_id="",
        idempotency_key="batch-append-only-accept",
        context_type="primary_order_batch",
        context_id=batch_key,
        data_snapshot={
            "currency": "CHF",
            "items": [{"loan_id": str(loan.pk), "amount_minor": amount_minor}],
        },
    )
    result = place_primary_order_batch(
        PlacePrimaryOrderBatchCommand(
            actor=investor,
            items=[
                PrimaryOrderBatchItemCommand(
                    loan_id=str(loan.pk),
                    amount_minor=amount_minor,
                )
            ],
            document_acceptance_id=str(acceptance.pk),
            idempotency_key=batch_key,
            **_sensitive_code_payload(investor, "primary_investment"),
        )
    )

    with pytest.raises(AppendOnlyViolation):
        result.batch.save()
    with pytest.raises(AppendOnlyViolation):
        PrimaryInvestmentOrderBatch.objects.filter(id=result.batch.id).update(order_count=2)
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE marketplace_primary_primaryinvestmentorderbatch "
                "SET order_count = 2 WHERE id = %s",
                [
                    str(result.batch.id).replace("-", "")
                    if connection.vendor == "sqlite"
                    else result.batch.id
                ],
            )
