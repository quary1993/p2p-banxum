from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.investor_portal.services import (
    get_investor_activity,
    get_investor_balances,
    get_investor_portfolio,
)
from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import Currency


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="portal-admin@example.test",
            password="AdminPass123!",
            full_name="Portal Admin",
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
            email="portal-investor@example.test",
            full_name="Portal Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )


@pytest.fixture
def other_investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="portal-other@example.test",
            full_name="Portal Other",
            account_type="natural_person_lender",
            status="active",
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


def _at(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=business_timezone())


def _declare_deposit(
    *,
    admin_user: Model,
    investor: Model,
    amount_minor: int,
    value_date: date,
    idempotency_key: str,
    currency: str = "CHF",
) -> Model:
    ledger_services = import_module("backend.apps.ledger.services")
    result = ledger_services.declare_lender_deposit(
        ledger_services.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency=currency,
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier=f"{currency}-COLLECTION",
            payer_name=str(cast(Any, investor).full_name),
            payer_account_identifier=f"{currency}-INVESTOR-IBAN",
            bank_reference=f"BANK-{idempotency_key}",
            payment_reference=f"INV-{investor.pk}",
            evidence_reference=f"statement:{idempotency_key}",
            idempotency_key=idempotency_key,
        )
    )
    return cast(Model, result.balance_lot)


def _create_borrower(admin_user: Model, *, name: str, country: str = "CH") -> Model:
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    return cast(
        Model,
        borrower_model.objects.create(
            legal_name=name,
            year_founded=2018,
            entity_type="swiss_company",
            kyb_status="approved",
            compliance_hold=False,
            country=country,
            created_by_admin_id=admin_user.pk,
        ),
    )


def _create_loan(
    admin_user: Model,
    borrower: Model,
    *,
    title: str,
    status: str = "funded",
    currency: str = "CHF",
    principal_minor: int = 10_000_00,
) -> Model:
    loan_model = apps.get_model("loans", "Loan")
    currency_obj = Currency.objects.get(code=currency)
    return cast(
        Model,
        loan_model.objects.create(
            borrower=borrower,
            status=status,
            title=title,
            investor_summary="Portal test loan.",
            purpose="bridge_financing",
            principal_minor=principal_minor,
            currency=currency_obj,
            interest_rate_bps=1000,
            term_months=12,
            repayment_type="equal_installments",
            funding_deadline=date(2026, 1, 31),
            first_payment_date=date(2026, 2, 28),
            collateral_type="real_estate",
            collateral_value_minor=20_000_00,
            risk_rating="BBB",
            borrower_success_fee_bps=200,
            committed_principal_minor=principal_minor,
            total_scheduled_principal_minor=principal_minor,
            total_scheduled_interest_minor=1_000_00,
            created_by_admin_id=admin_user.pk,
            published_at=timezone.now(),
        ),
    )


def _create_holding(
    *,
    admin_user: Model,
    investor: Model,
    loan: Model,
    amount_minor: int,
    idempotency_key: str,
    status: str = "active",
) -> Model:
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    return cast(
        Model,
        holding_model.objects.create(
            loan=loan,
            investor_user_id=investor.pk,
            source_type="manual_admin",
            source_id=idempotency_key,
            status=status,
            original_principal_minor=amount_minor,
            current_principal_minor=amount_minor if status == "active" else 0,
            currency=cast(Any, loan).currency,
            loan_share_ppm=500_000,
            assignment_effective_at=_at(date(2026, 1, 1)),
            created_by_admin_id=admin_user.pk,
            metadata={},
            idempotency_key=idempotency_key,
        ),
    )


def _create_primary_order(
    *,
    investor: Model,
    loan: Model,
    idempotency_key: str,
) -> Model:
    order_model = apps.get_model("marketplace_primary", "PrimaryInvestmentOrder")
    return cast(
        Model,
        order_model.objects.create(
            loan=loan,
            investor_user_id=investor.pk,
            status="pending",
            requested_amount_minor=2_000_00,
            allocated_amount_minor=0,
            currency=cast(Any, loan).currency,
            created_by_user_id=investor.pk,
            idempotency_key=idempotency_key,
        ),
    )


