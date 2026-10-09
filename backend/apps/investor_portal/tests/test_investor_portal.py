from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any, cast
from unittest.mock import patch

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.investor_portal.services import (
    InvestorDocumentDownloadCommand,
    InvestorPortalValidationError,
    download_investor_document,
    get_deposit_instructions,
    get_investor_activity,
    get_investor_balances,
    get_investor_documents,
    get_investor_notifications,
    get_investor_portfolio,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.time import business_date, business_timezone, now_utc
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.services.impersonation import issue_readonly_impersonation_token
from backend.apps.platform_core.services.settings import (
    SetPlatformSettingCommand,
    seed_default_platform_settings,
    set_platform_setting,
)


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
def superadmin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="portal-superadmin@example.test",
            password="AdminPass123!",
            full_name="Portal Superadmin",
            account_type="superadmin",
            status="active",
            is_staff=True,
            is_superuser=True,
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
            payer_account_identifier="CH9300762011623852957",
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
            original_principal_minor=principal_minor,
            principal_minor=principal_minor,
            currency=currency_obj,
            interest_rate_bps=1000,
            term_months=12,
            repayment_type="equal_installments",
            loan_start_date=date(2026, 1, 31),
            funding_deadline=date(2026, 1, 31),
            first_payment_date=date(2026, 2, 28),
            collateral_type="real_estate",
            collateral_value_minor=20_000_00,
            risk_rating="BBB",
            default_penalty_interest_bps=1200,
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


def _create_registration_acceptance(investor: Model, *, key: str = "portal-acceptance") -> Model:
    template_model = apps.get_model("documents", "DocumentTemplate")
    version_model = apps.get_model("documents", "DocumentTemplateVersion")
    acceptance_model = apps.get_model("documents", "DocumentAcceptanceEvidence")
    template = template_model.objects.create(
        category="registration",
        template_key=key,
        language="en",
        name="Registration terms",
        created_by_superadmin_id=investor.pk,
    )
    version = version_model.objects.create(
        template=template,
        version_number=1,
        status="published",
        title="Registration terms",
        body="BANXUM registration terms.",
        checkbox_labels=["I accept the registration terms."],
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
            category="registration",
            template=template,
            template_version=version,
            template_version_number=1,
            template_hash=version.content_hash,
            context_type="registration",
            context_id=str(investor.pk),
            accepted_checkbox_labels=["I accept the registration terms."],
            data_snapshot={},
            idempotency_key=key,
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
    assert chf["investable_minor"] == 3_000_00
    assert chf["withdraw_only_minor"] == 0
    assert chf["overdue_minor"] == 3_000_00
    assert chf["penalty_mode_minor"] == 4_000_00
    assert payload["has_penalty_mode_balance"] is True
    assert {lot["bucket"] for lot in payload["lots"]} == {
        "investable",
        "overdue",
        "penalty_mode",
    }


@pytest.mark.django_db
def test_deadline_date_is_the_last_withdraw_only_day_before_overdue(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=1_000_00,
        value_date=date(2026, 1, 14),
        idempotency_key="portal-deadline-day",
    )

    deadline_day = get_investor_balances(actor=investor, as_of=_at(date(2026, 3, 15)))
    day_after = get_investor_balances(actor=investor, as_of=_at(date(2026, 3, 16)))

    lot = deadline_day["lots"][0]
    assert (lot["bucket"], lot["days_until_withdrawal_deadline"]) == ("withdraw_only", 0)
    assert lot["requires_withdrawal"] is True
    chf = next(item for item in deadline_day["summaries"] if item["currency"] == "CHF")
    assert (chf["withdraw_only_minor"], chf["overdue_minor"]) == (1_000_00, 0)
    assert day_after["lots"][0]["bucket"] == "overdue"


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
    installment_model = apps.get_model("loans", "LoanInstallment")
    installment_model.objects.create(
        loan=loan,
        schedule_version=cast(Any, loan).schedule_version,
        installment_number=1,
        due_date=date(2026, 2, 28),
        principal_minor=5_000_00,
        interest_minor=100_00,
        total_minor=5_100_00,
    )
    installment_model.objects.create(
        loan=loan,
        schedule_version=cast(Any, loan).schedule_version,
        installment_number=2,
        due_date=date(2026, 3, 31),
        principal_minor=5_000_00,
        interest_minor=50_00,
        total_minor=5_050_00,
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
    portal_holding = next(
        holding
        for holding in payload["holdings"]
        if holding["loan"]["loan_title"] == "Portal loan"
    )
    portal_loan = portal_holding["loan"]
    assert portal_loan["default_penalty_interest_bps"] == 1200
    assert portal_loan["collateral_value_minor"] == 20_000_00
    assert portal_loan["collateral_description"] == ""
    assert portal_loan["schedule_version"] == 1
    assert [row["installment_number"] for row in portal_loan["schedule"]] == [1, 2]
    assert portal_loan["schedule"][0]["status"] == "overdue"
    assert portal_loan["schedule"][0]["outstanding_total_minor"] == 5_100_00
    assert [
        row["projected_principal_minor"]
        for row in portal_holding["investment_schedule"]
    ] == [5_000_00, 5_000_00]
    assert [
        row["projected_interest_minor"]
        for row in portal_holding["investment_schedule"]
    ] == [100_00, 50_00]
    borrower_exposure = payload["exposure"]["by_borrower"]
    assert {item["name"] for item in borrower_exposure} == {
        "Portal Borrower AG",
        "Other Borrower AG",
    }


@pytest.mark.django_db
def test_portfolio_investment_schedule_uses_exact_current_holding_weights(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    borrower = _create_borrower(admin_user, name="Weighted Schedule Borrower AG")
    loan = _create_loan(
        admin_user,
        borrower,
        title="Weighted schedule loan",
        principal_minor=10_00,
    )
    investor_holding = _create_holding(
        admin_user=admin_user,
        investor=investor,
        loan=loan,
        amount_minor=3_33,
        idempotency_key="portal-weighted-holding-investor",
    )
    _create_holding(
        admin_user=admin_user,
        investor=other_investor,
        loan=loan,
        amount_minor=6_67,
        idempotency_key="portal-weighted-holding-other",
    )
    installment_model = apps.get_model("loans", "LoanInstallment")
    installment_model.objects.create(
        loan=loan,
        schedule_version=cast(Any, loan).schedule_version,
        installment_number=1,
        due_date=date(2026, 2, 28),
        principal_minor=5_00,
        interest_minor=1_00,
        total_minor=6_00,
    )
    installment_model.objects.create(
        loan=loan,
        schedule_version=cast(Any, loan).schedule_version,
        installment_number=2,
        due_date=date(2026, 3, 31),
        principal_minor=5_00,
        interest_minor=1_01,
        total_minor=6_01,
    )

    payload = get_investor_portfolio(actor=investor, as_of=_at(date(2026, 1, 31)))

    holding = next(
        item for item in payload["holdings"] if item["id"] == str(investor_holding.pk)
    )
    schedule = holding["investment_schedule"]
    assert [row["projected_principal_minor"] for row in schedule] == [1_67, 1_66]
    assert [row["projected_interest_minor"] for row in schedule] == [33, 34]
    assert sum(row["projected_principal_minor"] for row in schedule) == 3_33
    assert sum(row["projected_total_minor"] for row in schedule) == 4_00


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
    listing = listing_model.objects.create(
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
    listing_event_model = apps.get_model("secondary_market", "SecondaryMarketListingEvent")
    listing_event_model.objects.create(
        listing=listing,
        holding_id=holding.pk,
        loan_id=loan.pk,
        seller_user_id=investor.pk,
        event_type="created",
        actor_user_id=investor.pk,
        actor_account_type="natural_person_lender",
        new_status="active",
        metadata={
            "current_principal_minor": 8_000_00,
            "transfer_price_minor": 8_000_00,
            "price_bps": 10_000,
        },
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
    portfolio_response = client.get("/api/v1/investor/portal/portfolio/")
    secondary_response = client.get("/api/v1/investor/portal/secondary-market/")
    fx_response = client.get("/api/v1/investor/portal/fx/")

    assert order_response.status_code == 200
    assert order_response.json()["orders"][0]["loan_title"] == "History loan"
    assert portfolio_response.status_code == 200
    open_listing = portfolio_response.json()["holdings"][0]["open_secondary_listing"]
    assert open_listing["id"] == str(listing.pk)
    assert open_listing["status"] == "active"
    assert secondary_response.status_code == 200
    secondary_payload = secondary_response.json()
    assert secondary_payload["listings"][0]["seller_net_proceeds_minor"] == 798000
    assert "seller_user_id" not in secondary_payload["listings"][0]
    assert secondary_payload["entries"][0]["action"] == "list"
    assert secondary_payload["entries"][0]["event_type"] == "created"
    assert fx_response.status_code == 200
    assert fx_response.json()["quotes"][0]["source_currency"] == "CHF"


@pytest.mark.django_db
def test_deposit_instructions_are_self_scoped_and_config_driven(investor: Model) -> None:
    _approve_financial_access(investor)
    set_platform_setting(
        SetPlatformSettingCommand(
            actor=ActorRef.system(),
            key="payments.deposit_instructions_by_currency",
            value={
                "CHF": {
                    "account_holder_name": "Garanta Finanzgruppe AG",
                    "iban": "CH9300762011623852957",
                    "qr_iban": "CH4431999123000889012",
                    "bic": "TESTCHZZ",
                    "bank_name": "Test Bank CHF",
                    "collection_account_identifier": "CHF-COLLECTION",
                    "qr_bill_payload": "SPC\n0200\n1\nCH9300762011623852957\n\n\n",
                    "notes": "CHF only.",
                }
            },
            value_type="json",
            reason="test",
        )
    )

    payload = get_deposit_instructions(actor=investor)
    chf = next(item for item in payload["instructions"] if item["currency"] == "CHF")

    assert chf["iban"] == "CH9300762011623852957"
    assert chf["qr_iban"] == "CH4431999123000889012"
    assert chf["qr_bill_payload"] == "SPC\n0200\n1\nCH9300762011623852957\n\n\n"
    assert chf["is_configured"] is True
    assert chf["payment_reference"] == f"BX-CHF-{cast(Any, investor).investor_reference}"


@pytest.mark.django_db
def test_default_deposit_instructions_project_chf_eur_collector_accounts(
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    seed_default_platform_settings()

    payload = get_deposit_instructions(actor=investor)
    by_currency = {item["currency"]: item for item in payload["instructions"]}

    assert by_currency["CHF"]["iban"] == "CH1183019GARANTAFI001"
    assert by_currency["CHF"]["qr_iban"] == "CH8330334GARANTAFI001"
    assert by_currency["CHF"]["bic"] == "YAPECHZ2"
    assert by_currency["CHF"]["collection_account_identifier"] == "Garanta_CHF"
    assert by_currency["CHF"]["qr_bill_payload"].startswith("SPC\n0200\n1\n")
    assert by_currency["CHF"]["payment_reference"] == (
        f"BX-CHF-{cast(Any, investor).investor_reference}"
    )
    assert by_currency["EUR"]["iban"] == "CH8183019GARANTAFI002"
    assert by_currency["EUR"]["bic"] == "YAPECHZ2"
    assert by_currency["EUR"]["collection_account_identifier"] == "Garanta_EUR"
    assert by_currency["EUR"]["qr_bill_payload"] == ""
    assert by_currency["EUR"]["payment_reference"] == (
        f"BX-EUR-{cast(Any, investor).investor_reference}"
    )


@pytest.mark.django_db
def test_investor_documents_and_acceptance_download_are_self_scoped(
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    own_acceptance = _create_registration_acceptance(investor, key="portal-own-acceptance")
    other_acceptance = _create_registration_acceptance(
        other_investor,
        key="portal-other-acceptance",
    )

    listing = get_investor_documents(actor=investor)
    own_document = next(
        item for item in listing["documents"] if item["id"] == str(own_acceptance.pk)
    )
    assert own_document["title"] == "Lender user agreement"
    assert own_document["generated_on_request"] is True
    assert own_document["output_formats"] == ["pdf", "csv"]
    assert str(other_acceptance.pk) not in {item["id"] for item in listing["documents"]}

    artifact = download_investor_document(
        InvestorDocumentDownloadCommand(
            actor=investor,
            document_kind="acceptance_evidence",
            document_id=str(own_acceptance.pk),
            output_format="pdf",
        )
    )
    assert artifact["content_type"] == "application/pdf"
    assert artifact["content_encoding"] == "base64"
    assert artifact["content_sha256"]
    with pytest.raises(InvestorPortalValidationError):
        download_investor_document(
            InvestorDocumentDownloadCommand(
                actor=investor,
                document_kind="acceptance_evidence",
                document_id=str(other_acceptance.pk),
                output_format="pdf",
            )
        )


@pytest.mark.django_db
def test_investor_document_download_api_returns_generated_pdf(
    client: Client,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    acceptance = _create_registration_acceptance(investor, key="portal-api-pdf-acceptance")
    client.force_login(cast(Any, investor))

    response = client.post(
        "/api/v1/investor/portal/documents/download/",
        data={
            "document_kind": "acceptance_evidence",
            "document_id": str(acceptance.pk),
            "output_format": "pdf",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_type"] == "application/pdf"
    assert payload["content_encoding"] == "base64"
    assert payload["content_sha256"]
    assert payload["manifest"]["output_format"] == "pdf"
    assert payload["manifest"]["content_sha256"] == payload["content_sha256"]


@pytest.mark.django_db
def test_superadmin_readonly_impersonation_can_read_and_download_without_user_attribution(
    client: Client,
    superadmin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    acceptance = _create_registration_acceptance(investor, key="portal-impersonated-acceptance")
    token_payload = issue_readonly_impersonation_token(
        actor=superadmin_user,
        target_user_id=str(investor.pk),
    )
    client.force_login(cast(Any, superadmin_user))

    dashboard_response = client.get(
        "/api/v1/investor/portal/dashboard/",
        HTTP_X_BANXUM_IMPERSONATE=token_payload["token"],
    )
    assert dashboard_response.status_code == 200

    download_response = client.post(
        "/api/v1/investor/portal/documents/download/",
        data={
            "document_kind": "acceptance_evidence",
            "document_id": str(acceptance.pk),
            "output_format": "pdf",
        },
        content_type="application/json",
        HTTP_X_BANXUM_IMPERSONATE=token_payload["token"],
    )

    assert download_response.status_code == 200
    artifact_model = apps.get_model("documents", "DocumentRenderedArtifact")
    artifact = artifact_model.objects.latest("rendered_at")
    assert artifact.user_id == investor.pk
    assert artifact.actor_user_id == superadmin_user.pk
    assert artifact.metadata["download_subject_user_id"] == str(investor.pk)
    assert artifact.metadata["download_actor_user_id"] == str(superadmin_user.pk)


@pytest.mark.django_db
def test_investor_statement_download_is_self_scoped(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=1_500_00,
        value_date=date(2026, 3, 1),
        idempotency_key="portal-statement-own",
    )
    _declare_deposit(
        admin_user=admin_user,
        investor=other_investor,
        amount_minor=9_500_00,
        value_date=date(2026, 3, 1),
        idempotency_key="portal-statement-other",
    )

    artifact = download_investor_document(
        InvestorDocumentDownloadCommand(
            actor=investor,
            document_kind="account_statement",
            output_format="csv",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
    )

    assert artifact["content_type"].startswith("text/csv")
    assert cast(Any, investor).investor_reference in artifact["content"]
    assert "1500.00" in artifact["content"]
    assert cast(Any, other_investor).investor_reference not in artifact["content"]
    assert "9500.00" not in artifact["content"]
    assert "950000" not in artifact["content"]


def _receipt(investor: Model, *, key: str, topic: str, delivered: bool = True) -> None:
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    record_model = apps.get_model("communications", "EmailDeliveryRecord")
    email = cast(Any, investor).email
    outbox = outbox_model.objects.create(
        topic=topic,
        payload={"user_id": str(investor.pk), "email": email, "action": "withdrawal"},
        status="processed" if delivered else "pending",
        processed_at=timezone.now() if delivered else None,
        idempotency_key=f"portal-receipt-{key}",
    )
    if delivered:
        record_model.objects.create(
            outbox_message=outbox,
            topic=topic,
            template_key="auth.receipt.v1",
            recipient_email=email,
            subject="Your BANXUM confirmation code",
            body_text="Your code is 123456",
            body_html="Your code is 123456",
            provider="mock",
            provider_message_id=f"mock-receipt-{key}",
            status="sent",
            attempt_number=1,
            sent_at=timezone.now(),
        )


@pytest.mark.django_db
def test_notification_centre_leaves_out_sign_in_and_code_receipts(investor: Model) -> None:
    _approve_financial_access(investor)
    _outbox, notice = _delivered_notice(investor, key="deposit", topic="email.deposit_reconciled")
    # Sixty newer sign-in links and codes (investor and admin login codes share the code topic)
    # must not push the real notice off the default 50-item page.
    for index in range(30):
        _receipt(investor, key=f"link-{index}", topic="email.magic_link_requested")
        _receipt(investor, key=f"code-{index}", topic="email.sensitive_action_code_requested")
    _receipt(
        investor, key="queued-code", topic="email.sensitive_action_code_requested", delivered=False
    )
    client = Client()
    client.force_login(cast(Any, investor))

    listed = client.get("/api/v1/investor/portal/notifications/").json()

    assert [item["id"] for item in listed["notifications"]] == [str(notice.id)]
    assert listed["unread_count"] == 1
    assert "123456" not in str(listed)
    # A receipt cannot be marked read through the notification centre either.
    receipt_record = apps.get_model("communications", "EmailDeliveryRecord").objects.filter(
        topic="email.magic_link_requested"
    ).first()
    response = client.post(f"/api/v1/investor/portal/notifications/{receipt_record.id}/read/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_documents_list_only_closed_tax_years_and_refuses_open_ones(
    client: Client,
    investor: Model,
) -> None:
    # JOURNEY-16: tax information was generated for unfinished and future years.
    _approve_financial_access(investor)
    user = cast(Any, investor)
    user.date_joined = datetime(2023, 5, 2, 12, 0, tzinfo=business_timezone())
    user.save(update_fields=["date_joined"])
    today = business_date(now_utc())

    listing = get_investor_documents(actor=investor)
    tax_years = [
        item["period_end"].year
        for item in listing["documents"]
        if item["document_kind"] == "annual_tax_information"
    ]
    statements = {
        item["id"]: (item["period_start"], item["period_end"])
        for item in listing["documents"]
        if item["document_kind"] == "account_statement"
    }
    assert tax_years == list(range(today.year - 1, 2022, -1))
    assert all(year < today.year for year in tax_years)
    assert statements[f"statement-{today.year}"] == (date(today.year, 1, 1), today)
    assert statements[f"statement-{today.year - 1}"] == (
        date(today.year - 1, 1, 1),
        date(today.year - 1, 12, 31),
    )
    assert all(item["period_end"] <= today for item in listing["documents"] if "period_end" in item)

    for year in (today.year, today.year + 1):
        with pytest.raises(InvestorPortalValidationError, match="year that has ended"):
            download_investor_document(
                InvestorDocumentDownloadCommand(
                    actor=investor, document_kind="annual_tax_information", year=year
                )
            )
    client.force_login(user)
    response = client.post(
        "/api/v1/investor/portal/documents/download/",
        data={"document_kind": "annual_tax_information", "year": today.year + 1},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "year that has ended" in response.json()["detail"]
    response = client.post(
        "/api/v1/investor/portal/documents/download/",
        data={
            "document_kind": "account_statement",
            "start_date": date(today.year, 1, 1).isoformat(),
            "end_date": (today + timedelta(days=1)).isoformat(),
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "cannot end after today" in response.json()["detail"]


@pytest.mark.django_db
def test_notifications_show_human_labels_and_hide_delivery_internals(investor: Model) -> None:
    _approve_financial_access(investor)
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    record_model = apps.get_model("communications", "EmailDeliveryRecord")
    email = cast(Any, investor).email
    failed = outbox_model.objects.create(
        topic="email.withdrawal_status",
        payload={
            "user_id": str(investor.pk),
            "email": email,
            "subject": "Withdrawal requested: CHF 250.00",
            "body_text": "We received your request to withdraw CHF 250.00.",
        },
        status="pending",
        attempts=1,
        last_error="Provider secret SG.xyz rejected the request.",
        idempotency_key="portal-failed-notice",
    )
    record_model.objects.create(
        outbox_message=failed,
        topic="email.withdrawal_status",
        template_key="ledger.withdrawal_requested.v1",
        recipient_email=email,
        subject="Withdrawal requested: CHF 250.00",
        body_text="We received your request to withdraw CHF 250.00.",
        provider="twilio_email",
        provider_message_id="",
        status="failed",
        attempt_number=1,
        error="Provider secret SG.xyz rejected the request.",
    )
    queued = outbox_model.objects.create(
        topic="email.originator_subscription_activated",
        payload={
            "user_id": str(investor.pk),
            "email": email,
            "subject": "BANXUM investment activated: LO Main",
            "body_text": "Your CHF 1'000.00 subscription in LO Main is now active.",
        },
        status="pending",
        idempotency_key="portal-queued-lo-notice",
    )

    payload = get_investor_notifications(actor=investor)
    by_topic = {item["topic"]: item for item in payload["notifications"]}

    assert "SG.xyz" not in str(payload)
    assert "twilio" not in str(payload)
    for item in payload["notifications"]:
        assert "metadata" not in item
        assert "email." not in item["topic_label"]
    assert by_topic["email.withdrawal_status"]["topic_label"] == "Withdrawal"
    assert by_topic["email.withdrawal_status"]["status"] == "failed"
    activated = by_topic["email.originator_subscription_activated"]
    # A queued notice shows its own subject and content, not a title made from the topic key.
    assert activated["id"] == str(queued.id)
    assert activated["title"] == "BANXUM investment activated: LO Main"
    assert activated["body"] == "Your CHF 1'000.00 subscription in LO Main is now active."
    assert activated["topic_label"] == "Investment"


@pytest.mark.django_db
def test_notice_time_is_the_event_time_not_the_later_send_time(investor: Model) -> None:
    _approve_financial_access(investor)
    event_at = datetime(2026, 10, 9, 11, 47, tzinfo=UTC)
    clock = "backend.apps.platform_core.models.base.now_utc"
    with patch(clock, return_value=event_at):
        outbox = apps.get_model("platform_core", "OutboxMessage").objects.create(
            topic="email.deposit_reconciled",
            payload={"user_id": str(investor.pk), "email": cast(Any, investor).email},
            idempotency_key="portal-late-send",
        )
    # The scheduled dispatcher sent it the next day.
    with patch(clock, return_value=event_at + timedelta(days=1)):
        apps.get_model("communications", "EmailDeliveryRecord").objects.create(
            outbox_message=outbox,
            topic="email.deposit_reconciled",
            template_key="ledger.deposit_credited.v1",
            recipient_email=cast(Any, investor).email,
            subject="Deposit credited: CHF 1.00",
            body_text="We credited CHF 1.00.",
            provider="mock",
            status="sent",
            attempt_number=1,
        )

    item = get_investor_notifications(actor=investor)["notifications"][0]

    assert item["created_at"] == event_at


@pytest.mark.django_db
def test_loan_originator_repayment_notices_show_their_content(investor: Model) -> None:
    _approve_financial_access(investor)
    _delivered_notice(
        investor, key="lo-repayment", topic="email.originator_claim_repayment_credited"
    )

    item = get_investor_notifications(actor=investor)["notifications"][0]

    assert item["topic_label"] == "Repayment"
    assert item["body"] == "Notice body."
    assert item["navigation_target"] == "portfolio"


@pytest.mark.django_db
def test_notice_with_its_own_target_opens_that_page(investor: Model) -> None:
    _approve_financial_access(investor)
    notices = import_module("backend.apps.platform_core.services.investor_notices")
    holding_id = "22222222-2222-4222-8222-222222222222"
    notices.enqueue_investor_notice(
        notices.InvestorNotice(
            investor_user_id=str(investor.pk),
            topic="email.loan_funding_status",
            idempotency_key="portal-target",
            subject="Loan funded: Example",
            body_text="Example is funded.",
            template_key="marketplace.funding_closed.v1",
            navigation_target="holding",
            navigation_target_id=holding_id,
        )
    )
    notices.enqueue_investor_notice(
        notices.InvestorNotice(
            investor_user_id=str(investor.pk),
            topic="email.loan_funding_status",
            idempotency_key="portal-target-cancel",
            subject="Loan funding cancelled: Example",
            body_text="Funding for Example was cancelled.",
            template_key="marketplace.funding_cancelled.v1",
            navigation_target="balances",
        )
    )

    targets = {
        item["title"]: (item["navigation_target"], item["navigation_target_id"])
        for item in get_investor_notifications(actor=investor)["notifications"]
    }

    assert targets["Loan funded: Example"] == ("holding", holding_id)
    assert targets["Loan funding cancelled: Example"] == ("balances", "")


@pytest.mark.django_db
def test_notifications_redact_unknown_email_topics_by_default(investor: Model) -> None:
    _approve_financial_access(investor)
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    record_model = apps.get_model("communications", "EmailDeliveryRecord")
    outbox = outbox_model.objects.create(
        topic="email.future_sensitive_notice",
        payload={"user_id": str(investor.pk), "email": cast(Any, investor).email},
        status="processed",
        processed_at=timezone.now(),
        idempotency_key="portal-unknown-sensitive-email",
    )
    record_model.objects.create(
        outbox_message=outbox,
        topic="email.future_sensitive_notice",
        template_key="future.sensitive.v1",
        recipient_email=cast(Any, investor).email,
        subject="Sensitive future notice",
        body_text="Future sensitive value 123456",
        body_html="Future sensitive value 123456",
        provider="mock",
        provider_message_id="mock-unknown",
        status="sent",
        attempt_number=1,
        sent_at=timezone.now(),
    )

    payload = get_investor_notifications(actor=investor)

    assert payload["notifications"][0]["title"] == "Sensitive future notice"
    assert "123456" not in payload["notifications"][0]["body"]
    assert "not shown in the portal" in payload["notifications"][0]["body"]


@pytest.mark.django_db
def test_notifications_show_body_only_for_portal_safe_topics(investor: Model) -> None:
    _approve_financial_access(investor)
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    record_model = apps.get_model("communications", "EmailDeliveryRecord")
    outbox = outbox_model.objects.create(
        topic="email.investor_notice",
        payload={"user_id": str(investor.pk), "email": cast(Any, investor).email},
        status="processed",
        processed_at=timezone.now(),
        idempotency_key="portal-safe-email",
    )
    record_model.objects.create(
        outbox_message=outbox,
        topic="email.investor_notice",
        template_key="investor.notice.v1",
        recipient_email=cast(Any, investor).email,
        subject="Investor notice",
        body_text="Your repayment distribution has been credited.",
        body_html="Your repayment distribution has been credited.",
        provider="mock",
        provider_message_id="mock-safe",
        status="sent",
        attempt_number=1,
        sent_at=timezone.now(),
    )

    payload = get_investor_notifications(actor=investor)

    assert payload["notifications"][0]["title"] == "Investor notice"
    assert payload["notifications"][0]["body"] == "Your repayment distribution has been credited."


def _delivered_notice(
    investor: Model,
    *,
    key: str,
    topic: str = "email.investor_notice",
    payload_metadata: dict[str, Any] | None = None,
) -> tuple[Any, Any]:
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    record_model = apps.get_model("communications", "EmailDeliveryRecord")
    email = cast(Any, investor).email
    outbox = outbox_model.objects.create(
        topic=topic,
        payload={
            "user_id": str(investor.pk),
            "email": email,
            "metadata": payload_metadata or {},
        },
        status="processed",
        processed_at=timezone.now(),
        idempotency_key=f"portal-notice-{key}",
    )
    record = record_model.objects.create(
        outbox_message=outbox,
        topic=topic,
        template_key="investor.notice.v1",
        recipient_email=email,
        subject=f"Notice {key}",
        body_text="Notice body.",
        provider="mock",
        provider_message_id=f"mock-{key}",
        status="sent",
        attempt_number=1,
        sent_at=timezone.now(),
    )
    return outbox, record


@pytest.mark.django_db
def test_notifications_can_be_marked_read_one_by_one_and_all_at_once(
    investor: Model, other_investor: Model
) -> None:
    _approve_financial_access(investor)
    _approve_financial_access(other_investor)
    first_outbox, first_record = _delivered_notice(investor, key="first")
    _delivered_notice(investor, key="second")
    _delivered_notice(investor, key="code", topic="email.sensitive_action_code_requested")
    outbox_model = apps.get_model("platform_core", "OutboxMessage")
    queued = outbox_model.objects.create(
        topic="email.investor_notice",
        payload={"user_id": str(investor.pk), "email": cast(Any, investor).email},
        status="pending",
        idempotency_key="portal-notice-queued",
    )
    _other_outbox, other_record = _delivered_notice(other_investor, key="other")
    client = Client()
    client.force_login(cast(Any, investor))

    listed = client.get("/api/v1/investor/portal/notifications/").json()
    # Sign-in and confirmation-code receipts are neither listed nor counted as unread.
    assert listed["unread_count"] == 3
    unread_by_id = {item["id"]: item["unread"] for item in listed["notifications"]}
    assert unread_by_id[str(first_record.id)] is True
    assert unread_by_id[str(queued.id)] is True

    response = client.post(f"/api/v1/investor/portal/notifications/{first_record.id}/read/")
    assert response.status_code == 200
    assert response.json() == {"marked_count": 1, "unread_count": 2}
    # Idempotent: marking it again records nothing new.
    repeat = client.post(f"/api/v1/investor/portal/notifications/{first_record.id}/read/")
    assert repeat.json() == {"marked_count": 0, "unread_count": 2}
    receipt_model = apps.get_model("communications", "NotificationReadReceipt")
    assert receipt_model.objects.filter(outbox_message=first_outbox).count() == 1

    listed = client.get("/api/v1/investor/portal/notifications/").json()
    unread_by_id = {item["id"]: item["unread"] for item in listed["notifications"]}
    assert unread_by_id[str(first_record.id)] is False

    # A queued notice is marked by its outbox id and stays read once it is delivered.
    queued_response = client.post(f"/api/v1/investor/portal/notifications/{queued.id}/read/")
    assert queued_response.json()["unread_count"] == 1

    # Another investor's notification cannot be touched, by record id or outbox id.
    foreign = client.post(f"/api/v1/investor/portal/notifications/{other_record.id}/read/")
    assert foreign.status_code == 404
    foreign_outbox = client.post(
        f"/api/v1/investor/portal/notifications/{other_record.outbox_message_id}/read/"
    )
    assert foreign_outbox.status_code == 404
    assert (
        not receipt_model.objects.filter(investor_user_id=investor.pk)
        .exclude(outbox_message_id__in=[first_outbox.id, queued.id])
        .exists()
    )

    read_all = client.post("/api/v1/investor/portal/notifications/read-all/")
    assert read_all.status_code == 200
    assert read_all.json()["unread_count"] == 0
    assert client.post("/api/v1/investor/portal/notifications/read-all/").json() == {
        "marked_count": 0,
        "unread_count": 0,
    }
    # The other investor's notice is still unread for them.
    assert get_investor_notifications(actor=other_investor)["unread_count"] == 1


@pytest.mark.django_db
def test_notifications_expose_a_typed_navigation_target(investor: Model) -> None:
    _approve_financial_access(investor)
    loan_id = "11111111-1111-4111-8111-111111111111"
    holding_id = "22222222-2222-4222-8222-222222222222"
    _delivered_notice(
        investor,
        key="repayment",
        topic="email.repayment_distribution_credited",
        payload_metadata={"loan_id": loan_id, "holding_ids": [holding_id]},
    )
    _delivered_notice(
        investor,
        key="ageing",
        topic="email.balance_ageing_reminder",
        payload_metadata={"balance_lot_id": "33333333-3333-4333-8333-333333333333"},
    )
    _delivered_notice(
        investor,
        key="status",
        topic="email.loan_status_changed",
        payload_metadata={"loan_id": loan_id},
    )
    _delivered_notice(
        investor,
        key="unsafe",
        topic="email.loan_risk_note_published",
        payload_metadata={"loan_id": "../../admin"},
    )

    payload = get_investor_notifications(actor=investor)
    targets = {
        item["topic"]: (item["navigation_target"], item["navigation_target_id"])
        for item in payload["notifications"]
    }

    assert targets["email.repayment_distribution_credited"] == ("holding", holding_id)
    assert targets["email.balance_ageing_reminder"] == ("balances", "")
    assert targets["email.loan_status_changed"] == ("loan", loan_id)
    assert targets["email.loan_risk_note_published"] == ("none", "")


@pytest.mark.django_db
def test_notification_read_requires_the_investor_session(
    investor: Model, superadmin_user: Model
) -> None:
    _approve_financial_access(investor)
    _outbox, record = _delivered_notice(investor, key="session")
    client = Client()
    client.force_login(cast(Any, superadmin_user))

    token_payload = issue_readonly_impersonation_token(
        actor=superadmin_user,
        target_user_id=str(investor.pk),
    )

    response = client.post(
        f"/api/v1/investor/portal/notifications/{record.id}/read/",
        HTTP_X_BANXUM_IMPERSONATE=token_payload["token"],
    )
    read_all = client.post(
        "/api/v1/investor/portal/notifications/read-all/",
        HTTP_X_BANXUM_IMPERSONATE=token_payload["token"],
    )

    # A read-only view never changes the investor's read state.
    assert response.status_code == 403
    assert read_all.status_code == 403
    receipt_model = apps.get_model("communications", "NotificationReadReceipt")
    assert not receipt_model.objects.exists()


@pytest.mark.django_db
def test_activity_labels_withdrawal_outcomes_and_shows_the_cancellation_credit(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    ledger_services = import_module("backend.apps.ledger.services")
    factories = import_module("backend.apps.platform_core.tests.factories")
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=1_000_00,
        value_date=date(2026, 3, 1),
        idempotency_key="portal-withdrawal-deposit",
    )
    # The deposit's source IBAN (CH93...) is the verified payout account.

    def request(amount_minor: int, key: str) -> Any:
        code = factories.issue_sensitive_action_test_code(investor, "withdrawal")
        return ledger_services.request_investor_withdrawal(
            ledger_services.RequestInvestorWithdrawalCommand(
                actor=investor,
                amount_minor=amount_minor,
                currency="CHF",
                destination_iban="CH9300762011623852957",
                destination_account_name="Portal Investor",
                idempotency_key=key,
                sensitive_action_code_id=code.code_id,
                sensitive_action_code=code.raw_code,
            )
        )

    cancelled = request(100_00, "portal-withdrawal-cancelled")
    ledger_services.cancel_investor_withdrawal(
        ledger_services.CancelInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(cancelled.id),
            reason="Investor asked to stop the payout.",
            idempotency_key="portal-withdrawal-cancel",
        )
    )
    finalized = request(200_00, "portal-withdrawal-finalized")
    ledger_services.finalize_investor_withdrawal(
        ledger_services.FinalizeInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(finalized.id),
            booking_date=date(2026, 3, 2),
            value_date=date(2026, 3, 2),
            collection_account_identifier="CHF-COLLECTION",
            bank_reference="BANK-PORTAL-WITHDRAWAL",
            idempotency_key="portal-withdrawal-finalize",
        )
    )
    pending = request(50_00, "portal-withdrawal-pending")

    entries = get_investor_activity(actor=investor, limit=50)["entries"]
    by_id = {entry["id"]: entry for entry in entries}

    assert by_id[str(cancelled.id)]["status"] == "cancelled"
    assert by_id[str(finalized.id)]["status"] == "finalized"
    assert by_id[str(pending.id)]["status"] == "requested"
    reversal = by_id[f"{cancelled.id}:cancellation"]
    assert reversal["activity_type"] == "withdrawal_cancellation"
    assert reversal["direction"] == "in"
    assert reversal["amount_minor"] == 100_00
    assert reversal["status"] == "returned"
    assert reversal["metadata"]["withdrawal_request_id"] == str(cancelled.id)
    assert not any(
        entry["id"] in {f"{finalized.id}:cancellation", f"{pending.id}:cancellation"}
        for entry in entries
    )


@pytest.mark.django_db
def test_balance_summary_reports_penalty_charged_apart_from_frozen_balance(
    admin_user: Model,
    investor: Model,
) -> None:
    _approve_financial_access(investor)
    penalty_lot = _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=5_000_00,
        value_date=date(2026, 1, 2),
        idempotency_key="portal-penalty-split",
    )
    lot = cast(Any, penalty_lot)
    lot.status = "penalty_mode"
    lot.available_amount_minor = 4_900_00
    lot.penalized_amount_minor = 100_00
    lot.save(update_fields=["status", "available_amount_minor", "penalized_amount_minor"])

    payload = get_investor_balances(actor=investor, as_of=_at(date(2026, 3, 5)))
    chf = next(item for item in payload["summaries"] if item["currency"] == "CHF")

    # The blocked balance excludes the penalty already taken; the penalty is reported apart.
    assert chf["penalty_mode_minor"] == 4_900_00
    assert chf["penalty_charged_minor"] == 100_00
    assert payload["lots"][0]["penalized_amount_minor"] == 100_00


@pytest.mark.django_db
def test_activity_shows_penalty_charges_and_labels_forced_returns(
    admin_user: Model,
    investor: Model,
    other_investor: Model,
) -> None:
    _approve_financial_access(investor)
    ledger_services = import_module("backend.apps.ledger.services")
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=1_000_00,
        value_date=date(2026, 1, 1),
        idempotency_key="portal-forced-deposit",
    )
    penalty_lot = _declare_deposit(
        admin_user=admin_user,
        investor=other_investor,
        amount_minor=2_000_00,
        value_date=date(2026, 1, 1),
        idempotency_key="portal-penalty-deposit",
    )
    # The other investor's only IBAN is revoked, so day 61 means penalty mode.
    for instruction in apps.get_model("ledger", "InvestorPayoutInstruction").objects.filter(
        investor_user_id=other_investor.pk
    ):
        ledger_services.revoke_investor_payout_instruction(
            ledger_services.RevokeInvestorPayoutInstructionCommand(
                actor=admin_user,
                instruction_id=str(instruction.pk),
                reason="Returned by the bank.",
            )
        )
    scan = ledger_services.run_balance_ageing_scan(
        ledger_services.RunBalanceAgeingScanCommand(actor=admin_user, as_of=_at(date(2026, 3, 3)))
    )
    forced = scan.forced_withdrawal_requests[0]

    entries = get_investor_activity(actor=investor, limit=50)["entries"]
    forced_entry = next(entry for entry in entries if entry["id"] == str(forced.id))
    assert forced_entry["title"] == "Forced return to your bank account"
    assert forced_entry["metadata"]["is_forced"] is True
    assert forced_entry["metadata"]["destination_iban"] == "CH9300762011623852957"

    _approve_financial_access(other_investor)
    other_entries = get_investor_activity(actor=other_investor, limit=50)["entries"]
    penalties = [e for e in other_entries if e["activity_type"] == "balance_penalty_charge"]
    assert len(penalties) == 1
    assert penalties[0]["direction"] == "out"
    assert penalties[0]["amount_minor"] == 20_00
    assert penalties[0]["currency"] == "CHF"
    assert penalties[0]["metadata"]["balance_lot_id"] == str(penalty_lot.pk)


@pytest.mark.django_db
def test_balances_list_pending_withdrawals_with_forced_returns_and_the_daily_penalty(
    admin_user: Model,
    investor: Model,
    settings: Any,
) -> None:
    # Audit A-21/A-20: the Account page needs the open withdrawal requests (forced returns
    # labelled) and the daily penalty rate for the penalty-mode banner.
    settings.BALANCE_PENALTY_BPS_PER_DAY = 100
    _approve_financial_access(investor)
    ledger_services = import_module("backend.apps.ledger.services")
    factories = import_module("backend.apps.platform_core.tests.factories")
    _declare_deposit(
        admin_user=admin_user,
        investor=investor,
        amount_minor=1_000_00,
        value_date=date(2026, 3, 1),
        idempotency_key="portal-pending-deposit",
    )

    def request(amount_minor: int, key: str) -> Any:
        code = factories.issue_sensitive_action_test_code(investor, "withdrawal")
        return ledger_services.request_investor_withdrawal(
            ledger_services.RequestInvestorWithdrawalCommand(
                actor=investor,
                amount_minor=amount_minor,
                currency="CHF",
                destination_iban="CH9300762011623852957",
                destination_account_name="Portal Investor",
                idempotency_key=key,
                sensitive_action_code_id=code.code_id,
                sensitive_action_code=code.raw_code,
            )
        )

    pending = request(150_00, "portal-pending-open")
    finished = request(50_00, "portal-pending-finalized")
    ledger_services.finalize_investor_withdrawal(
        ledger_services.FinalizeInvestorWithdrawalCommand(
            actor=admin_user,
            withdrawal_request_id=str(finished.id),
            booking_date=date(2026, 3, 2),
            value_date=date(2026, 3, 2),
            collection_account_identifier="CHF-COLLECTION",
            bank_reference="BANK-PORTAL-PENDING",
            idempotency_key="portal-pending-finalize",
        )
    )
    forced = request(25_00, "portal-pending-forced")
    withdrawal_model = apps.get_model("ledger", "InvestorWithdrawalRequest")
    withdrawal_model.objects.filter(pk=forced.id).update(is_forced=True)

    payload = get_investor_balances(actor=investor)

    assert payload["penalty_bps_per_day"] == 100
    rows = payload["pending_withdrawals"]
    assert [row["id"] for row in rows] == [str(pending.id), str(forced.id)]
    assert rows[0]["amount_minor"] == 150_00
    assert rows[0]["currency"] == "CHF"
    assert rows[0]["destination_iban"] == "CH9300762011623852957"
    assert rows[0]["is_forced"] is False
    assert rows[1]["is_forced"] is True

    client = Client()
    client.force_login(cast(Any, investor))
    response = client.get("/api/v1/investor/portal/balances/")
    assert response.status_code == 200
    assert response.json()["pending_withdrawals"][1]["is_forced"] is True
    assert response.json()["penalty_bps_per_day"] == 100


@pytest.mark.django_db
def test_fx_history_carries_the_daily_limit_and_quote_lock_from_settings(investor: Model) -> None:
    # Audit A-64: the FX page showed a hard-coded "CHF 100,000" limit and "60 seconds".
    _approve_financial_access(investor)
    set_platform_setting(
        SetPlatformSettingCommand(
            actor=ActorRef.system(),
            key="fx.daily_limit_chf_minor",
            value=25_000_00,
        )
    )
    client = Client()
    client.force_login(cast(Any, investor))

    response = client.get("/api/v1/investor/portal/fx/")

    assert response.status_code == 200
    terms = response.json()["terms"]
    assert terms["daily_limit_chf_minor"] == 25_000_00
    assert terms["daily_limit_used_chf_minor"] == 0
    assert terms["quote_ttl_seconds"] == 60
    assert terms["platform_fee_bps"] >= 0
