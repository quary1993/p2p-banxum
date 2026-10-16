# IP of Webby-Soft SRL.
"""Public site API: projects, statistics and Loan Originators (owner decision 2026-10-15)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.db.models import Model
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from backend.apps.marketplace_primary.api.views import (
    PublicOriginatorListView,
    PublicProjectDetailView,
    PublicProjectListView,
    PublicStatisticsView,
)
from backend.apps.marketplace_primary.public_site import public_country_code
from backend.apps.marketplace_primary.tests.test_primary_marketplace import (
    _approve_financial_access,
    _create_and_allocate_order,
    _create_originator_batch_loan,
    _create_published_loan,
    _declare_deposit,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import Currency

PROJECTS_URL = "/api/v1/marketplace/primary/public/projects/"
STATISTICS_URL = "/api/v1/marketplace/primary/public/statistics/"
ORIGINATORS_URL = "/api/v1/marketplace/primary/public/originators/"

PUBLIC_PROJECT_FIELDS = {
    "loan_id",
    "title",
    "product_type",
    "is_refinancing",
    "public_status",
    "currency",
    "principal_minor",
    "committed_principal_minor",
    "remaining_capacity_minor",
    "minimum_investment_minor",
    "investors_count",
    "max_investors",
    "places_left",
    "interest_rate_bps",
    "term_months",
    "repayment_type",
    "risk_rating",
    "collateral_type",
    "collateral_description",
    "ltv_bps",
    "purpose",
    "purpose_description",
    "investor_summary",
    "borrower_country",
    "borrower_sector",
    "borrower_year_founded",
    "originator",
    "published_at",
    "funding_deadline",
    "funded_at",
    "record",
}
RECORD_FIELDS = {
    "installments_total",
    "installments_paid",
    "principal_repaid_minor",
    "interest_paid_minor",
    "outstanding_principal_minor",
    "days_past_due",
    "defaulted_on",
    "public_note",
}
BORROWER_LEGAL_NAME = "Marketplace Borrower AG"


@pytest.fixture(autouse=True)
def _clear_public_site_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="public-site-admin@example.test",
            password="AdminPass123!",
            full_name="Public Site Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


def _lender(email: str) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name="Public Site Lender",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


@pytest.fixture
def investor() -> Model:
    return _lender("public-site-investor@example.test")


def _today() -> date:
    return business_date(timezone.now())


def _project(client: Client, loan: Model) -> dict[str, Any]:
    response = client.get(f"{PROJECTS_URL}{loan.pk}/")
    assert response.status_code == 200, response.content
    return cast(dict[str, Any], response.json())


def _funded_direct_loan(
    admin_user: Model,
    *,
    status: str,
    principal_minor: int,
    installments: list[tuple[date, int, int]],
    holders: list[Model],
    currency_code: str = "CHF",
    interest_rate_bps: int = 1000,
    loan_start_date: date | None = None,
    country: str = "CH",
) -> Any:
    """A published Direct loan after its funding close, with schedule and holdings."""
    loan = cast(Any, _create_published_loan(admin_user, currency_code=currency_code))
    start = loan_start_date or _today() - timedelta(days=40)
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=loan.pk).update(
        status=status,
        principal_minor=principal_minor,
        original_principal_minor=principal_minor,
        committed_principal_minor=principal_minor,
        interest_rate_bps=interest_rate_bps,
        loan_start_date=start,
        funding_deadline=start,
        first_payment_date=installments[0][0],
        term_months=len(installments),
        total_scheduled_principal_minor=principal_minor,
        total_scheduled_interest_minor=sum(row[2] for row in installments),
    )
    borrower_model = apps.get_model("entities", "BorrowerEntity")
    borrower_model.objects.filter(pk=loan.borrower_id).update(country=country)
    installment_model = apps.get_model("loans", "LoanInstallment")
    for number, (due_date, principal, interest) in enumerate(installments, start=1):
        installment_model.objects.create(
            loan_id=loan.pk,
            schedule_version=1,
            installment_number=number,
            due_date=due_date,
            principal_minor=principal,
            interest_minor=interest,
            total_minor=principal + interest,
        )
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    share = principal_minor // len(holders)
    for index, holder in enumerate(holders):
        amount = share if index < len(holders) - 1 else principal_minor - share * index
        holding_model.objects.create(
            loan_id=loan.pk,
            investor_user_id=holder.pk,
            source_type="primary_market",
            source_id=f"public-site-order-{loan.pk}-{index}",
            status="active",
            original_principal_minor=amount,
            current_principal_minor=amount,
            currency=Currency.objects.get(code=currency_code),
            loan_share_ppm=1_000_000 * amount // principal_minor,
            assignment_effective_at=timezone.now(),
            created_by_admin_id=admin_user.pk,
            idempotency_key=f"public-site-holding-{loan.pk}-{index}",
        )
    loan.refresh_from_db()
    return loan


def _record_installment_payment(
    admin_user: Model, loan: Any, *, amount_minor: int, on: date
) -> None:
    servicing = import_module("backend.apps.servicing.services")
    servicing.record_borrower_repayment(
        servicing.RecordBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=amount_minor,
            booking_date=on,
            value_date=on,
            collection_account_identifier="CH00GARANTAPUBLIC",
            payer_name="Borrower",
            payer_account_identifier="CH22BORROWER",
            bank_reference=f"BANK-{loan.pk}",
            payment_reference=f"LOAN-{loan.pk}",
            evidence_reference=f"statement:{loan.pk}",
            idempotency_key=f"public-site-repayment-{loan.pk}",
        )
    )


def _create_par_subscription_loan(admin_user: Model, *, suffix: str) -> Any:
    services = import_module("backend.apps.originator_claims.services")
    today = _today()
    boundary_due = today + timedelta(days=10)
    second_due = boundary_due + timedelta(days=30)
    final_due = second_due + timedelta(days=30)
    csv_content = "\n".join(
        [
            (
                "row_type,reference,installment_number,accrual_start_date,due_date,value_date,"
                "payment_type,opening_principal_minor,principal_minor,interest_minor,"
                "penalty_minor,fee_minor,total_minor,closing_principal_minor,"
                "resulting_principal_minor"
            ),
            (
                f"schedule,,1,{(today - timedelta(days=20)).isoformat()},"
                f"{boundary_due.isoformat()},,,1000000,200000,10000,2000,0,212000,800000,"
            ),
            (
                f"schedule,,2,{boundary_due.isoformat()},{second_due.isoformat()},,,800000,"
                "400000,100000,40000,0,540000,400000,"
            ),
            (
                f"schedule,,3,{second_due.isoformat()},{final_due.isoformat()},,,400000,"
                "400000,50000,20000,0,470000,0,"
            ),
        ]
    )
    originator = services.create_loan_originator(
        services.CreateLoanOriginatorCommand(
            actor=admin_user,
            legal_name=f"Public Originator {suffix} Holding AG",
            public_name=f"Public Originator {suffix}",
            registration_number=f"CHE-PUBLIC-{suffix}",
            jurisdiction="Switzerland",
            registered_address="Zurich, Switzerland",
            settlement_account_name=f"Public Originator {suffix} AG",
            settlement_iban="CH9300762011623852957",
            kyb_evidence_reference=f"KYB-PUBLIC-{suffix}",
            status="active",
        )
    )
    result = services.create_originator_loan(
        services.CreateOriginatorLoanCommand(
            actor=admin_user,
            originator_id=str(originator.id),
            title=f"Workshop machines {suffix}",
            investor_summary="Par subscription with component participation.",
            purpose="working_capital",
            purpose_description="Working capital",
            currency="CHF",
            original_principal_minor=1_000_000,
            interest_rate_bps=1_200,
            distribution_model="par_component_v2",
            minimum_investment_minor=100_000,
            repayment_type="equal_installments",
            interest_only_months=0,
            collateral_type="receivables",
            collateral_value_minor=1_500_000,
            collateral_description="Assigned receivables",
            risk_rating="BBB",
            csv_content=f"{csv_content}\n",
            source_filename=f"public-{suffix}.csv",
            as_of_date=today,
            borrower_snapshot={
                "borrower_legal_name": f"Secret Claim Borrower {suffix} SRL",
                "borrower_display_name": f"Hidden display borrower {suffix}",
                "country": "Romania",
                "year_founded": 2004,
                "business_classification": "Hospitality",
                "business_classification_public": True,
            },
            funding_deadline=today + timedelta(days=5),
            entitlement_start_date=boundary_due,
            activation_outstanding_principal_minor=800_000,
            investor_interest_participation_bps=7_000,
            investor_penalty_participation_bps=5_000,
        )
    )
    services.publish_originator_loan(
        services.PublishOriginatorLoanCommand(
            actor=admin_user,
            loan_id=str(result.loan.id),
            as_of_date=today,
        )
    )
    return result


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("loan_status", "expected"),
    [
        ("draft", None),
        ("cancelled", None),
        ("funding_close_failed", None),
        ("published", "open"),
        ("funded", "repaying"),
        ("active", "repaying"),
        ("late", "late"),
        ("defaulted", "default"),
        ("written_off", "default"),
        ("repaid", "repaid"),
    ],
)
def test_public_status_maps_every_loan_status(
    client: Client,
    admin_user: Model,
    loan_status: str,
    expected: str | None,
) -> None:
    loan = cast(Any, _create_published_loan(admin_user))
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=loan.pk).update(status=loan_status)

    rows = client.get(PROJECTS_URL).json()
    detail = client.get(f"{PROJECTS_URL}{loan.pk}/")

    if expected is None:
        assert rows == []
        assert detail.status_code == 404
        return
    assert [row["public_status"] for row in rows] == [expected]
    assert detail.status_code == 200
    payload = detail.json()
    assert payload == rows[0]
    assert payload["public_status"] == expected
    if expected == "open":
        assert payload["record"] is None
        assert payload["funded_at"] is None
    else:
        assert set(payload["record"]) == RECORD_FIELDS
        assert payload["remaining_capacity_minor"] == 0
        assert payload["minimum_investment_minor"] is None
        assert payload["committed_principal_minor"] == payload["principal_minor"]
        assert payload["funded_at"] == loan.loan_start_date.isoformat()


@pytest.mark.django_db
def test_fully_subscribed_round_is_fully_funded_and_past_deadline_round_is_hidden(
    client: Client,
    admin_user: Model,
) -> None:
    full = cast(Any, _create_published_loan(admin_user))
    expired = cast(Any, _create_published_loan(admin_user))
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=full.pk).update(committed_principal_minor=full.principal_minor)
    loan_model.objects.filter(pk=expired.pk).update(funding_deadline=_today() - timedelta(days=1))

    rows = client.get(PROJECTS_URL).json()

    assert [(row["loan_id"], row["public_status"]) for row in rows] == [
        (str(full.pk), "fully_funded")
    ]
    assert rows[0]["committed_principal_minor"] == full.principal_minor
    assert rows[0]["remaining_capacity_minor"] == 0
    assert rows[0]["minimum_investment_minor"] is None
    assert rows[0]["record"] is None
    # Waiting for the expiry resolution: not open, not fully funded, so not shown.
    assert client.get(f"{PROJECTS_URL}{expired.pk}/").status_code == 404


@pytest.mark.django_db
def test_public_project_has_the_contract_fields_and_never_the_borrower_identity(
    client: Client,
    admin_user: Model,
) -> None:
    loan = cast(Any, _create_published_loan(admin_user))
    borrower = loan.borrower
    borrower.registration_number = "CHE-111.222.333"
    borrower.registered_address = "Seestrasse 99, 8002 Zurich"
    borrower.registered_address_public = True
    borrower.contact_info = "cfo@borrower.example.test"
    borrower.contact_info_public = True
    borrower.business_classification = "Residential real estate"
    borrower.business_classification_public = False
    borrower.save()

    response = client.get(PROJECTS_URL)

    assert response.status_code == 200
    [row] = response.json()
    assert set(row) == PUBLIC_PROJECT_FIELDS
    body = response.content.decode()
    for hidden in (
        BORROWER_LEGAL_NAME,
        "CHE-111.222.333",
        "Seestrasse",
        "cfo@borrower",
        "Residential real estate",
        "borrower_name",
        "borrower_id",
        "documents",
    ):
        assert hidden not in body
    assert row["title"] == "Real estate bridge loan"
    assert row["product_type"] == "direct"
    assert row["public_status"] == "open"
    assert row["currency"] == "CHF"
    assert row["interest_rate_bps"] == 1000
    assert row["term_months"] == 12
    assert row["repayment_type"] == "equal_installments"
    assert row["risk_rating"] == "BBB"
    assert row["collateral_type"] == "real_estate"
    assert row["ltv_bps"] == 6667
    assert row["purpose"] == "bridge_financing"
    assert row["investor_summary"] == "Short real-estate backed bridge facility."
    assert row["borrower_country"] == "CH"
    assert row["borrower_sector"] == ""
    assert row["borrower_year_founded"] == 2010
    assert row["originator"] is None
    assert row["funding_deadline"] == loan.funding_deadline.isoformat()
    assert row["published_at"] is not None

    # The sector is published only when the admin marked it public.
    borrower.business_classification_public = True
    borrower.save(update_fields=["business_classification_public"])
    cache.clear()
    assert _project(client, loan)["borrower_sector"] == "Residential real estate"


@pytest.mark.django_db
def test_open_loan_reports_investors_remaining_capacity_and_minimum(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    # Not a Swiss borrower: no investor limit (MKT-DEC-028 has its own tests).
    loan = cast(
        Any,
        _create_published_loan(admin_user, principal_minor=100_000_00, borrower_country="DE"),
    )
    _approve_financial_access(investor)
    _declare_deposit(admin_user, investor, amount_minor=20_000_00, idempotency_key="public-dep")
    _create_and_allocate_order(
        investor=investor,
        loan=loan,
        amount_minor=20_000_00,
        idempotency_prefix="public-site-order",
    )

    payload = _project(client, loan)

    assert payload["public_status"] == "open"
    assert payload["principal_minor"] == 100_000_00
    assert payload["committed_principal_minor"] == 20_000_00
    assert payload["remaining_capacity_minor"] == 80_000_00
    # The launch minimum (platform setting, CHF 1,000.00 by default).
    assert payload["minimum_investment_minor"] == 1_000_00
    assert payload["investors_count"] == 1
    assert payload["max_investors"] is None
    assert payload["places_left"] is None

    # Less than the minimum left: the minimum is what is left.
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=loan.pk).update(committed_principal_minor=100_000_00 - 400_00)
    cache.clear()
    payload = _project(client, loan)
    assert payload["remaining_capacity_minor"] == 400_00
    assert payload["minimum_investment_minor"] == 400_00


@pytest.mark.django_db
def test_record_of_a_repaying_loan_with_one_paid_installment(
    client: Client,
    admin_user: Model,
) -> None:
    today = _today()
    holders = [_lender("public-holder-1@example.test"), _lender("public-holder-2@example.test")]
    loan = _funded_direct_loan(
        admin_user,
        status="active",
        principal_minor=30_000_00,
        installments=[
            (today - timedelta(days=10), 3_000_00, 300_00),
            (today + timedelta(days=20), 27_000_00, 200_00),
        ],
        holders=holders,
    )
    _record_installment_payment(
        admin_user, loan, amount_minor=3_300_00, on=today - timedelta(days=10)
    )
    servicing = import_module("backend.apps.servicing.services")
    servicing.add_loan_risk_note(
        servicing.AddLoanRiskNoteCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            visibility="public",
            note_type="public_update",
            body="The borrower paid the first installment on time.",
            idempotency_key="public-site-note-1",
        )
    )
    servicing.add_loan_risk_note(
        servicing.AddLoanRiskNoteCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            visibility="internal",
            note_type="internal_note",
            body="Internal follow-up only.",
            idempotency_key="public-site-note-2",
        )
    )

    payload = _project(client, loan)

    assert payload["public_status"] == "repaying"
    assert payload["principal_minor"] == 30_000_00
    assert payload["committed_principal_minor"] == 30_000_00
    assert payload["investors_count"] == 2
    assert payload["funded_at"] == loan.loan_start_date.isoformat()
    assert payload["record"] == {
        "installments_total": 2,
        "installments_paid": 1,
        "principal_repaid_minor": 3_000_00,
        "interest_paid_minor": 300_00,
        "outstanding_principal_minor": 27_000_00,
        "days_past_due": 0,
        "defaulted_on": None,
        "public_note": "The borrower paid the first installment on time.",
    }
    assert "Internal follow-up" not in client.get(PROJECTS_URL).content.decode()


@pytest.mark.django_db
def test_record_of_a_late_and_a_defaulted_loan(client: Client, admin_user: Model) -> None:
    today = _today()
    late = _funded_direct_loan(
        admin_user,
        status="late",
        principal_minor=20_000_00,
        installments=[
            (today - timedelta(days=12), 10_000_00, 150_00),
            (today + timedelta(days=18), 10_000_00, 75_00),
        ],
        holders=[_lender("public-late@example.test")],
    )
    defaulted = _funded_direct_loan(
        admin_user,
        status="defaulted",
        principal_minor=10_000_00,
        installments=[(today - timedelta(days=40), 10_000_00, 100_00)],
        holders=[_lender("public-default@example.test")],
    )
    apps.get_model("loans", "LoanEvent").objects.create(
        loan_id=defaulted.pk,
        event_type="servicing_status_changed",
        actor_user_id=admin_user.pk,
        actor_account_type="admin",
        previous_status="late",
        new_status="defaulted",
        metadata={"as_of_date": (today - timedelta(days=24)).isoformat()},
    )

    late_record = _project(client, late)["record"]
    default_payload = _project(client, defaulted)

    assert late_record["days_past_due"] == 12
    assert late_record["installments_paid"] == 0
    assert late_record["installments_total"] == 2
    assert late_record["outstanding_principal_minor"] == 20_000_00
    assert late_record["defaulted_on"] is None
    assert default_payload["public_status"] == "default"
    assert default_payload["record"]["days_past_due"] == 40
    assert default_payload["record"]["defaulted_on"] == (today - timedelta(days=24)).isoformat()
    assert default_payload["record"]["outstanding_principal_minor"] == 10_000_00


@pytest.mark.django_db
def test_statistics_totals_per_currency_and_weighted_average(
    client: Client,
    admin_user: Model,
) -> None:
    today = _today()
    chf = _funded_direct_loan(
        admin_user,
        status="active",
        principal_minor=10_000_00,
        installments=[
            (today - timedelta(days=5), 1_000_00, 100_00),
            (today + timedelta(days=25), 9_000_00, 50_00),
        ],
        holders=[_lender("public-stats-1@example.test")],
        interest_rate_bps=1000,
        country="Switzerland",
    )
    _record_installment_payment(
        admin_user, chf, amount_minor=1_100_00, on=today - timedelta(days=5)
    )
    _funded_direct_loan(
        admin_user,
        status="defaulted",
        principal_minor=10_000_00,
        installments=[(today - timedelta(days=30), 10_000_00, 100_00)],
        holders=[_lender("public-stats-2@example.test")],
        currency_code="EUR",
        interest_rate_bps=1002,
        country="Germany",
    )
    _funded_direct_loan(
        admin_user,
        status="late",
        principal_minor=20_000_00,
        installments=[(today - timedelta(days=7), 20_000_00, 300_00)],
        holders=[_lender("public-stats-3@example.test")],
        currency_code="EUR",
        interest_rate_bps=1000,
        country="AT",
    )
    # Open loans are public projects but not funded loans.
    open_loan = cast(Any, _create_published_loan(admin_user, principal_minor=50_000_00))
    apps.get_model("loans", "Loan").objects.filter(pk=open_loan.pk).update(interest_rate_bps=1500)

    response = client.get(STATISTICS_URL)

    assert response.status_code == 200
    stats = response.json()
    assert stats["loans_funded"] == 3
    assert stats["loans_repaid"] == 0
    assert stats["loans_late"] == 1
    assert stats["loans_defaulted"] == 1
    # (1000 x 10,000 + 1002 x 10,000 + 1000 x 20,000) / 40,000 = 1000.5, rounded half up.
    assert stats["average_interest_rate_bps"] == 1001
    assert stats["countries_count"] == 3
    assert stats["originators_count"] == 0
    assert stats["as_of"]
    assert stats["by_currency"] == [
        {
            "currency": "CHF",
            "loans": 1,
            "lent_minor": 10_000_00,
            "principal_repaid_minor": 1_000_00,
            "interest_paid_minor": 100_00,
            "outstanding_minor": 9_000_00,
            "defaulted_minor": 0,
        },
        {
            "currency": "EUR",
            "loans": 2,
            "lent_minor": 30_000_00,
            "principal_repaid_minor": 0,
            "interest_paid_minor": 0,
            "outstanding_minor": 20_000_00,
            "defaulted_minor": 10_000_00,
        },
    ]


@pytest.mark.django_db
def test_statistics_without_funded_loans_keep_both_currency_rows(client: Client) -> None:
    stats = client.get(STATISTICS_URL).json()

    assert stats["loans_funded"] == 0
    assert stats["average_interest_rate_bps"] is None
    assert [row["currency"] for row in stats["by_currency"]] == ["CHF", "EUR"]
    assert all(row["lent_minor"] == 0 for row in stats["by_currency"])


@pytest.mark.django_db
def test_loan_originator_claims_and_originators_list(
    client: Client,
    admin_user: Model,
) -> None:
    subscription = _create_par_subscription_loan(admin_user, suffix="OPEN")
    legacy_loan = cast(Any, _create_originator_batch_loan(admin_user, suffix="LEGACY"))
    blocked = _create_par_subscription_loan(admin_user, suffix="BLOCKED")
    apps.get_model("originator_claims", "LoanOriginator").objects.filter(
        pk=blocked.profile.originator_id
    ).update(status="blocked")

    response = client.get(PROJECTS_URL)
    rows = {row["loan_id"]: row for row in response.json()}
    body = response.content.decode()

    open_claim = rows[str(subscription.loan.id)]
    assert open_claim["product_type"] == "originator_claim"
    assert open_claim["public_status"] == "open"
    # Coupon 12.00% x 70% investor interest participation, as the investor marketplace.
    assert open_claim["interest_rate_bps"] == 840
    assert open_claim["principal_minor"] == 800_000
    assert open_claim["committed_principal_minor"] == 0
    assert open_claim["remaining_capacity_minor"] == 800_000
    assert open_claim["minimum_investment_minor"] == 100_000
    assert open_claim["borrower_country"] == "RO"
    assert open_claim["borrower_sector"] == "Hospitality"
    assert open_claim["borrower_year_founded"] == 2004
    assert open_claim["originator"] == {
        "id": str(subscription.profile.originator_id),
        "name": "Public Originator OPEN",
        "country": "CH",
    }
    assert open_claim["funding_deadline"] == (_today() + timedelta(days=5)).isoformat()
    # A blocked originator's round is not open on the investor marketplace either.
    assert str(blocked.loan.id) not in rows
    # Historical quoted claims are sold out of an active loan: shown as repaying.
    legacy = rows[str(legacy_loan.pk)]
    assert legacy["public_status"] == "repaying"
    assert legacy["interest_rate_bps"] == 800
    assert legacy["record"]["installments_total"] == 2
    assert legacy["record"]["installments_paid"] == 0
    for hidden in (
        "Secret Claim Borrower",
        "Hidden display borrower",
        "Confidential Batch Borrower",
        "Batch borrower LEGACY",
        "Holding AG",
    ):
        assert hidden not in body

    originators = client.get(ORIGINATORS_URL).json()
    assert originators == sorted(originators, key=lambda row: row["name"].casefold())
    by_name = {row["name"]: row for row in originators}
    assert set(by_name) == {"Public Originator OPEN", "Batch Originator LEGACY"}
    assert by_name["Public Originator OPEN"] == {
        "id": str(subscription.profile.originator_id),
        "name": "Public Originator OPEN",
        "country": "CH",
        "partner_since": _today().isoformat(),
        "claims_funded": 0,
    }
    assert by_name["Batch Originator LEGACY"]["claims_funded"] == 1
    assert client.get(STATISTICS_URL).json()["originators_count"] == 2

    # After the round, the claim is a funded project with its investors' record.
    apps.get_model("loans", "Loan").objects.filter(pk=subscription.loan.id).update(status="active")
    cache.clear()
    funded_claim = _project(client, subscription.loan)
    assert funded_claim["public_status"] == "repaying"
    assert funded_claim["record"]["installments_total"] == 2
    assert funded_claim["record"]["installments_paid"] == 0


@pytest.mark.django_db
def test_projects_order_limit_and_cache(client: Client, admin_user: Model) -> None:
    now = timezone.now()
    today = _today()
    loan_model = apps.get_model("loans", "Loan")
    older_open = cast(Any, _create_published_loan(admin_user))
    newer_open = cast(Any, _create_published_loan(admin_user))
    fully_funded = cast(Any, _create_published_loan(admin_user))
    loan_model.objects.filter(pk=older_open.pk).update(published_at=now - timedelta(days=3))
    loan_model.objects.filter(pk=newer_open.pk).update(published_at=now - timedelta(days=1))
    loan_model.objects.filter(pk=fully_funded.pk).update(
        published_at=now - timedelta(days=9),
        committed_principal_minor=fully_funded.principal_minor,
    )
    older_funded = _funded_direct_loan(
        admin_user,
        status="active",
        principal_minor=10_000_00,
        installments=[(today + timedelta(days=30), 10_000_00, 100_00)],
        holders=[_lender("public-order-1@example.test")],
        loan_start_date=today - timedelta(days=60),
    )
    newer_funded = _funded_direct_loan(
        admin_user,
        status="repaid",
        principal_minor=10_000_00,
        installments=[(today + timedelta(days=30), 10_000_00, 100_00)],
        holders=[_lender("public-order-2@example.test")],
        loan_start_date=today - timedelta(days=20),
    )

    ids = [row["loan_id"] for row in client.get(PROJECTS_URL).json()]

    assert ids == [
        str(newer_open.pk),
        str(older_open.pk),
        str(fully_funded.pk),
        str(newer_funded.pk),
        str(older_funded.pk),
    ]
    limited = client.get(PROJECTS_URL, {"limit": 2}).json()
    assert [row["loan_id"] for row in limited] == ids[:2]
    assert client.get(PROJECTS_URL, {"limit": 0}).status_code == 400
    assert client.get(PROJECTS_URL, {"limit": 501}).status_code == 400

    # The payload is cached for a short time (60 s), then simply expires.
    _create_published_loan(admin_user)
    assert [row["loan_id"] for row in client.get(PROJECTS_URL).json()] == ids
    cache.clear()
    assert len(client.get(PROJECTS_URL).json()) == 6


@pytest.mark.django_db
def test_direct_projects_are_read_without_a_query_per_loan(
    client: Client,
    admin_user: Model,
) -> None:
    today = _today()

    def add_loans(count: int, offset: int) -> None:
        for index in range(offset, offset + count):
            _create_published_loan(admin_user)
            _funded_direct_loan(
                admin_user,
                status="active",
                principal_minor=10_000_00,
                installments=[(today + timedelta(days=30), 10_000_00, 100_00)],
                holders=[_lender(f"public-queries-{index}@example.test")],
            )

    def project_queries() -> int:
        cache.clear()
        with CaptureQueriesContext(connection) as queries:
            assert client.get(PROJECTS_URL).status_code == 200
        return len(queries)

    add_loans(2, 0)
    baseline = project_queries()
    add_loans(4, 2)

    assert project_queries() == baseline


@pytest.mark.django_db
def test_public_endpoints_are_anonymous_and_ignore_sessions(
    client: Client,
    admin_user: Model,
    investor: Model,
) -> None:
    loan = cast(Any, _create_published_loan(admin_user))
    draft = cast(Any, _create_published_loan(admin_user))
    apps.get_model("loans", "Loan").objects.filter(pk=draft.pk).update(status="draft")
    for view in (
        PublicProjectListView,
        PublicProjectDetailView,
        PublicStatisticsView,
        PublicOriginatorListView,
    ):
        assert view.authentication_classes == []

    anonymous = {
        url: client.get(url)
        for url in (PROJECTS_URL, f"{PROJECTS_URL}{loan.pk}/", STATISTICS_URL, ORIGINATORS_URL)
    }
    assert {url: response.status_code for url, response in anonymous.items()} == {
        url: 200 for url in anonymous
    }
    assert client.get(f"{PROJECTS_URL}{draft.pk}/").status_code == 404
    assert client.get(f"{PROJECTS_URL}00000000-0000-0000-0000-000000000000/").status_code == 404

    # A logged-in session is not read (no session authentication, no CSRF): same payloads.
    client.force_login(cast(Any, investor))
    cache.clear()
    assert client.get(PROJECTS_URL).json() == anonymous[PROJECTS_URL].json()
    assert client.get(ORIGINATORS_URL).json() == anonymous[ORIGINATORS_URL].json()


def test_public_country_code_normalizes_admin_values() -> None:
    assert public_country_code("Switzerland") == "CH"
    assert public_country_code(" ch ") == "CH"
    assert public_country_code("Deutschland") == "DE"
    assert public_country_code("Atlantis") == ""
    assert public_country_code("ZZ") == ""
    assert public_country_code("") == ""


def test_openapi_schema_describes_the_public_site_endpoints() -> None:
    generators: Any = import_module("drf_spectacular.generators")
    schema = generators.SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    components = schema["components"]["schemas"]

    operations = {
        PROJECTS_URL: "v1_marketplace_primary_public_projects_list",
        f"{PROJECTS_URL}{{loan_id}}/": "v1_marketplace_primary_public_projects_retrieve",
        STATISTICS_URL: "v1_marketplace_primary_public_statistics_retrieve",
        ORIGINATORS_URL: "v1_marketplace_primary_public_originators_list",
    }
    for path, operation_id in operations.items():
        operation = paths[path]["get"]
        assert operation["operationId"] == operation_id
        assert operation.get("security") in (None, [], [{}])
    assert set(components["PublicProject"]["properties"]) == PUBLIC_PROJECT_FIELDS
    assert set(components["PublicProjectRecord"]["properties"]) == RECORD_FIELDS
    assert set(components["PublicStatistics"]["properties"]) == {
        "as_of",
        "loans_funded",
        "loans_repaid",
        "loans_late",
        "loans_defaulted",
        "average_interest_rate_bps",
        "originators_count",
        "countries_count",
        "by_currency",
    }
    assert set(components["PublicOriginator"]["properties"]) == {
        "id",
        "name",
        "country",
        "partner_since",
        "claims_funded",
    }
