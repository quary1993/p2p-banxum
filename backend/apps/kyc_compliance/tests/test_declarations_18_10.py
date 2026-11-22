"""IP of Webby-Soft SRL. 18.10 (Q12, U33-DEC-27): declarations, reviews, re-verification."""

from __future__ import annotations

from datetime import date, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.kyc_compliance import declarations as services
from backend.apps.kyc_compliance.models import ComplianceReview, InvestorDeclaration
from backend.apps.platform_core.domain import declarations as rules
from backend.apps.platform_core.domain.time import business_date
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.models.base import AppendOnlyViolation

CLEAN = {
    "beneficial_owner_is_self": True,
    "sources_of_funds": ["salary", "savings"],
    "savings_origin": "Salary saved since 2015",
    "pep_status": "no",
    "yearly_volume_band": "10k_50k",
}


@pytest.fixture(autouse=True)
def _gate_on(settings: Any) -> None:
    settings.COMPLIANCE_DECLARATIONS_REQUIRED = True


def _user(email: str, *, account_type: str = "natural_person_lender", **extra: Any) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name=email.split("@")[0],
            account_type=account_type,
            status="active",
            **extra,
        ),
    )


def _compliance_officer(email: str = "compliance@example.test") -> Model:
    return _user(
        email,
        account_type="admin",
        is_staff=True,
        staff_roles=[rules.ROLE_COMPLIANCE],
    )


def test_validation_and_triggers() -> None:
    with pytest.raises(rules.DeclarationError, match="savings come from"):
        rules.validate_declaration({**CLEAN, "savings_origin": ""})
    with pytest.raises(rules.DeclarationError, match="person, the relation"):
        rules.validate_declaration({**CLEAN, "pep_status": "yes"})
    with pytest.raises(rules.DeclarationError, match="company name"):
        rules.validate_declaration({**CLEAN, "subject_type": "company"})
    answers = rules.validate_declaration(
        {
            **CLEAN,
            "beneficial_owner_is_self": False,
            "beneficial_owner_name": "A. Parent",
            "sources_of_funds": ["other"],
            "source_other_text": "Lottery",
            "pep_status": "not_sure",
            "yearly_volume_band": "over_250k",
        }
    )
    assert set(rules.review_triggers(answers)) == {
        rules.TRIGGER_PEP,
        rules.TRIGGER_BENEFICIAL_OWNER,
        rules.TRIGGER_SOURCE_OTHER,
        rules.TRIGGER_VOLUME,
    }
    assert rules.review_triggers(rules.validate_declaration(CLEAN)) == ()


@pytest.mark.django_db
def test_no_declaration_blocks_new_investments_and_a_clean_one_unblocks() -> None:
    investor = _user("investor@example.test")
    assert services.investment_block(investor) == services.BLOCK_NO_DECLARATION
    declaration = services.submit_declaration(
        services.SubmitDeclarationCommand(actor=investor, data=dict(CLEAN))
    )
    assert declaration.version == 1 and declaration.review_triggers == []
    assert services.investment_block(investor) is None
    # A new submission is a new version; the old one stays and cannot be changed.
    second = services.submit_declaration(
        services.SubmitDeclarationCommand(actor=investor, data={**CLEAN, "pep_status": "no"})
    )
    assert second.version == 2
    assert InvestorDeclaration.objects.filter(user_id=investor.pk).count() == 2
    with pytest.raises((DatabaseError, AppendOnlyViolation)), transaction.atomic():
        InvestorDeclaration.objects.filter(pk=declaration.pk).update(pep_status="yes")


