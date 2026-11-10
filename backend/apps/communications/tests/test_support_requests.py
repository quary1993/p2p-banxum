"""IP of Webby-Soft SRL. U33-DEC-35 Help messages and U33-DEC-28 account closure requests."""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from rest_framework.test import APIClient

from backend.apps.communications.models import InvestorSupportRequest
from backend.apps.communications.services import render_email_for_outbox_message
from backend.apps.communications.tests.conftest import ThrottleClock
from backend.apps.platform_core.models import OutboxMessage, PlatformSetting

URL = "/api/v1/investor/portal/support-requests/"


def _user(email: str, **extra: Any) -> Model:
    defaults: dict[str, Any] = {
        "full_name": "Support Investor",
        "account_type": "natural_person_lender",
        "status": "active",
    }
    return cast(Model, get_user_model().objects.create_user(email=email, **{**defaults, **extra}))


@pytest.fixture
def investor(db: None) -> Model:
    PlatformSetting.objects.update_or_create(
        key="platform.support_email",
        defaults={"value": "help@banxum.test", "value_type": "string"},
    )
    return _user("support-investor@example.test")


def _client(user: Model) -> APIClient:
    client = APIClient()
    client.force_authenticate(cast(Any, user))
    return client


def _help(key: str, **extra: Any) -> dict[str, Any]:
    return {
        "kind": "help",
        "idempotency_key": key,
        "topic": "My Banxum account",
        "message": "How do I change my bank account?",
        **extra,
    }


@pytest.mark.django_db
def test_help_message_is_emailed_to_support_with_a_receipt_for_the_investor(
    investor: Model, throttle_clock: ThrottleClock
) -> None:
    response = _client(investor).post(URL, _help("help-1"), format="json")
    assert response.status_code == 201, response.content
    receipt = response.json()
    assert receipt["reference"].startswith("SUP-")
    assert receipt["receipt_email"] == "support-investor@example.test"

    request = InvestorSupportRequest.objects.get(reference=receipt["reference"])
    assert request.kind == "help"
    assert request.message == "How do I change my bank account?"
    team = request.support_outbox_message
    assert team is not None
    assert team.topic == "email.investor_support_request"
    assert team.payload["email"] == "help@banxum.test"
    # The team email is not one of the investor's notifications.
    assert "user_id" not in team.payload
    rendered = render_email_for_outbox_message(team)
    assert rendered.recipient_email == "help@banxum.test"
    assert rendered.reply_to == "support-investor@example.test"
    assert "How do I change my bank account?" in rendered.body_text
    assert receipt["reference"] in rendered.subject

    own = request.receipt_outbox_message
    assert own is not None
    assert own.payload["user_id"] == str(investor.pk)
    own_email = render_email_for_outbox_message(own)
    assert own_email.recipient_email == "support-investor@example.test"
    assert own_email.subject == f"We received your message ({receipt['reference']})"
    # No ticket system and no closure: a Help message opens no admin task.
    assert request.admin_task_id is None


@pytest.mark.django_db
def test_a_retry_returns_the_same_receipt_and_a_reused_key_is_refused(
    investor: Model, throttle_clock: ThrottleClock
) -> None:
    client = _client(investor)
    first = client.post(URL, _help("help-retry"), format="json").json()
    again = client.post(URL, _help("help-retry"), format="json")
    assert again.status_code == 201
    assert again.json()["reference"] == first["reference"]
    assert InvestorSupportRequest.objects.count() == 1
    assert OutboxMessage.objects.filter(topic="email.investor_support_request").count() == 1

    other = client.post(URL, _help("help-retry", message="Another question."), format="json")
    assert other.status_code == 409


