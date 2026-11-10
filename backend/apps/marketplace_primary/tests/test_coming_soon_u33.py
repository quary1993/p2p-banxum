"""IP of Webby-Soft SRL. U33-DEC-17: Coming soon opportunities and the opening alert."""

from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.marketplace_primary.models import LoanOpeningAlert
from backend.apps.marketplace_primary.public_site import list_public_projects
from backend.apps.marketplace_primary.services import (
    CreatePrimaryInvestmentOrderCommand,
    MarketplacePrimaryValidationError,
    create_primary_investment_order,
)
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import OutboxMessage

pytestmark = pytest.mark.django_db

OPENING_TOPIC = "email.loan_opening_alert"


def _loans() -> Any:
    return import_module("backend.apps.loans.services")


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="soon-admin@example.test",
            password="AdminPass123!",
            full_name="Soon Admin",
            account_type="superadmin",
            status="active",
            is_staff=True,
            is_superuser=True,
        ),
    )


def _make_investor(email: str) -> Model:
    user_model: Any = get_user_model()
    user = cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name="Soon Investor",
            account_type="natural_person_lender",
            status="active",
        ),
    )
    cast(Any, user).phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])
    apps.get_model("kyc_compliance", "KycVerificationCase").objects.create(
        user_id=user.pk,
        subject_reference=f"user:{user.pk}",
        provider_environment="test",
        workflow_id="test-workflow",
        vendor_data=f"user:{user.pk}",
        status="approved",
        decision_at=timezone.now(),
    )
    apps.get_model("ledger", "InvestorPayoutInstruction").objects.create(
        investor_user_id=user.pk,
        currency_id="CHF",
        destination_iban="CH5604835012345678009",
        destination_account_name="Soon Investor",
        is_verified_usable=True,
        is_default_return=True,
        verified_at=timezone.now(),
        created_by_admin_id=user.pk,
        metadata={"source": "test_return_account"},
    )
    return user


@pytest.fixture
def investor() -> Model:
    return _make_investor("soon-investor@example.test")


def _draft(admin_user: Model, *, title: str = "Coming soon bridge loan") -> Model:
    borrower = apps.get_model("entities", "BorrowerEntity").objects.create(
        legal_name="Soon Borrower AG",
        year_founded=2015,
        kyb_status="approved",
        country="CH",
        created_by_admin_id=admin_user.pk,
    )
    loans = _loans()
    return cast(
        Model,
        loans.create_loan(
            loans.CreateLoanCommand(
                actor=admin_user,
                borrower_id=str(borrower.pk),
                title=title,
                investor_summary="A secured opportunity shown before it opens.",
                purpose="bridge_financing",
                principal_minor=100_000_00,
                currency="CHF",
                interest_rate_bps=950,
                term_months=18,
                repayment_type="equal_installments",
                funding_deadline=timezone.localdate() + timedelta(days=30),
                collateral_type="real_estate",
                collateral_value_minor=180_000_00,
                risk_rating="BBB",
            )
        ),
    )


def _announce(admin_user: Model, loan: Model, *, days: int = 5) -> Any:
    client = Client()
    client.force_login(cast(Any, admin_user))
    return client.post(
        f"/api/v1/loans/admin/loans/{loan.pk}/coming-soon/",
        data={
            "planned_opening_date": (
                business_date(timezone.now()) + timedelta(days=days)
            ).isoformat(),
            "note": "Documents are being finished.",
        },
        content_type="application/json",
    )


def _client(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def _publish(admin_user: Model, loan: Model) -> None:
    loans = _loans()
    loans.publish_loan(loans.PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))


