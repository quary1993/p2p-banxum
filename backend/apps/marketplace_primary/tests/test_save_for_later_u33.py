"""IP of Webby-Soft SRL. U33-DEC-18: Save for later and the 7, 3 and 1 day closing reminders."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
from django.apps import apps
from django.db.models import Model

from backend.apps.marketplace_primary.models import (
    SavedOpportunity,
    SavedOpportunityReminder,
)
from backend.apps.marketplace_primary.saved_opportunities import (
    SAVED_REMINDER_TOPIC,
    send_saved_opportunity_reminders,
)
from backend.apps.marketplace_primary.tests.test_coming_soon_u33 import (
    _client,
    _draft,
    _make_investor,
    _publish,
    admin_user,
    investor,
)
from backend.apps.platform_core.models import OutboxMessage

__all__ = ["admin_user", "investor"]

pytestmark = pytest.mark.django_db


def _open_loan(admin_user: Model, title: str = "Saved bridge loan") -> Model:
    loan = _draft(admin_user, title=title)
    _publish(admin_user, loan)
    return loan


def _save(user: Model, loan: Model, amount_minor: int | None = None) -> Any:
    return _client(user).put(
        f"/api/v1/marketplace/primary/loans/{loan.pk}/saved/",
        data={"amount_minor": amount_minor},
        content_type="application/json",
    )


def _saved_list(user: Model) -> list[dict[str, Any]]:
    response = _client(user).get("/api/v1/marketplace/primary/saved/")
    assert response.status_code == 200, response.content
    return list(response.json()["saved"])


def _deadline(loan: Model) -> date:
    loan.refresh_from_db()
    return loan.funding_deadline  # type: ignore[attr-defined, no-any-return]


def _run_on(day: date) -> dict[str, Any]:
    # 07:00 UTC is 08:00 or 09:00 in Zurich: the same business day.
    return send_saved_opportunity_reminders(as_of=datetime.combine(day, time(7, 0), tzinfo=UTC))


def _saved_on(loan: Model, user: Model, day: date) -> None:
    SavedOpportunity.objects.filter(loan_id=loan.pk, investor_user_id=user.pk).update(
        created_at=datetime.combine(day, time(9, 0), tzinfo=UTC)
    )


def _reminders(loan: Model, user: Model) -> list[tuple[int, str]]:
    return list(
        SavedOpportunityReminder.objects.filter(loan_id=loan.pk, investor_user_id=user.pk)
        .order_by("-days_before")
        .values_list("days_before", "status")
    )


def test_save_with_or_without_an_amount_change_it_and_remove_it(
    admin_user: Model, investor: Model
) -> None:
    loan = _open_loan(admin_user)

    saved = _save(investor, loan)
    assert saved.status_code == 200, saved.content
    assert saved.json()["amount_minor"] is None
    assert saved.json()["amount_check"] == "none"
    assert saved.json()["is_open"] is True

    changed = _save(investor, loan, 12_500_00)
    assert changed.json()["amount_minor"] == 12_500_00
    assert changed.json()["amount_check"] == "ok"
    [row] = _saved_list(investor)
    assert (row["loan_id"], row["amount_minor"], row["currency"]) == (
        str(loan.pk),
        12_500_00,
        "CHF",
    )
    assert SavedOpportunity.objects.count() == 1
    # Saving reserves nothing: no order and no change to the loan.
    assert not apps.get_model("marketplace_primary", "PrimaryInvestmentOrder").objects.exists()

    removed = _client(investor).delete(f"/api/v1/marketplace/primary/loans/{loan.pk}/saved/")
    assert removed.status_code == 204
    assert _saved_list(investor) == []
    assert (
        _client(investor).delete(f"/api/v1/marketplace/primary/loans/{loan.pk}/saved/").status_code
        == 204
    )


def test_an_amount_that_does_not_fit_or_a_closed_opportunity_is_refused(
    admin_user: Model, investor: Model
) -> None:
    loan = _open_loan(admin_user)
    draft = _draft(admin_user, title="Not open yet")

    below = _save(investor, loan, 1_00)
    above = _save(investor, loan, 200_000_00)
    not_open = _save(investor, draft)

    assert below.status_code == 400
    assert "minimum investment" in below.json()["detail"]
    assert above.status_code == 400
    assert "available to invest" in above.json()["detail"]
    assert not_open.status_code == 400
    assert "not open for investment" in not_open.json()["detail"]
    assert not SavedOpportunity.objects.exists()


def test_on_return_a_saved_amount_that_no_longer_fits_is_explained_not_changed(
    admin_user: Model, investor: Model
) -> None:
    loan = _open_loan(admin_user)
    assert _save(investor, loan, 20_000_00).status_code == 200
    loan_model = apps.get_model("loans", "Loan")

    loan_model.objects.filter(pk=loan.pk).update(committed_principal_minor=90_000_00)
    [row] = _saved_list(investor)
    assert row["amount_check"] == "above_available"
    assert row["available_minor"] == 10_000_00
    assert row["amount_minor"] == 20_000_00

    loan_model.objects.filter(pk=loan.pk).update(status="funded")
    [row] = _saved_list(investor)
    assert (row["is_open"], row["amount_check"], row["amount_minor"]) == (
        False,
        "closed",
        20_000_00,
    )
    assert row["minimum_investment_minor"] is None


def test_reminders_7_3_and_1_day_before_closing_once_each(
    admin_user: Model, investor: Model
) -> None:
    loan = _open_loan(admin_user)
    assert _save(investor, loan, 10_000_00).status_code == 200
    deadline = _deadline(loan)
    _saved_on(loan, investor, deadline - timedelta(days=20))

    assert _run_on(deadline - timedelta(days=8))["reminders_sent"] == 0
    assert _run_on(deadline - timedelta(days=7))["reminders_sent"] == 1
    assert _run_on(deadline - timedelta(days=7))["reminders_sent"] == 0
    assert _run_on(deadline - timedelta(days=3))["reminders_sent"] == 1
    assert _run_on(deadline - timedelta(days=1))["reminders_sent"] == 1
    assert _run_on(deadline)["reminders_sent"] == 0

    assert _reminders(loan, investor) == [(7, "sent"), (3, "sent"), (1, "sent")]
    subjects = [
        message.payload["subject"]
        for message in OutboxMessage.objects.filter(topic=SAVED_REMINDER_TOPIC).order_by("id")
    ]
    assert subjects == [
        "Funding closes in 7 days: Saved bridge loan",
        "Funding closes in 3 days: Saved bridge loan",
        "Funding closes tomorrow: Saved bridge loan",
    ]
    message = OutboxMessage.objects.filter(topic=SAVED_REMINDER_TOPIC).first()
    assert message is not None
    assert message.payload["user_id"] == str(investor.pk)
    assert ["Your saved amount", "CHF 10'000.00"] in message.payload["data_rows"]
    topics = [
        row["topic"]
        for row in _client(investor)
        .get("/api/v1/investor/portal/notifications/")
        .json()["notifications"]
    ]
    assert SAVED_REMINDER_TOPIC in topics


def test_no_retroactive_reminder_and_one_reminder_after_a_missed_run(
    admin_user: Model, investor: Model
) -> None:
    late_saver = _make_investor("late-saver@example.test")
    loan = _open_loan(admin_user)
    assert _save(investor, loan).status_code == 200
    assert _save(late_saver, loan).status_code == 200
    deadline = _deadline(loan)
    _saved_on(loan, investor, deadline - timedelta(days=20))
    _saved_on(loan, late_saver, deadline - timedelta(days=5))

    # A missed run: on day 2 before closing, the 7 and 3 day milestones have both come.
    result = _run_on(deadline - timedelta(days=2))

    assert result["reminders_sent"] == 2
    assert _reminders(loan, investor) == [(7, "skipped"), (3, "sent")]
    # Saved 5 days before closing: the 7 day milestone was before saving and is never sent.
    assert _reminders(loan, late_saver) == [(3, "sent")]


def test_no_reminder_after_removal_or_when_the_opportunity_is_no_longer_open(
    admin_user: Model, investor: Model
) -> None:
    removed = _open_loan(admin_user, title="Removed")
    closed = _open_loan(admin_user, title="Closed")
    for loan in (removed, closed):
        assert _save(investor, loan).status_code == 200
        _saved_on(loan, investor, _deadline(loan) - timedelta(days=20))
    _client(investor).delete(f"/api/v1/marketplace/primary/loans/{removed.pk}/saved/")
    apps.get_model("loans", "Loan").objects.filter(pk=closed.pk).update(status="funded")

    assert _run_on(_deadline(removed) - timedelta(days=7))["reminders_sent"] == 0
    assert not OutboxMessage.objects.filter(topic=SAVED_REMINDER_TOPIC).exists()


def test_a_new_funding_deadline_schedules_the_reminders_again(
    admin_user: Model, investor: Model
) -> None:
    loan = _open_loan(admin_user)
    assert _save(investor, loan).status_code == 200
    deadline = _deadline(loan)
    _saved_on(loan, investor, deadline - timedelta(days=20))
    assert _run_on(deadline - timedelta(days=7))["reminders_sent"] == 1

    later = deadline + timedelta(days=10)
    apps.get_model("loans", "Loan").objects.filter(pk=loan.pk).update(funding_deadline=later)

    assert _run_on(later - timedelta(days=7))["reminders_sent"] == 1
    assert SavedOpportunityReminder.objects.filter(funding_deadline=later, days_before=7).exists()


def test_saved_list_is_ordered_by_closing_date(admin_user: Model, investor: Model) -> None:
    """C05: "Closing soonest" orders the saved group (Overview panel), whatever the saving order."""
    later = _open_loan(admin_user, title="Closes later")
    sooner = _open_loan(admin_user, title="Closes sooner")
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(pk=later.pk).update(
        funding_deadline=_deadline(sooner) + timedelta(days=5)
    )
    # Saved first, so "newest saved first" would list it last.
    assert _save(investor, sooner).status_code == 200
    assert _save(investor, later).status_code == 200

    titles = [item["title"] for item in _saved_list(investor)]

    assert titles == ["Closes sooner", "Closes later"]