@pytest.mark.django_db
def test_a_trigger_opens_a_necessary_review_that_blocks_until_compliance_closes_it() -> None:
    investor = _user("pep@example.test")
    officer = _compliance_officer()
    services.submit_declaration(
        services.SubmitDeclarationCommand(actor=investor, data={**CLEAN, "pep_status": "not_sure"})
    )
    review = ComplianceReview.objects.get(user_id=investor.pk)
    assert review.necessary and review.triggers == [rules.TRIGGER_PEP]
    assert services.investment_block(investor) == services.BLOCK_REVIEW_OPEN

    # Another trigger later joins the same open review.
    services.submit_declaration(
        services.SubmitDeclarationCommand(
            actor=investor,
            data={**CLEAN, "pep_status": "not_sure", "yearly_volume_band": "over_250k"},
        )
    )
    review.refresh_from_db()
    assert ComplianceReview.objects.filter(user_id=investor.pk).count() == 1
    assert set(review.triggers) == {rules.TRIGGER_PEP, rules.TRIGGER_VOLUME}

    services.decide_review(
        services.DecideReviewCommand(
            actor=officer,
            review_id=str(review.id),
            decision="more_information",
            investor_message="Please describe the function of the person.",
        )
    )
    assert services.investment_block(investor) == services.BLOCK_REVIEW_OPEN
    assert OutboxMessage.objects.filter(topic="email.compliance_more_information").exists()
    services.decide_review(
        services.DecideReviewCommand(
            actor=officer, review_id=str(review.id), decision="close", note="No PEP link found."
        )
    )
    assert services.investment_block(investor) is None


@pytest.mark.django_db
def test_only_the_compliance_role_decides_and_only_a_superadmin_grants_roles() -> None:
    investor = _user("someone@example.test")
    plain_admin = _user("admin@example.test", account_type="admin", is_staff=True)
    superadmin = _user(
        "super@example.test", account_type="superadmin", is_staff=True, is_superuser=True
    )
    services.submit_declaration(
        services.SubmitDeclarationCommand(
            actor=investor,
            data={
                **CLEAN,
                "pep_status": "yes",
                "pep_person": "Self",
                "pep_relation": "Self",
                "pep_function": "Mayor",
                "pep_country": "CH",
            },
        )
    )
    review = ComplianceReview.objects.get(user_id=investor.pk)
    with pytest.raises(services.DeclarationsPermissionError):
        services.decide_review(
            services.DecideReviewCommand(
                actor=plain_admin, review_id=str(review.id), decision="close", note="ok ok ok"
            )
        )
    with pytest.raises(services.DeclarationsPermissionError):
        services.set_staff_roles(
            services.SetStaffRolesCommand(
                actor=plain_admin, user_id=str(plain_admin.pk), roles=(rules.ROLE_COMPLIANCE,)
            )
        )
    services.set_staff_roles(
        services.SetStaffRolesCommand(
            actor=superadmin,
            user_id=str(plain_admin.pk),
            roles=(rules.ROLE_COMPLIANCE_DEPUTY,),
        )
    )
    plain_admin.refresh_from_db()
    services.decide_review(
        services.DecideReviewCommand(
            actor=plain_admin, review_id=str(review.id), decision="close", note="Checked by deputy."
        )
    )
    with pytest.raises(services.DeclarationsError, match="admin accounts"):
        services.set_staff_roles(
            services.SetStaffRolesCommand(
                actor=superadmin, user_id=str(investor.pk), roles=(rules.ROLE_COMPLIANCE,)
            )
        )


@pytest.mark.django_db
def test_reverification_date_notices_and_block_after_the_date() -> None:
    investor = _user("reverify@example.test")
    officer = _compliance_officer()
    services.submit_declaration(services.SubmitDeclarationCommand(actor=investor, data=dict(CLEAN)))
    today = business_date(timezone.now())
    due = today + timedelta(days=40)
    services.set_reverification(
        services.SetReverificationCommand(actor=officer, investor_id=str(investor.pk), due_date=due)
    )
    assert services.send_reverification_notices(as_of=due - timedelta(days=31))["sent"] == []
    assert len(services.send_reverification_notices(as_of=due - timedelta(days=30))["sent"]) == 1
    # Same milestone again: nothing; after a missed run only the closest milestone.
    assert services.send_reverification_notices(as_of=due - timedelta(days=29))["sent"] == []
    assert len(services.send_reverification_notices(as_of=due - timedelta(days=5))["sent"]) == 1
    assert services.send_reverification_notices(as_of=due - timedelta(days=4))["sent"] == []
    assert OutboxMessage.objects.filter(topic="email.compliance_reverification_due").count() == 2

    assert services.investment_block(investor, on=due) is None
    assert services.investment_block(investor, on=due + timedelta(days=1)) == (
        services.BLOCK_REVERIFICATION_DUE
    )
    services.complete_reverification(actor=officer, investor_id=str(investor.pk))
    assert services.investment_block(investor, on=due + timedelta(days=1)) is None
    with pytest.raises(services.DeclarationsError, match="future"):
        services.set_reverification(
            services.SetReverificationCommand(
                actor=officer, investor_id=str(investor.pk), due_date=date(2020, 1, 1)
            )
        )