def test_admin_shows_a_draft_as_coming_soon_and_hides_it_again(admin_user: Model) -> None:
    loan = _draft(admin_user)

    response = _announce(admin_user, loan)

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == "draft"
    assert body["coming_soon_at"] is not None
    assert (
        body["planned_opening_date"]
        == (business_date(timezone.now()) + timedelta(days=5)).isoformat()
    )
    event_model = apps.get_model("loans", "LoanEvent")
    assert event_model.objects.filter(loan_id=loan.pk, event_type="coming_soon_announced").exists()

    withdrawn = _client(admin_user).delete(f"/api/v1/loans/admin/loans/{loan.pk}/coming-soon/")
    assert withdrawn.status_code == 200, withdrawn.content
    assert withdrawn.json()["coming_soon_at"] is None
    assert withdrawn.json()["planned_opening_date"] is None
    assert event_model.objects.filter(loan_id=loan.pk, event_type="coming_soon_withdrawn").exists()


def test_the_planned_date_must_be_between_today_and_the_funding_deadline(
    admin_user: Model,
) -> None:
    loan = _draft(admin_user)

    past = _announce(admin_user, loan, days=-1)
    late = _announce(admin_user, loan, days=40)

    assert past.status_code == 400
    assert "past" in past.json()["detail"]
    assert late.status_code == 400
    assert "funding deadline" in late.json()["detail"]


def test_only_a_draft_direct_loan_can_be_coming_soon(admin_user: Model, investor: Model) -> None:
    loan = _draft(admin_user)
    _publish(admin_user, loan)

    response = _announce(admin_user, loan)

    assert response.status_code == 400
    assert "draft Direct loan" in response.json()["detail"]
    assert _client(investor).post(
        f"/api/v1/loans/admin/loans/{loan.pk}/coming-soon/", data={}
    ).status_code in {400, 403}


def test_an_investor_sees_coming_soon_but_cannot_invest(admin_user: Model, investor: Model) -> None:
    hidden = _draft(admin_user, title="Hidden draft")
    loan = _draft(admin_user)
    assert _announce(admin_user, loan).status_code == 200
    client = _client(investor)

    listed = client.get("/api/v1/marketplace/primary/coming-soon/")
    assert listed.status_code == 200, listed.content
    [row] = listed.json()
    assert row["loan_id"] == str(loan.pk)
    assert row["opportunity_status"] == "coming_soon"
    assert row["opening_alert_requested"] is False
    open_ids = [
        item["loan_id"] for item in client.get("/api/v1/marketplace/primary/opportunities/").json()
    ]
    assert str(loan.pk) not in open_ids
    assert str(hidden.pk) not in open_ids

    detail = client.get(f"/api/v1/marketplace/primary/loans/{loan.pk}/")
    assert detail.status_code == 200, detail.content
    assert detail.json()["opportunity_status"] == "coming_soon"
    assert client.get(f"/api/v1/marketplace/primary/loans/{hidden.pk}/").status_code == 400

    with pytest.raises(MarketplacePrimaryValidationError, match="not published"):
        create_primary_investment_order(
            CreatePrimaryInvestmentOrderCommand(
                actor=investor,
                loan_id=str(loan.pk),
                amount_minor=10_000_00,
                idempotency_key="soon-order",
            )
        )


def test_the_opening_alert_is_sent_once_at_the_real_opening(
    admin_user: Model, investor: Model
) -> None:
    other = _make_investor("soon-other@example.test")
    loan = _draft(admin_user)
    assert _announce(admin_user, loan).status_code == 200
    url = f"/api/v1/marketplace/primary/loans/{loan.pk}/opening-alert/"

    asked = _client(investor).post(url)
    assert asked.status_code == 200, asked.content
    assert asked.json()["opening_alert_requested"] is True
    assert _client(investor).post(url).status_code == 200
    assert LoanOpeningAlert.objects.filter(loan_id=loan.pk).count() == 1
    assert _client(other).post(url).status_code == 200
    cancelled = _client(other).delete(url)
    assert cancelled.json()["opening_alert_requested"] is False
    assert not OutboxMessage.objects.filter(topic=OPENING_TOPIC).exists()

    _publish(admin_user, loan)

    [message] = OutboxMessage.objects.filter(topic=OPENING_TOPIC)
    assert message.payload["user_id"] == str(investor.pk)
    assert message.payload["subject"] == "Now open: Coming soon bridge loan"
    alert = LoanOpeningAlert.objects.get(loan_id=loan.pk, investor_user_id=investor.pk)
    assert alert.notified_at is not None
    assert alert.outbox_message_id == message.pk
    # Once open, the loan is an ordinary open opportunity and no longer coming soon.
    assert _client(investor).get("/api/v1/marketplace/primary/coming-soon/").json() == []
    assert _client(investor).post(url).status_code == 400
    topics = [
        row["topic"]
        for row in _client(investor)
        .get("/api/v1/investor/portal/notifications/")
        .json()["notifications"]
    ]
    assert OPENING_TOPIC in topics


