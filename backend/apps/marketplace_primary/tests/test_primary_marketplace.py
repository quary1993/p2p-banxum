from __future__ import annotations

from datetime import date
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
    PrimaryInvestmentOrderEvent,
    PrimaryInvestmentOrderStatus,
)
from backend.apps.marketplace_primary.services import (
    AllocatePrimaryInvestmentOrderCommand,
    CreatePrimaryInvestmentOrderCommand,
    MarketplacePrimaryAuthorizationError,
    MarketplacePrimaryValidationError,
    ReleasePrimaryInvestmentOrderCommand,
    allocate_primary_order_from_balance,
    create_primary_investment_order,
    release_primary_order_balance,
)
from backend.apps.platform_core.models import AuditEvent, Currency, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation


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
    funding_deadline: date = date(2026, 6, 25),
) -> Model:
    borrower = _create_borrower(admin_user)
    loan_model = apps.get_model("loans", "Loan")
    currency = Currency.objects.get(code="CHF")
    return cast(
        Model,
        loan_model.objects.create(
            borrower=borrower,
            status="published",
            title="Real estate bridge loan",
            investor_summary="Short real-estate backed bridge facility.",
            purpose="bridge_financing",
            principal_minor=principal_minor,
            currency=currency,
            interest_rate_bps=1000,
            term_months=12,
            repayment_type="equal_installments",
            funding_deadline=funding_deadline,
            first_payment_date=date(2026, 7, 25),
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
    value_date: date = date(2026, 6, 2),
    idempotency_key: str = "market-deposit-1",
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
            collection_account_identifier="CH00GARANTAMARKET",
            payer_name="Market Investor",
            payer_account_identifier="CH11INVESTOR",
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
) -> Model:
    template_model = apps.get_model("documents", "DocumentTemplate")
    version_model = apps.get_model("documents", "DocumentTemplateVersion")
    acceptance_model = apps.get_model("documents", "DocumentAcceptanceEvidence")
    template = template_model.objects.create(
        category="primary_market_investment",
        template_key="default",
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
            category="primary_market_investment",
            template=template,
            template_version=version,
            template_version_number=1,
            template_hash=version.content_hash,
            context_type="primary_order",
            context_id=order_id,
            accepted_checkbox_labels=["I accept the primary-market terms."],
            data_snapshot={},
            idempotency_key=idempotency_key,
        ),
    )


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
def test_balance_allocation_blocks_lots_that_expire_before_funding_deadline(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    loan = _create_published_loan(admin_user, funding_deadline=date(2026, 7, 10))
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=25_000_00,
        value_date=date(2026, 6, 1),
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

    with pytest.raises(MarketplacePrimaryValidationError, match="Insufficient eligible"):
        allocate_primary_order_from_balance(
            AllocatePrimaryInvestmentOrderCommand(
                actor=investor,
                order_id=str(order.id),
                document_acceptance_id=str(acceptance.pk),
                idempotency_key="market-allocate-expiring",
            )
        )


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
        )
    )
    deposit.balance_lot.refresh_from_db()
    loan.refresh_from_db()

    assert allocated.status == PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED
    assert allocated.allocated_amount_minor == 10_000_00
    assert deposit.balance_lot.available_amount_minor == 20_000_00
    assert cast(Any, loan).committed_principal_minor == 30_000_00


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
    _declare_deposit(admin_user, investor, amount_minor=20_000_00)

    preview_response = client.get("/api/v1/marketplace/primary/loans/")
    client.force_login(cast(Any, investor))
    detail_response = client.get(f"/api/v1/marketplace/primary/loans/{loan.pk}/")
    order_response = client.post(
        "/api/v1/marketplace/primary/orders/",
        data={
            "loan_id": str(loan.pk),
            "amount_minor": 10_000_00,
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
        },
        content_type="application/json",
    )

    assert preview_response.status_code == 200
    assert preview_response.json()[0]["loan_id"] == str(loan.pk)
    assert detail_response.status_code == 200
    assert detail_response.json()["investor_summary"]
    assert order_response.status_code == 201
    assert allocation_response.status_code == 200
    assert allocation_response.json()["status"] == PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
    assert PrimaryInvestmentOrder.objects.count() == 1
