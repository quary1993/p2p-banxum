"""IP of Webby-Soft SRL. U33-DEC-20: "Checks & updates" and the structured credit file."""

from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.loans.services import PublishLoanCommand, create_loan, publish_loan
from backend.apps.loans.tests.test_loans import _borrower, _loan_command, admin_user

__all__ = ["admin_user"]

pytestmark = pytest.mark.django_db


def _client(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def test_checks_and_monitoring_reach_the_credit_file(admin_user: Model) -> None:
    borrower = _borrower(admin_user)
    loan = create_loan(_loan_command(admin_user, borrower))
    client = _client(admin_user)
    url = f"/api/v1/loans/admin/loans/{loan.pk}/credit-checks/"

    check = client.post(
        url,
        data={
            "name": "Company and owners",
            "result": "Register details, ownership and authorised signatories reconciled.",
            "source": "Commercial register",
            "checked_on": timezone.localdate().isoformat(),
        },
        content_type="application/json",
    )
    assert check.status_code == 201, check.content
    future = client.post(
        url,
        data={
            "name": "Later",
            "result": "x",
            "checked_on": (timezone.localdate() + timedelta(days=3)).isoformat(),
        },
        content_type="application/json",
    )
    assert future.status_code == 400
    assert (
        client.post(
            url, data={"name": "No result", "result": " "}, content_type="application/json"
        ).status_code
        == 400
    )
    monitoring = client.post(
        f"/api/v1/loans/admin/loans/{loan.pk}/monitoring/",
        data={"frequency": "Quarterly", "focus": "Order intake and cash generation."},
        content_type="application/json",
    )
    assert monitoring.status_code == 200, monitoring.content
    apps.get_model("entities", "BorrowerFinancialYear").objects.create(
        borrower=borrower,
        year=2025,
        period_end="2025-12-31",
        currency="CHF",
        revenue_minor=1_000_000_00,
        operating_profit_minor=100_000_00,
        total_assets_minor=900_000_00,
        equity_minor=300_000_00,
        financial_debt_minor=400_000_00,
    )
    publish_loan(PublishLoanCommand(actor=admin_user, loan_id=str(loan.pk)))
    loan.refresh_from_db()

    detail = import_module(
        "backend.apps.marketplace_primary.services"
    ).full_marketplace_listing_payload(loan)

    [recorded] = detail["credit_checks"]
    assert (recorded["name"], recorded["source"]) == ("Company and owners", "Commercial register")
    assert detail["monitoring"] == {
        "frequency": "Quarterly",
        "focus": "Order intake and cash generation.",
    }
    [year] = detail["financial_years"]
    assert (year["year"], year["revenue_minor"], year["materials_costs_minor"]) == (
        2025,
        1_000_000_00,
        None,
    )
    assert detail["debt_facilities"] == []
    assert detail["recovery_stages"] == {"stages": [], "next_step": None}

    removed = client.delete(f"{url}{recorded['id']}/")
    assert removed.status_code == 204
    assert client.get(url).json()["checks"] == []