def test_smart_invest_does_not_alert_again_after_the_opening_alert(
    admin_user: Model, investor: Model
) -> None:
    smart_invest = import_module("backend.apps.smart_invest.services")
    follower = _make_investor("soon-follower@example.test")
    for user in (investor, follower):
        smart_invest.save_smart_invest_rule(
            smart_invest.SaveSmartInvestRuleCommand(
                actor=user,
                minimum_yield_bps=900,
                maximum_term_months=24,
                currencies=["CHF"],
                collateral=["any_secured"],
            )
        )
    loan = _draft(admin_user)
    assert _announce(admin_user, loan).status_code == 200
    assert (
        _client(follower)
        .post(f"/api/v1/marketplace/primary/loans/{loan.pk}/opening-alert/")
        .status_code
        == 200
    )

    _publish(admin_user, loan)

    match_topic = "email.smart_invest_opportunity_match"
    assert OutboxMessage.objects.filter(topic=OPENING_TOPIC).count() == 1
    assert OutboxMessage.objects.filter(
        topic=match_topic, payload__user_id=str(investor.pk)
    ).exists()
    assert not OutboxMessage.objects.filter(
        topic=match_topic, payload__user_id=str(follower.pk)
    ).exists()
    # The match is still recorded, so Smart Invest does not alert later either.
    match_model = apps.get_model("smart_invest", "SmartInvestMatchNotification")
    assert match_model.objects.filter(investor_user_id=follower.pk, loan_id=loan.pk).exists()


def test_the_public_site_shows_coming_soon_with_the_planned_date(admin_user: Model) -> None:
    hidden = _draft(admin_user, title="Hidden draft")
    loan = _draft(admin_user)
    assert _announce(admin_user, loan, days=7).status_code == 200

    projects = list_public_projects()

    ids = [project["loan_id"] for project in projects]
    assert str(hidden.pk) not in ids
    [project] = [project for project in projects if project["loan_id"] == str(loan.pk)]
    assert project["public_status"] == "coming_soon"
    assert project["committed_principal_minor"] == 0
    assert project["planned_opening_date"] == business_date(timezone.now()) + timedelta(days=7)
    assert project["published_at"] is None


def test_smart_invest_lists_matching_coming_soon_apart_from_the_open_matches(
    admin_user: Model, investor: Model
) -> None:
    smart_invest = import_module("backend.apps.smart_invest.services")
    smart_invest.save_smart_invest_rule(
        smart_invest.SaveSmartInvestRuleCommand(
            actor=investor,
            minimum_yield_bps=900,
            maximum_term_months=24,
            currencies=["CHF"],
            collateral=["any_secured"],
        )
    )
    loan = _draft(admin_user)
    assert _announce(admin_user, loan).status_code == 200

    payload = _client(investor).get("/api/v1/investor/smart-invest/").json()

    assert payload["match_count"] == 0
    assert payload["matches"] == []
    [soon] = payload["coming_soon_matches"]
    assert soon["loan_id"] == str(loan.pk)
    assert soon["opportunity_status"] == "coming_soon"
    smart_invest.pause_smart_invest_rule(actor=investor)
    assert (
        _client(investor).get("/api/v1/investor/smart-invest/").json()["coming_soon_matches"] == []
    )
