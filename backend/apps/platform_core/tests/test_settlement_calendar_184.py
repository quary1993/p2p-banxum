"""IP of Webby-Soft SRL. 18.4 (F17): CHF and EUR settlement calendars kept by operations."""

from __future__ import annotations

from datetime import date, datetime, time
from importlib import import_module
from types import SimpleNamespace
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from freezegun import freeze_time

from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import (
    AuditEvent,
    OutboxMessage,
    SettlementCalendarYear,
    SettlementHoliday,
)
from backend.apps.platform_core.services.balance_schedule import BalanceScheduler
from backend.apps.platform_core.services.scheduled_jobs import (
    DEFAULT_SCHEDULED_JOB_NAMES,
    SETTLEMENT_CALENDAR_CHECK_JOB,
)
from backend.apps.platform_core.services.settlement_calendar import (
    AddSettlementHolidayCommand,
    ConfirmSettlementCalendarYearCommand,
    RemoveSettlementHolidayCommand,
    SettlementCalendarAuthorizationError,
    SettlementCalendarValidationError,
    add_settlement_holiday,
    calendar_year_payload,
    check_settlement_calendars,
    confirm_settlement_calendar_year,
    ensure_calendar_year,
    remove_settlement_holiday,
    settlement_calendar,
)


@pytest.fixture
def admin_user() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="calendar-admin@example.test",
            password="AdminPass123!",
            full_name="Calendar Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


def _at(value: date, hour: int = 9) -> datetime:
    return datetime.combine(value, time(hour), tzinfo=business_timezone())


@pytest.mark.django_db
def test_a_year_is_preloaded_once_from_the_rule_list() -> None:
    payload = calendar_year_payload("CHF", 2027)
    assert payload["stored"] is False
    assert [day["date"] for day in payload["days"]][:2] == [date(2027, 1, 1), date(2027, 1, 2)]

    calendar_year, created = ensure_calendar_year("CHF", 2027)
    again, created_again = ensure_calendar_year("chf", 2027)
    assert (created, created_again, again.id) == (True, False, calendar_year.id)
    assert SettlementHoliday.objects.filter(currency="CHF", date__year=2027).count() == 10
    assert calendar_year_payload("CHF", 2027)["stored"] is True
    with pytest.raises(SettlementCalendarValidationError, match="Use CHF or EUR"):
        ensure_calendar_year("USD", 2027)


@pytest.mark.django_db
def test_admin_changes_drive_the_settlement_days(admin_user: Model) -> None:
    # 24 December is a value day by rule; operations close it for 2026.
    assert settlement_calendar("CHF").is_settlement_day(date(2026, 12, 24))
    add_settlement_holiday(
        AddSettlementHolidayCommand(
            actor=admin_user, currency="CHF", date=date(2026, 12, 24), name="Bank closed"
        )
    )
    assert not settlement_calendar("CHF").is_settlement_day(date(2026, 12, 24))
    # Whit Monday opened by mistake in the rule list? Operations can open a day with a reason.
    remove_settlement_holiday(
        RemoveSettlementHolidayCommand(
            actor=admin_user, currency="CHF", date=date(2026, 5, 25), reason="Bank confirmed."
        )
    )
    assert settlement_calendar("CHF").is_settlement_day(date(2026, 5, 25))
    assert settlement_calendar("EUR").is_settlement_day(date(2026, 12, 24))

    with pytest.raises(SettlementCalendarValidationError, match="never settlement days"):
        add_settlement_holiday(
            AddSettlementHolidayCommand(
                actor=admin_user, currency="CHF", date=date(2026, 12, 27), name="Sunday"
            )
        )
    with pytest.raises(SettlementCalendarValidationError, match="already a closed day"):
        add_settlement_holiday(
            AddSettlementHolidayCommand(
                actor=admin_user, currency="CHF", date=date(2026, 12, 25), name="Again"
            )
        )
    with pytest.raises(SettlementCalendarValidationError, match="is not a closed day"):
        remove_settlement_holiday(
            RemoveSettlementHolidayCommand(
                actor=admin_user, currency="CHF", date=date(2026, 12, 23), reason="No."
            )
        )
    investor = get_user_model().objects.create_user(
        email="calendar-investor@example.test",
        full_name="Calendar Investor",
        account_type="natural_person_lender",
        status="active",
    )
    with pytest.raises(SettlementCalendarAuthorizationError):
        add_settlement_holiday(
            AddSettlementHolidayCommand(
                actor=investor, currency="CHF", date=date(2026, 12, 23), name="No"
            )
        )


@pytest.mark.django_db
def test_return_dates_follow_the_stored_calendar(admin_user: Model) -> None:
    # Value date Monday 2026-09-07: day 57 is Tuesday 11-03.
    lot = SimpleNamespace(
        withdrawal_deadline_at=datetime.combine(
            date(2026, 11, 6), time.min, tzinfo=business_timezone()
        ),
        return_after_days=56,
        currency_id="CHF",
    )
    assert BalanceScheduler().schedule(lot).return_date == date(2026, 11, 3)
    add_settlement_holiday(
        AddSettlementHolidayCommand(
            actor=admin_user, currency="CHF", date=date(2026, 11, 3), name="Bank closed"
        )
    )
    schedule = BalanceScheduler().schedule(lot)
    assert (schedule.return_date, schedule.last_day) == (date(2026, 11, 2), date(2026, 11, 1))