@pytest.mark.django_db
def test_message_about_an_investment_names_only_the_investors_own_holding(
    investor: Model, throttle_clock: ThrottleClock
) -> None:
    other = _user("support-other@example.test")
    loan_model = apps.get_model("loans", "Loan")
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    currency = apps.get_model("platform_core", "Currency").objects.get(code="CHF")
    borrower = apps.get_model("entities", "BorrowerEntity").objects.create(
        legal_name="Support Borrower AG",
        year_founded=2018,
        kyb_status="approved",
        country="Switzerland",
        created_by_admin_id=investor.pk,
    )
    loan = loan_model.objects.create(
        borrower=borrower,
        status="active",
        title="Alpine refinancing",
        investor_summary="Test.",
        purpose="working_capital",
        original_principal_minor=10_000_00,
        principal_minor=10_000_00,
        currency=currency,
        interest_rate_bps=800,
        term_months=12,
        repayment_type="equal_installments",
        loan_start_date="2026-01-31",
        funding_deadline="2026-01-31",
        first_payment_date="2026-02-28",
        collateral_value_minor=20_000_00,
        risk_rating="BBB",
        created_by_admin_id=investor.pk,
    )

    def _holding(owner: Model, key: str) -> Any:
        return holding_model.objects.create(
            loan=loan,
            investor_user_id=owner.pk,
            source_type="primary_market",
            source_id=key,
            status="active",
            original_principal_minor=1_000_00,
            current_principal_minor=1_000_00,
            currency=currency,
            loan_share_ppm=100_000,
            assignment_effective_at="2026-02-01T00:00:00Z",
            created_by_admin_id=investor.pk,
            idempotency_key=key,
        )

    own = _holding(investor, "support-own")
    foreign = _holding(other, "support-foreign")
    client = _client(investor)
    refused = client.post(
        URL,
        _help("help-foreign", context_type="holding", context_id=str(foreign.pk)),
        format="json",
    )
    assert refused.status_code == 400
    accepted = client.post(
        URL, _help("help-own", context_type="holding", context_id=str(own.pk)), format="json"
    )
    assert accepted.status_code == 201
    assert accepted.json()["context_label"] == "Alpine refinancing"


@pytest.mark.django_db
def test_account_closure_request_opens_a_task_and_does_not_close_the_account(
    investor: Model, throttle_clock: ThrottleClock
) -> None:
    response = _client(investor).post(
        URL, {"kind": "account_closure", "idempotency_key": "closure-1"}, format="json"
    )
    assert response.status_code == 201, response.content
    reference = response.json()["reference"]
    assert reference.startswith("CLS-")
    request = InvestorSupportRequest.objects.get(reference=reference)
    task = apps.get_model("admin_ops", "AdminTask").objects.get(pk=request.admin_task_id)
    assert task.task_type == "account_access_review"
    assert task.related_object_id == str(request.id)
    assert reference in task.title
    investor.refresh_from_db()
    assert cast(Any, investor).status == "active"
    receipt = request.receipt_outbox_message
    assert receipt is not None
    assert "Your account is not closed yet." in receipt.payload["body_text"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"message": ""}, "message"),
        ({"topic": ""}, "topic"),
    ],
)
def test_help_message_needs_a_topic_and_a_message(
    investor: Model, throttle_clock: ThrottleClock, payload: dict[str, Any], field: str
) -> None:
    response = _client(investor).post(URL, _help("help-empty", **payload), format="json")
    assert response.status_code == 400
    assert field in response.json()["detail"]
    assert not InvestorSupportRequest.objects.exists()


@pytest.mark.django_db
def test_too_many_closure_requests_are_throttled(
    investor: Model, throttle_clock: ThrottleClock
) -> None:
    client = _client(investor)
    for number in range(3):
        sent = client.post(
            URL, {"kind": "account_closure", "idempotency_key": f"cl-{number}"}, format="json"
        )
        assert sent.status_code == 201
    blocked = client.post(
        URL, {"kind": "account_closure", "idempotency_key": "cl-4"}, format="json"
    )
    assert blocked.status_code == 429
    assert int(blocked["Retry-After"]) > 0


@pytest.mark.django_db
def test_only_an_investor_account_can_send_requests(throttle_clock: ThrottleClock) -> None:
    admin = _user("support-admin@example.test", account_type="admin", is_staff=True)
    response = _client(admin).post(URL, _help("help-admin"), format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_admins_see_the_investors_messages_and_the_closure_task_names_the_investor(
    investor: Model, throttle_clock: ThrottleClock
) -> None:
    client = _client(investor)
    assert client.post(URL, _help("help-admin"), format="json").status_code == 201
    closure = client.post(
        URL, {"kind": "account_closure", "idempotency_key": "closure-admin"}, format="json"
    ).json()
    admin = _user("support-admin@example.test", account_type="admin", is_staff=True)

    listed = _client(admin).get(f"/api/v1/admin-ops/users/{investor.pk}/support-requests/")

    assert listed.status_code == 200, listed.content
    rows = listed.json()["support_requests"]
    assert [row["kind"] for row in rows] == ["account_closure", "help"]
    assert rows[1]["message"] == "How do I change my bank account?"
    task_id = rows[0]["admin_task_id"]
    assert task_id
    tasks = _client(admin).get("/api/v1/admin-ops/tasks/").json()
    [task] = [row for row in tasks if row["id"] == task_id]
    assert task["subject_user_id"] == str(investor.pk)
    assert closure["reference"] in task["title"]
    # Investors cannot read this admin list.
    assert client.get(f"/api/v1/admin-ops/users/{investor.pk}/support-requests/").status_code == 403
