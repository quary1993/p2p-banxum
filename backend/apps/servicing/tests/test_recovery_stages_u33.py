"""IP of Webby-Soft SRL. U33-DEC-22: recorded recovery stages and the known next step."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, cast

import pytest
from django.db.models import Model
from django.test import Client

from backend.apps.platform_core.models import AuditEvent
from backend.apps.servicing.models import LoanRecoveryStage
from backend.apps.servicing.tests.test_loan_status_thresholds import (
    _approve_financial_access,
    _day,
    _freeze_today,
    _scan_and_declare,
)
from backend.apps.servicing.tests.test_servicing_repayments import (
    _funded_loan_with_holdings,
    admin_user,
    investor_one,
    investor_two,
)

__all__ = ["admin_user", "investor_one", "investor_two"]

pytestmark = pytest.mark.django_db


def _today(monkeypatch: pytest.MonkeyPatch, today: date) -> None:
    import backend.apps.servicing.recovery_stages as stages

    _freeze_today(monkeypatch, today)
    noon = datetime(today.year, today.month, today.day, 11, 0, tzinfo=UTC)
    monkeypatch.setattr(stages, "now_utc", lambda: noon)


def _url(loan: Model) -> str:
    return f"/api/v1/servicing/admin/loans/{loan.pk}/recovery-stages/"


def _admin(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def _record(client: Client, loan: Model, **data: Any) -> Any:
    return client.post(_url(loan), data=data, content_type="application/json")


def _portfolio_loan_holding(investor: Model) -> dict[str, Any]:
    _approve_financial_access(investor)
    client = Client()
    client.force_login(cast(Any, investor))
    response = client.get("/api/v1/investor/portal/portfolio/")
    assert response.status_code == 200, response.content
    return cast(dict[str, Any], response.json()["holdings"][0])


def test_admin_records_real_stages_and_the_next_step_investors_see_them(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _today(monkeypatch, _day(70))
    client = _admin(admin_user)

    # Not for a performing loan.
    refused = _record(
        client, loan, status="done", title="Reminder sent", occurred_on=_day(3).isoformat()
    )
    assert refused.status_code == 400
    assert "late, in default or written off" in refused.json()["detail"]

    assert _scan_and_declare(admin_user, loan, _day(60)) == "defaulted"
    reminder = _record(
        client,
        loan,
        status="done",
        title="Reminder sent",
        occurred_on=_day(3).isoformat(),
        investor_note="Banxum reminded the borrower in writing.",
    )
    assert reminder.status_code == 201, reminder.content
    notice = _record(
        client, loan, status="done", title="Formal notice", occurred_on=_day(20).isoformat()
    )
    assert notice.status_code == 201
    first_next = _record(client, loan, status="next", title="Sale of the security")
    assert first_next.status_code == 201
    second_next = _record(
        client,
        loan,
        status="next",
        title="Auction of the property",
        occurred_on=_day(90).isoformat(),
        investor_note="The auction date is set by the court.",
    )
    assert second_next.status_code == 201

    # The first next step was replaced, not deleted.
    replaced = LoanRecoveryStage.objects.get(id=first_next.json()["id"])
    assert (replaced.removed_reason, replaced.removed_at is not None) == ("Replaced", True)
    listed = client.get(_url(loan)).json()["stages"]
    assert len(listed) == 4
    assert AuditEvent.objects.filter(action="servicing.recovery_stage_recorded").count() == 4

    holding = _portfolio_loan_holding(investor_one)
    assert [stage["title"] for stage in holding["recovery_stages"]] == [
        "Reminder sent",
        "Formal notice",
    ]
    assert (
        holding["recovery_stages"][0]["investor_note"] == "Banxum reminded the borrower in writing."
    )
    assert holding["recovery_next_step"] == {
        "title": "Auction of the property",
        "recovery_result": "",
        "occurred_on": _day(90).isoformat(),
        "investor_note": "The auction date is set by the court.",
    }

    # A wrong entry is removed with a reason and disappears for investors.
    removed = client.post(
        f"{_url(loan)}{notice.json()['id']}/remove/",
        data={"reason": "Wrong loan."},
        content_type="application/json",
    )
    assert removed.status_code == 200, removed.content
    assert removed.json()["removed_reason"] == "Wrong loan."
    # The admin list keeps the removed entry with who recorded and who removed it.
    admin_email = str(getattr(admin_user, "email", ""))
    [listed] = [
        stage
        for stage in client.get(_url(loan)).json()["stages"]
        if stage["id"] == notice.json()["id"]
    ]
    assert (listed["recorded_by_email"], listed["removed_by_email"]) == (admin_email, admin_email)
    holding = _portfolio_loan_holding(investor_one)
    assert [stage["title"] for stage in holding["recovery_stages"]] == ["Reminder sent"]
    again = client.post(
        f"{_url(loan)}{notice.json()['id']}/remove/",
        data={"reason": "Again."},
        content_type="application/json",
    )
    assert again.status_code == 400


def test_dates_follow_what_really_happened(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _today(monkeypatch, _day(70))
    client = _admin(admin_user)
    assert _scan_and_declare(admin_user, loan, _day(60)) == "defaulted"

    no_date = _record(client, loan, status="done", title="Formal notice")
    future = _record(
        client, loan, status="done", title="Formal notice", occurred_on=_day(71).isoformat()
    )
    past_next = _record(client, loan, status="next", title="Sale", occurred_on=_day(69).isoformat())
    no_title = _record(client, loan, status="done", title="  ", occurred_on=_day(10).isoformat())

    assert no_date.status_code == 400
    assert "date of a stage that happened" in no_date.json()["detail"]
    assert future.status_code == 400
    assert past_next.status_code == 400
    assert no_title.status_code == 400
    assert not LoanRecoveryStage.objects.exists()
    # Only admins.
    assert (
        _record(
            _admin(investor_one), loan, status="done", title="X", occurred_on=_day(10).isoformat()
        ).status_code
        == 403
    )


def test_standard_stage_names_and_the_result_of_recovery_closed(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Q16: a standard name or an own title; "Recovery closed" states the result."""
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _today(monkeypatch, _day(70))
    client = _admin(admin_user)
    assert _scan_and_declare(admin_user, loan, _day(60)) == "defaulted"
    day = _day(65).isoformat()

    standard = _record(client, loan, status="done", standard_key="formal_notice", occurred_on=day)
    own = _record(client, loan, status="done", title="Call with the borrower", occurred_on=day)
    unknown = _record(client, loan, status="done", standard_key="unknown", occurred_on=day)
    no_result = _record(
        client, loan, status="done", standard_key="recovery_closed", occurred_on=day
    )
    result_elsewhere = _record(
        client, loan, status="done", title="Note", recovery_result="full", occurred_on=day
    )
    closed = _record(
        client,
        loan,
        status="done",
        standard_key="recovery_closed",
        recovery_result="partial",
        occurred_on=day,
    )

    assert standard.status_code == 201, standard.content
    assert (standard.json()["title"], standard.json()["standard_key"]) == (
        "Formal notice",
        "formal_notice",
    )
    assert (own.json()["title"], own.json()["standard_key"]) == ("Call with the borrower", "")
    assert unknown.status_code == 400
    assert no_result.status_code == 400
    assert "states the result" in no_result.json()["detail"]
    assert result_elsewhere.status_code == 400
    assert closed.status_code == 201, closed.content
    holding = _portfolio_loan_holding(investor_one)
    last = holding["recovery_stages"][-1]
    assert (last["title"], last["recovery_result"]) == ("Recovery closed", "partial")
