"""IP of Webby-Soft SRL. The admin loan history: loan events and loan audit entries."""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.db.models import Model
from django.test import Client

from backend.apps.loans.models import Loan
from backend.apps.loans.services import create_loan
from backend.apps.loans.tests.test_loans import _borrower, _loan_command, admin_user

__all__ = ["admin_user"]

pytestmark = pytest.mark.django_db


def _client(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def _history(user: Model, loan: Loan) -> Any:
    return _client(user).get(f"/api/v1/loans/admin/loans/{loan.pk}/history/")


def test_the_history_merges_events_and_changes_newest_first(admin_user: Model) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    client = _client(admin_user)
    added = client.post(
        f"/api/v1/loans/admin/loans/{loan.pk}/securities/",
        data={"security_type": "equipment", "value_minor": 400_00},
        content_type="application/json",
    )
    assert added.status_code == 201, added.content

    response = _history(admin_user, loan)

    assert response.status_code == 200, response.content
    entries = response.json()["entries"]
    codes = [entry["code"] for entry in entries]
    # The security change comes from the audit; the creation from the loan event, shown once.
    assert codes[0] == "loan.security_added"
    assert codes.count("created") == 1
    assert "loan.created" not in codes
    added_entry = entries[0]
    assert added_entry["kind"] == "change"
    assert added_entry["actor"] == str(getattr(admin_user, "email", ""))
    assert added_entry["details"]["security_type"] == "equipment"
    times = [entry["occurred_at"] for entry in entries]
    assert times == sorted(times, reverse=True)


def test_only_admins_read_the_history(admin_user: Model, django_user_model: Any) -> None:
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    investor = django_user_model.objects.create_user(email="history@example.test", full_name="I")

    assert _history(investor, loan).status_code == 403