def _create_secondary_listing_acceptance(investor: Model) -> Model:
    template_model = apps.get_model("documents", "DocumentTemplate")
    version_model = apps.get_model("documents", "DocumentTemplateVersion")
    acceptance_model = apps.get_model("documents", "DocumentAcceptanceEvidence")
    template = template_model.objects.create(
        category="secondary_market_listing",
        template_key="portal-secondary-listing",
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
        checkbox_labels=["I accept."],
        variable_schema={},
        content_hash="d" * 64,
        created_by_superadmin_id=investor.pk,
        published_at=timezone.now(),
    )
    template.current_published_version = version
    template.save(update_fields=["current_published_version"])
    return cast(
        Model,
        acceptance_model.objects.create(
            user_id=investor.pk,
            category="secondary_market_listing",
            template=template,
            template_version=version,
            template_version_number=1,
            template_hash=version.content_hash,
            context_type="secondary_market_listing",
            context_id="portal-secondary",
            accepted_checkbox_labels=["I accept."],
            data_snapshot={},
            idempotency_key="portal-secondary-listing-acceptance",
        ),
    )


@pytest.mark.django_db
def test_portal_requires_financial_access(investor: Model) -> None:
    client = Client()
    client.force_login(cast(Any, investor))

    response = client.get("/api/v1/investor/portal/dashboard/")

    assert response.status_code == 403
    assert "requires active lender access" in response.json()["detail"]


@pytest.mark.django_db
def test_balances_are_self_scoped_and_bucketed(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    as_of = _at(date(2026, 3, 15))
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=1_000_00,
        value_date=date(2026, 3, 1),
        idempotency_key="portal-investable",
    )
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=2_000_00,
        value_date=date(2026, 2, 1),
        idempotency_key="portal-withdraw-only",
    )
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=3_000_00,
        value_date=date(2026, 1, 1),
        idempotency_key="portal-overdue",
    )
    penalty_lot = _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=4_000_00,
        value_date=date(2026, 1, 2),
        idempotency_key="portal-penalty",
    )
    cast(Any, penalty_lot).status = "penalty_mode"
    penalty_lot.save(update_fields=["status"])
    _declare_deposit(
        admin_user=admin_user,
        investor=other_investor,
        amount_minor=9_000_00,
        value_date=date(2026, 3, 1),
        idempotency_key="portal-other-investor",
    )

    payload = get_investor_balances(actor=investor, as_of=as_of)
    chf = next(item for item in payload["summaries"] if item["currency"] == "CHF")

    assert chf["total_available_minor"] == 10_000_00
    assert chf["investable_minor"] == 1_000_00
    assert chf["withdraw_only_minor"] == 2_000_00
    assert chf["overdue_minor"] == 3_000_00
    assert chf["penalty_mode_minor"] == 4_000_00
    assert payload["has_penalty_mode_balance"] is True
    assert {lot["bucket"] for lot in payload["lots"]} == {
        "investable",
        "withdraw_only",
        "overdue",
        "penalty_mode",
    }


