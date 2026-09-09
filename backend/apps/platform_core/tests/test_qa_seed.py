from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from backend.apps.platform_core.services.qa_seed import INVESTOR_EMAIL, seed_qa_starting_point


@pytest.mark.django_db
def test_qa_starting_point_is_repeatable_and_uses_real_financial_services(settings: Any) -> None:
    settings.ENVIRONMENT = "local"
    settings.IS_PRODUCTION = False
    settings.COMMUNICATIONS_EMAIL_PROVIDER = "mock"
    actor = get_user_model().objects.create_superuser(
        email="qa.operator@example.test",
        full_name="QA Operator",
        password=None,
    )
    first = seed_qa_starting_point(actor=actor)
    tracked = [
        ("loans", "Loan"),
        ("holdings", "InvestorLoanHolding"),
        ("ledger", "LedgerJournalEntry"),
        ("documents", "DocumentAcceptanceEvidence"),
    ]
    counts = {model: apps.get_model(app, model).objects.count() for app, model in tracked}
    assert counts["Loan"] == 18
    assert counts["InvestorLoanHolding"] >= 1
    assert counts["DocumentAcceptanceEvidence"] == 3
    investor = get_user_model().objects.get(email=INVESTOR_EMAIL)
    assert not investor.has_usable_password()
    assert not investor.is_staff
    assert first == seed_qa_starting_point(actor=actor)
    assert counts == {model: apps.get_model(app, model).objects.count() for app, model in tracked}


@pytest.mark.django_db
@pytest.mark.parametrize("production,provider", [(True, "mock"), (False, "sendgrid")])
def test_qa_seed_refuses_production_and_live_email(
    settings: Any, production: bool, provider: str
) -> None:
    settings.IS_PRODUCTION = production
    settings.ENVIRONMENT = "production" if production else "staging"
    settings.COMMUNICATIONS_EMAIL_PROVIDER = provider
    with pytest.raises(ValueError, match="forbidden|mock"):
        seed_qa_starting_point(actor=None)
    assert not get_user_model().objects.filter(email=INVESTOR_EMAIL).exists()