@pytest.mark.django_db
def test_the_daily_check_preloads_and_alerts_while_next_year_is_not_confirmed(
    admin_user: Model,
) -> None:
    assert SETTLEMENT_CALENDAR_CHECK_JOB in DEFAULT_SCHEDULED_JOB_NAMES
    october = check_settlement_calendars(actor=admin_user, as_of=_at(date(2026, 10, 15)))
    assert sorted(october["preloaded"]) == ["CHF:2026", "CHF:2027", "EUR:2026", "EUR:2027"]
    assert october["alerts"] == []
    assert SettlementCalendarYear.objects.count() == 4

    november = check_settlement_calendars(actor=admin_user, as_of=_at(date(2026, 11, 2)))
    assert sorted(november["alerts"]) == ["CHF:2027", "EUR:2027"]
    assert check_settlement_calendars(actor=admin_user, as_of=_at(date(2026, 11, 3)))[
        "alerts"
    ] == []
    tasks = apps.get_model("admin_ops", "AdminTask").objects.filter(
        task_type="settlement_calendar"
    )
    assert sorted(task.related_object_id for task in tasks) == ["CHF:2027", "EUR:2027"]
    assert OutboxMessage.objects.filter(topic="email.operations_alert").count() == 2

    confirmed = confirm_settlement_calendar_year(
        ConfirmSettlementCalendarYearCommand(
            actor=admin_user, currency="CHF", year=2027, note="Checked against the SIX list."
        )
    )
    assert confirmed["confirmed_at"] is not None
    chf_task = tasks.get(related_object_id="CHF:2027")
    assert chf_task.status == "resolved"
    assert tasks.get(related_object_id="EUR:2027").status == "open"