@pytest.mark.django_db
def test_the_primary_order_is_refused_while_blocked() -> None:
    helpers: Any = import_module("backend.apps.marketplace_primary.tests.test_primary_marketplace")
    primary: Any = import_module("backend.apps.marketplace_primary.services")
    admin = _user("loan-admin@example.test", account_type="admin", is_staff=True)
    investor = _user("blocked@example.test")
    helpers._approve_financial_access(investor)
    loan = helpers._create_published_loan(admin)
    with pytest.raises(primary.MarketplacePrimaryValidationError, match="declarations"):
        primary.create_primary_investment_order(
            primary.CreatePrimaryInvestmentOrderCommand(
                actor=investor,
                loan_id=str(cast(Any, loan).pk),
                amount_minor=5_000_00,
                idempotency_key="blocked-order",
            )
        )


@pytest.mark.django_db
def test_api_for_investor_and_compliance() -> None:
    investor = _user("api-investor@example.test")
    officer = _compliance_officer("api-officer@example.test")
    client = Client()
    client.force_login(cast(Any, investor))
    status_before = client.get("/api/v1/kyc/declarations/").json()
    assert status_before["declaration"] is None
    assert status_before["investment_block"] == services.BLOCK_NO_DECLARATION
    created = client.post(
        "/api/v1/kyc/declarations/",
        {**CLEAN, "yearly_volume_band": "over_250k"},
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    assert created.json()["review_open"] is True
    assert created.json()["declaration"]["version"] == 1

    staff = Client()
    staff.force_login(cast(Any, officer))
    reviews = staff.get("/api/v1/kyc/admin/compliance/reviews/?status=open")
    assert reviews.status_code == 200 and len(reviews.json()) == 1
    review_id = reviews.json()[0]["id"]
    closed = staff.post(
        f"/api/v1/kyc/admin/compliance/reviews/{review_id}/decision/",
        {"decision": "close", "note": "Volume explained by a property sale."},
        content_type="application/json",
    )
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    file = staff.get(f"/api/v1/kyc/admin/compliance/investors/{investor.pk}/")
    assert file.status_code == 200 and len(file.json()["declarations"]) == 1
    # An investor cannot reach the compliance endpoints.
    assert client.get("/api/v1/kyc/admin/compliance/reviews/").status_code == 403


COMPANY = {
    **CLEAN,
    "company_details": {
        "company_name": "Example Holding AG",
        "representative_name": "A. Director",
        "representative_authority": "Board member, signs alone",
        "controlling_persons": "A. Director (60%)",
    },
}


@pytest.mark.django_db
def test_the_account_type_decides_the_declaration_subject() -> None:
    """Audit S7-1: a company account cannot give the shorter person declaration."""
    company = _user("company-rep@example.test", account_type="legal_entity_lender_representative")
    person = _user("private@example.test")
    assert (
        services.investor_compliance_status(company)["declaration_subject"] == rules.SUBJECT_COMPANY
    )
    assert (
        services.investor_compliance_status(person)["declaration_subject"] == rules.SUBJECT_PERSON
    )
    # No subject given: the company account must still give the company details.
    with pytest.raises(services.DeclarationsError, match="company name"):
        services.submit_declaration(
            services.SubmitDeclarationCommand(actor=company, data=dict(CLEAN))
        )
    # A forged subject is refused for both account types.
    with pytest.raises(services.DeclarationsError, match="company"):
        services.submit_declaration(
            services.SubmitDeclarationCommand(
                actor=company, data={**CLEAN, "subject_type": rules.SUBJECT_PERSON}
            )
        )
    with pytest.raises(services.DeclarationsError):
        services.submit_declaration(
            services.SubmitDeclarationCommand(
                actor=person, data={**COMPANY, "subject_type": rules.SUBJECT_COMPANY}
            )
        )
    saved = services.submit_declaration(
        services.SubmitDeclarationCommand(actor=company, data=dict(COMPANY))
    )
    assert saved.subject_type == rules.SUBJECT_COMPANY

    client = Client()
    client.force_login(cast(Any, company))
    refused = client.post(
        "/api/v1/kyc/declarations/",
        {**CLEAN, "subject_type": "person"},
        content_type="application/json",
    )
    assert refused.status_code == 400, refused.content
    assert client.get("/api/v1/kyc/declarations/").json()["declaration_subject"] == "company"


@pytest.mark.django_db
def test_one_unresolved_necessary_review_with_its_history() -> None:
    """Audit S7-6, D3, D4: a manual review joins the open one; history is kept."""
    investor = _user("one-review@example.test")
    officer = _compliance_officer()
    services.submit_declaration(
        services.SubmitDeclarationCommand(actor=investor, data={**CLEAN, "pep_status": "not_sure"})
    )
    joined = services.open_review(
        services.OpenReviewCommand(
            actor=officer, investor_id=str(investor.pk), reason="Adverse media hit."
        )
    )
    reviews = ComplianceReview.objects.filter(user_id=investor.pk)
    assert reviews.count() == 1 and joined.id == reviews.get().id
    assert "manual" in joined.triggers
    assert [event["type"] for event in joined.trigger_events] == ["declaration", "manual"]
    task_model: Any = import_module("backend.apps.admin_ops.models").AdminTask
    assert (
        task_model.objects.filter(
            related_object_type="ComplianceReview", related_object_id=str(joined.id)
        ).count()
        == 1
    )
    assert OutboxMessage.objects.filter(topic="email.compliance_review_opened").count() == 1

    # The database refuses a second unresolved necessary review.
    with pytest.raises(DatabaseError), transaction.atomic():
        ComplianceReview.objects.create(
            user_id=investor.pk, necessary=True, status="open", triggers=["manual"]
        )

    # D5: a new declaration after "more information" opens the review again.
    services.decide_review(
        services.DecideReviewCommand(
            actor=officer,
            review_id=str(joined.id),
            decision="more_information",
            investor_message="Please describe the function of the person.",
        )
    )
    services.submit_declaration(services.SubmitDeclarationCommand(actor=investor, data=CLEAN))
    joined.refresh_from_db()
    assert joined.status == "open"
    assert [event["type"] for event in joined.trigger_events][-2:] == [
        "more_information",
        "declaration",
    ]
    services.decide_review(
        services.DecideReviewCommand(
            actor=officer, review_id=str(joined.id), decision="close", note="Function explained."
        )
    )
    task = task_model.objects.get(
        related_object_type="ComplianceReview", related_object_id=str(joined.id)
    )
    assert str(task.status) == "resolved"


@pytest.mark.django_db
def test_compliance_actions_need_an_investor_and_one_current_reverification() -> None:
    """Audit S7-6: staff and borrower accounts are refused; one current date only."""
    officer = _compliance_officer()
    staff = _user("staff@example.test", account_type="admin", is_staff=True)
    due = business_date(timezone.now()) + timedelta(days=40)
    with pytest.raises(services.DeclarationsError, match="not an investor"):
        services.open_review(
            services.OpenReviewCommand(
                actor=officer, investor_id=str(staff.pk), reason="Wrong account."
            )
        )
    with pytest.raises(services.DeclarationsError, match="not an investor"):
        services.set_reverification(
            services.SetReverificationCommand(
                actor=officer, investor_id=str(staff.pk), due_date=due
            )
        )
    investor = _user("dates@example.test")
    services.set_reverification(
        services.SetReverificationCommand(actor=officer, investor_id=str(investor.pk), due_date=due)
    )
    services.set_reverification(
        services.SetReverificationCommand(
            actor=officer, investor_id=str(investor.pk), due_date=due + timedelta(days=5)
        )
    )
    model: Any = import_module("backend.apps.kyc_compliance.models").InvestorReverification
    current = model.objects.filter(
        user_id=investor.pk, completed_at__isnull=True, replaced_at__isnull=True
    )
    assert current.count() == 1 and current.get().due_date == due + timedelta(days=5)
    with pytest.raises(DatabaseError), transaction.atomic():
        model.objects.create(user_id=investor.pk, due_date=due, set_by_user_id=officer.pk)
