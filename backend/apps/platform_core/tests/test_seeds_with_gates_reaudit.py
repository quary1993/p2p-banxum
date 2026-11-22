"""IP of Webby-Soft SRL. Re-audit P-2: the seeds work with the always-on rules.

With the declarations rule and the security proof rule on (as on the servers), the QA starting
point and the demo catalogues publish engine loans and accrued-interest offers with verified
(synthetic) securities, and the QA investor's investments go through.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command

from backend.apps.platform_core.services.qa_seed import (
    INVESTOR_EMAIL,
    QA_INVESTOR_PIN,
    seed_qa_starting_point,
)


@pytest.fixture
def gates_on(settings: Any, tmp_path: Any) -> None:
    settings.ENVIRONMENT = "local"
    settings.IS_PRODUCTION = False
    settings.COMMUNICATIONS_EMAIL_PROVIDER = "mock"
    settings.COMPLIANCE_DECLARATIONS_REQUIRED = True
    settings.SECURITY_PROOFS_REQUIRED = True
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.mark.django_db
def test_the_qa_starting_point_works_with_both_rules_on(gates_on: None) -> None:
    actor = get_user_model().objects.create_superuser(
        email="qa.gates@example.test", full_name="QA Gates", password=None
    )
    first = seed_qa_starting_point(actor=actor)
    loans = apps.get_model("loans", "Loan").objects.filter(status__in=["published", "active"])
    assert loans.exists()
    direct = loans.filter(product_type="direct")
    assert direct.exists()
    assert all(str(loan.interest_convention) == "act_365_fixed" for loan in direct)
    proofs: Any = __import__("backend.apps.loans.security_proofs", fromlist=["x"])
    assert all(proofs.publication_problems(loan) == [] for loan in loans)
    holdings = apps.get_model("holdings", "InvestorLoanHolding").objects.all()
    assert "originator_claim" in set(holdings.values_list("loan__product_type", flat=True))

    # One direct investment by the QA investor in a seeded engine loan, both rules on.
    primary: Any = __import__("backend.apps.marketplace_primary.services", fromlist=["x"])
    helpers: Any = __import__(
        "backend.apps.marketplace_primary.tests.test_primary_marketplace", fromlist=["x"]
    )
    investor = get_user_model().objects.get(email=INVESTOR_EMAIL)
    loan = direct.filter(currency_id="CHF").order_by("title").first()
    assert loan is not None
    order = primary.create_primary_investment_order(
        primary.CreatePrimaryInvestmentOrderCommand(
            actor=investor,
            loan_id=str(loan.pk),
            amount_minor=30_000_00,  # the 10/20 minimum for a new investor (18.9)
            idempotency_key="gates-direct-order",
        )
    )
    acceptance = helpers._create_primary_acceptance(
        investor, order_id=str(order.id), idempotency_key="gates-direct-accept"
    )
    allocated = primary.allocate_primary_order_from_balance(
        primary.AllocatePrimaryInvestmentOrderCommand(
            actor=investor,
            order_id=str(order.id),
            **helpers._sandbox_ack(order),
            document_acceptance_id=str(acceptance.pk),
            idempotency_key="gates-direct-allocate",
            **{
                **helpers._sensitive_code_payload(investor, "primary_investment"),
                "pin": QA_INVESTOR_PIN,
            },
        )
    )
    assert str(allocated.status) in {"balance_allocated", "partially_allocated"}
    assert first == seed_qa_starting_point(actor=actor)


@pytest.mark.django_db
def test_the_demo_catalogues_publish_with_both_rules_on(gates_on: None) -> None:
    actor = get_user_model().objects.create_superuser(
        email="demo.gates@example.test", full_name="Demo Gates", password=None
    )
    helpers: Any = __import__(
        "backend.apps.loans.tests.test_seed_marketplace_demo_loans", fromlist=["x"]
    )
    helpers._borrower(actor=actor, legal_name="Gates Borrower Alpha AG")
    helpers._borrower(actor=actor, legal_name="Gates Borrower Beta AG")
    call_command("seed_marketplace_demo_loans", actor_email=actor.email, verbosity=0)
    call_command("seed_originator_demo_loans", actor_email=actor.email, verbosity=0)
    loan_model = apps.get_model("loans", "Loan")
    assert loan_model.objects.filter(product_type="direct", status="published").count() >= 5
    profiles = apps.get_model("originator_claims", "OriginatorLoanProfile").objects.filter(
        opportunity_status="open"
    )
    assert profiles.count() >= 5
    assert all(str(profile.pricing_rule) == "accrued_interest" for profile in profiles)