@pytest.mark.django_db
def test_admin_calendar_api(client: Client, admin_user: Model) -> None:
    client.force_login(cast(Any, admin_user))
    year = client.get("/api/v1/admin/settlement-calendars/?currency=EUR&year=2027")
    assert year.status_code == 200
    assert year.json()["stored"] is False
    assert len(year.json()["days"]) == 6

    added = client.post(
        "/api/v1/admin/settlement-calendars/days/",
        data={"currency": "EUR", "date": "2027-12-24", "name": "Bank closed"},
        content_type="application/json",
    )
    assert added.status_code == 200, added.json()
    assert added.json()["stored"] is True
    assert {"date": "2027-12-24", "name": "Bank closed"}.items() <= next(
        day for day in added.json()["days"] if day["date"] == "2027-12-24"
    ).items()
    removed = client.post(
        "/api/v1/admin/settlement-calendars/days/remove/",
        data={"currency": "EUR", "date": "2027-12-24", "reason": "Open after all."},
        content_type="application/json",
    )
    assert removed.status_code == 200
    day = next(day for day in removed.json()["days"] if day["date"] == "2027-12-24")
    assert (day["is_active"], day["removal_reason"]) == (False, "Open after all.")
    bad = client.post(
        "/api/v1/admin/settlement-calendars/days/",
        data={"currency": "USD", "date": "2027-12-23", "name": "No"},
        content_type="application/json",
    )
    assert bad.status_code == 400
    confirmed = client.post(
        "/api/v1/admin/settlement-calendars/confirm/",
        data={"currency": "EUR", "year": 2027},
        content_type="application/json",
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["confirmed_at"]

    anonymous = Client()
    assert (
        anonymous.get("/api/v1/admin/settlement-calendars/?currency=EUR&year=2027").status_code
        in {401, 403}
    )


@pytest.mark.django_db
def test_the_scheduled_job_runs_the_check(admin_user: Model) -> None:
    jobs = import_module("backend.apps.platform_core.services.scheduled_jobs")
    with freeze_time(_at(date(2026, 11, 20), 2)):
        result = jobs.run_scheduled_jobs(
            jobs.RunScheduledJobsCommand(
                job_names=(SETTLEMENT_CALENDAR_CHECK_JOB,), actor=admin_user, force=True
            )
        )
    summary = result.results[0].summary
    assert result.results[0].status == "succeeded", result.results[0].error
    assert sorted(summary["alerts"]) == ["CHF:2027", "EUR:2027"]
    assert summary["as_of_date"] == date(2026, 11, 20).isoformat()


@pytest.mark.django_db
def test_a_changed_day_clears_the_confirmation_and_opens_the_task_again(
    admin_user: Model,
) -> None:
    """Audit S3-4: a confirmation covers the days as they were. A later change removes it, opens
    the task again at once and sends one new alert for the new revision."""
    tasks = apps.get_model("admin_ops", "AdminTask").objects.filter(
        task_type="settlement_calendar", related_object_id="CHF:2027"
    )
    check_settlement_calendars(actor=admin_user, as_of=_at(date(2026, 11, 2)))
    confirm_settlement_calendar_year(
        ConfirmSettlementCalendarYearCommand(actor=admin_user, currency="CHF", year=2027)
    )
    assert tasks.get().status == "resolved"
    alerts_before = OutboxMessage.objects.filter(topic="email.operations_alert").count()

    changed = add_settlement_holiday(
        AddSettlementHolidayCommand(
            actor=admin_user, currency="CHF", date=date(2027, 12, 24), name="Bank closed"
        )
    )
    assert changed["confirmed_at"] is None
    assert (changed["revision"], changed["reconfirmation_needed_since"] is not None) == (1, True)
    assert tasks.get().status == "open"
    assert "changed after it was confirmed" in tasks.get().notes
    assert OutboxMessage.objects.filter(topic="email.operations_alert").count() == alerts_before + 1
    cleared = AuditEvent.objects.get(action="settlement_calendar.confirmation_cleared")
    assert cleared.metadata["previous_confirmation"]["confirmed_by_admin_id"] == str(admin_user.pk)
    # The day's check finds the open task: no second alert for the same revision.
    assert (
        check_settlement_calendars(actor=admin_user, as_of=_at(date(2026, 11, 3)))["alerts"] == []
    )

    confirmed = confirm_settlement_calendar_year(
        ConfirmSettlementCalendarYearCommand(actor=admin_user, currency="CHF", year=2027)
    )
    assert confirmed["confirmed_at"] is not None
    assert confirmed["reconfirmation_needed_since"] is None
    assert tasks.get().status == "resolved"
    # Removing the day again changes the confirmed year once more.
    reopened = remove_settlement_holiday(
        RemoveSettlementHolidayCommand(
            actor=admin_user, currency="CHF", date=date(2027, 12, 24), reason="The bank is open."
        )
    )
    assert (reopened["confirmed_at"], reopened["revision"]) == (None, 2)
    assert tasks.count() == 1 and tasks.get().status == "open"
    assert OutboxMessage.objects.filter(topic="email.operations_alert").count() == alerts_before + 2


@pytest.mark.django_db
def test_a_change_in_the_current_year_is_alerted_outside_the_november_window(
    admin_user: Model,
) -> None:
    """Audit S3-4: a year that was confirmed and then changed is followed at any date."""
    ensure_calendar_year("EUR", 2026)
    confirm_settlement_calendar_year(
        ConfirmSettlementCalendarYearCommand(actor=admin_user, currency="EUR", year=2026)
    )
    # A year that was never confirmed and only changes is not an alert before November.
    add_settlement_holiday(
        AddSettlementHolidayCommand(
            actor=admin_user, currency="CHF", date=date(2026, 6, 1), name="Local closing"
        )
    )
    with freeze_time(_at(date(2026, 3, 2))):
        add_settlement_holiday(
            AddSettlementHolidayCommand(
                actor=admin_user, currency="EUR", date=date(2026, 6, 1), name="TARGET closed"
            )
        )
    tasks = apps.get_model("admin_ops", "AdminTask").objects.filter(task_type="settlement_calendar")
    assert [(task.related_object_id, task.status) for task in tasks] == [("EUR:2026", "open")]
    # The task was closed in the database by an older path: the March check opens it again.
    tasks.update(status="resolved")
    march = check_settlement_calendars(actor=admin_user, as_of=_at(date(2026, 3, 3)))
    assert march["alerts"] == ["EUR:2026"]
    assert tasks.get().status == "open"


@pytest.mark.django_db
def test_the_calendar_task_cannot_be_closed_without_the_confirmation(admin_user: Model) -> None:
    """Audit S3-4: the generic task action does not close the task of an unconfirmed year."""
    admin_ops: Any = import_module("backend.apps.admin_ops.services")
    check_settlement_calendars(actor=admin_user, as_of=_at(date(2026, 11, 2)))
    task = apps.get_model("admin_ops", "AdminTask").objects.get(
        task_type="settlement_calendar", related_object_id="CHF:2027"
    )
    for status in ("resolved", "cancelled"):
        with pytest.raises(admin_ops.AdminTaskValidationError, match="Confirm the year"):
            admin_ops.update_admin_task(
                admin_ops.UpdateAdminTaskCommand(
                    actor=admin_user, task_id=str(task.id), status=status, completion_note="Done."
                )
            )
    # Work on the task stays possible.
    admin_ops.update_admin_task(
        admin_ops.UpdateAdminTaskCommand(
            actor=admin_user, task_id=str(task.id), status="in_progress"
        )
    )
    confirm_settlement_calendar_year(
        ConfirmSettlementCalendarYearCommand(actor=admin_user, currency="CHF", year=2027)
    )
    task.refresh_from_db()
    assert task.status == "resolved"