@pytest.mark.django_db
def test_portfolio_exposure_uses_only_actor_holdings(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    borrower = _create_borrower(admin_user, name="Portal Borrower AG", country="CH")
    other_borrower = _create_borrower(admin_user, name="Other Borrower AG", country="DE")
    loan = _create_loan(admin_user, borrower, title="Portal loan", status="funded")
    late_loan = _create_loan(admin_user, other_borrower, title="Late portal loan", status="late")
    other_loan = _create_loan(admin_user, other_borrower, title="Other loan", status="funded")
    _create_holding(
        admin_user=admin_user,
        investor=investor,
        loan=loan,
        amount_minor=10_000_00,
        idempotency_key="portal-holding-1",
    )
    _create_holding(
        admin_user=admin_user,
        investor=investor,
        loan=late_loan,
        amount_minor=5_000_00,
        idempotency_key="portal-holding-2",
    )
    _create_holding(
        admin_user=admin_user,
        investor=other_investor,
        loan=other_loan,
        amount_minor=99_000_00,
        idempotency_key="portal-other-holding",
    )

    payload = get_investor_portfolio(actor=investor, as_of=_at(date(2026, 4, 1)))

    assert payload["summary"]["active_holding_count"] == 2
    assert payload["summary"]["outstanding_principal_by_currency"] == [
        {"currency": "CHF", "amount_minor": 15_000_00}
    ]
    assert payload["summary"]["late_or_defaulted_exposure_by_currency"] == [
        {"currency": "CHF", "amount_minor": 5_000_00}
    ]
    assert {holding["loan"]["loan_title"] for holding in payload["holdings"]} == {
        "Portal loan",
        "Late portal loan",
    }
    assert all(holding["current_principal_minor"] != 99_000_00 for holding in payload["holdings"])
    borrower_exposure = payload["exposure"]["by_borrower"]
    assert {item["name"] for item in borrower_exposure} == {
        "Portal Borrower AG",
        "Other Borrower AG",
    }


@pytest.mark.django_db
def test_activity_is_self_scoped(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    borrower = _create_borrower(admin_user, name="Activity Borrower AG")
    loan = _create_loan(admin_user, borrower, title="Activity loan")
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=1_500_00,
        value_date=date(2026, 3, 1),
        idempotency_key="portal-activity-deposit",
    )
    _declare_deposit(
        admin_user=admin_user,
        investor=other_investor,
        amount_minor=7_500_00,
        value_date=date(2026, 3, 1),
        idempotency_key="portal-activity-other-deposit",
    )
    _create_primary_order(investor=investor, loan=loan, idempotency_key="portal-order-1")

    payload = get_investor_activity(actor=investor, limit=20)

    assert {entry["activity_type"] for entry in payload["entries"]} == {
        "balance_deposit",
        "primary_order",
    }
    assert all(entry["amount_minor"] != 7_500_00 for entry in payload["entries"])
    assert any(entry["loan_title"] == "Activity loan" for entry in payload["entries"])


@pytest.mark.django_db
def test_read_history_endpoints_return_self_scoped_payloads(
    admin_user: Model,
    investor: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approve_financial_access(investor)
    borrower = _create_borrower(admin_user, name="History Borrower AG")
    loan = _create_loan(admin_user, borrower, title="History loan")
    holding = _create_holding(
        admin_user=admin_user,
        investor=investor,
        loan=loan,
        amount_minor=8_000_00,
        idempotency_key="portal-history-holding",
    )
    _create_primary_order(investor=investor, loan=loan, idempotency_key="portal-history-order")
    acceptance = _create_secondary_listing_acceptance(investor)
    listing_model = apps.get_model("secondary_market", "SecondaryMarketListing")
    listing_model.objects.create(
        holding=holding,
        loan=loan,
        seller_user_id=investor.pk,
        status="active",
        publication_type="automatic",
        current_principal_minor=8_000_00,
        currency=cast(Any, loan).currency,
        price_bps=10_000,
        transfer_price_minor=8_000_00,
        discount_premium_bps=0,
        accrued_interest_minor=0,
        accrued_interest_to_date=date(2026, 3, 1),
        maker_fee_bps=25,
        taker_fee_bps=75,
        maker_fee_minor=20_00,
        taker_fee_minor=60_00,
        seller_net_proceeds_minor=7_980_00,
        buyer_total_cost_minor=8_060_00,
        loan_status_at_listing="funded",
        document_acceptance=acceptance,
        listed_at=timezone.now(),
        created_by_user_id=investor.pk,
        idempotency_key="portal-history-listing",
    )
    quote_model = apps.get_model("fx", "FxQuote")
    quote_model.objects.create(
        investor_user_id=investor.pk,
        source_currency=Currency.objects.get(code="CHF"),
        target_currency=Currency.objects.get(code="EUR"),
        source_amount_minor=1_000_00,
        provider="mock",
        rate=Decimal("1.050000000000"),
        previous_day_average_rate=Decimal("1.040000000000"),
        platform_fee_bps=150,
        gross_target_amount_minor=1_050_00,
        fee_minor=15_75,
        target_amount_minor=1_034_25,
        limit_chf_equivalent_minor=100_000_00,
        issued_at=timezone.now(),
        expires_at=timezone.now() + timedelta(seconds=60),
        provider_rate_timestamp=timezone.now(),
        sanity_check_passed=True,
        idempotency_key="portal-history-quote",
    )
    fixed_now = timezone.now()
    monkeypatch.setattr("backend.apps.investor_portal.services.now_utc", lambda: fixed_now)
    client = Client()
    client.force_login(cast(Any, investor))

    order_response = client.get("/api/v1/investor/portal/primary-orders/")
    secondary_response = client.get("/api/v1/investor/portal/secondary-market/")
    fx_response = client.get("/api/v1/investor/portal/fx/")

    assert order_response.status_code == 200
    assert order_response.json()["orders"][0]["loan_title"] == "History loan"
    assert secondary_response.status_code == 200
    secondary_payload = secondary_response.json()
    assert secondary_payload["listings"][0]["seller_net_proceeds_minor"] == 798000
    assert "seller_user_id" not in secondary_payload["listings"][0]
    assert fx_response.status_code == 200
    assert fx_response.json()["quotes"][0]["source_currency"] == "CHF"
