"""IP of Webby-Soft SRL. U33-DEC-09: Due / Late from day 15 / Default from day 60, the
contract's own days per loan, and the contract termination as a separate admin event."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.platform_core.domain.loan_status import LoanStatusThresholds
from backend.apps.platform_core.models import AuditEvent, DomainEvent, PlatformSetting
from backend.apps.platform_core.selectors.settings import (
    loan_status_thresholds,
    platform_loan_status_thresholds,
)
from backend.apps.servicing.services import (
    RecordLoanContractTerminationCommand,
    ScanLoanServicingStatusesCommand,
    ServicingValidationError,
    get_loan_repayment_schedule_snapshots,
    get_loan_servicing_status_snapshot,
    record_loan_contract_termination,
    scan_loan_servicing_statuses,
)
from backend.apps.servicing.tests.default_helpers import scan_and_declare
from backend.apps.servicing.tests.test_servicing_repayments import (
    _funded_loan_with_holdings,
    admin_user,
    investor_one,
    investor_two,
)

__all__ = ["admin_user", "investor_one", "investor_two"]

# The first unpaid installment of _funded_loan_with_holdings is due on 28 Feb 2026.
DUE = date(2026, 2, 28)


def _day(days: int) -> date:
    return date.fromordinal(DUE.toordinal() + days)


def _freeze_today(monkeypatch: pytest.MonkeyPatch, today: date) -> None:
    import backend.apps.servicing.services as servicing_services

    noon = datetime(today.year, today.month, today.day, 11, 0, tzinfo=UTC)
    monkeypatch.setattr(servicing_services, "now_utc", lambda: noon)


def _scan(admin: Model, loan: Model, as_of: date) -> str:
    scan_loan_servicing_statuses(
        ScanLoanServicingStatusesCommand(actor=admin, as_of_date=as_of, loan_ids=(str(loan.pk),))
    )
    loan.refresh_from_db()
    return str(cast(Any, loan).status)


def _scan_and_declare(admin: Model, loan: Model, as_of: date) -> str:
    """18.6: the scan stops at Late; then the admin declares Default."""
    scan_and_declare(
        ScanLoanServicingStatusesCommand(actor=admin, as_of_date=as_of, loan_ids=(str(loan.pk),))
    )
    loan.refresh_from_db()
    return str(cast(Any, loan).status)


def _first_row_status(loan: Model, as_of: date) -> str:
    rows = get_loan_repayment_schedule_snapshots(loans=[loan], as_of_date=as_of)[str(loan.pk)]
    return next(row.status for row in rows if row.installment_number == 1)


def _approve_financial_access(investor: Model) -> None:
    now = timezone.now()
    cast(Any, investor).phone_verified_at = now
    investor.save(update_fields=["phone_verified_at"])
    apps.get_model("kyc_compliance", "KycVerificationCase").objects.update_or_create(
        user_id=investor.pk,
        defaults={
            "subject_reference": f"user:{investor.pk}",
            "provider_environment": "test",
            "workflow_id": "test-workflow",
            "vendor_data": f"user:{investor.pk}",
            "status": "approved",
            "decision_at": now,
        },
    )


def _thresholds_url(loan: Model) -> str:
    return f"/api/v1/servicing/admin/loans/{loan.pk}/status-thresholds/"


def _termination_url(loan: Model) -> str:
    return f"/api/v1/servicing/admin/loans/{loan.pk}/contract-termination/"


@pytest.mark.django_db
def test_due_for_14_days_late_from_day_15_default_from_day_60(
    admin_user: Model, investor_one: Model, investor_two: Model
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    assert platform_loan_status_thresholds() == LoanStatusThresholds(15, 60, "platform")

    # Day 14: still Due. The real days past due are kept; the loan is not "late".
    snapshot = get_loan_servicing_status_snapshot(loan=loan, as_of_date=_day(14))
    assert (snapshot.status, snapshot.days_past_due) == ("active", 14)
    assert _first_row_status(loan, _day(14)) == "due"
    assert _scan(admin_user, loan, _day(14)) == "active"

    assert _first_row_status(loan, _day(15)) == "overdue"
    assert _scan(admin_user, loan, _day(15)) == "late"
    assert _scan(admin_user, loan, _day(59)) == "late"
    # 18.6: Default is never automatic: on day 60 the loan stays Late and the admin is asked to
    # decide; the declaration makes it Default.
    assert _scan(admin_user, loan, _day(60)) == "late"
    task = apps.get_model("admin_ops", "AdminTask").objects.get(related_object_id=str(loan.pk))
    assert task.title.startswith("Default can be declared")
    assert _scan_and_declare(admin_user, loan, _day(60)) == "defaulted"
    # Default does not end the contract.
    assert cast(Any, loan).contract_terminated_on is None
    assert (
        not apps.get_model("loans", "LoanEvent")
        .objects.filter(loan=loan, event_type="contract_terminated")
        .exists()
    )


@pytest.mark.django_db
def test_platform_settings_change_the_days_and_unusable_values_fall_back(
    admin_user: Model, investor_one: Model, investor_two: Model
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    for key, value in (
        ("servicing.late_threshold_days", 10),
        ("servicing.default_threshold_days", 30),
    ):
        PlatformSetting.objects.update_or_create(
            key=key, defaults={"value": value, "value_type": "integer"}
        )
    assert loan_status_thresholds(loan) == LoanStatusThresholds(10, 30, "platform")
    assert _scan(admin_user, loan, _day(10)) == "late"

    # Late on or after Default is not a usable pair: the U33-DEC-09 defaults apply.
    PlatformSetting.objects.filter(key="servicing.late_threshold_days").update(value=40)
    assert loan_status_thresholds(loan) == LoanStatusThresholds(15, 60, "platform")


@pytest.mark.django_db
def test_admin_sets_and_clears_the_contract_days_of_a_loan(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _freeze_today(monkeypatch, _day(6))
    client = Client()
    client.force_login(cast(Any, admin_user))

    response = client.post(
        _thresholds_url(loan),
        data={"late_threshold_days": 5, "default_threshold_days": 16, "reason": "Contract §7."},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["threshold_source"] == "loan"
    assert (body["effective_late_threshold_days"], body["effective_default_threshold_days"]) == (
        5,
        16,
    )
    # A direct active loan is checked again at once: day 6 is Late with the contract's days.
    assert body["loan_status"] == "late"
    event = apps.get_model("loans", "LoanEvent").objects.get(
        loan=loan, event_type="status_thresholds_changed"
    )
    assert event.note == "Contract §7."
    assert event.metadata["previous_effective"] == {
        "late_days": 15,
        "default_days": 60,
        "source": "platform",
    }
    assert event.metadata["new"] == {"late_threshold_days": 5, "default_threshold_days": 16}
    assert AuditEvent.objects.filter(
        action="servicing.loan_status_thresholds_changed", target_id=str(loan.pk)
    ).exists()

    detail = client.get(f"/api/v1/loans/admin/loans/{loan.pk}/").json()
    assert (detail["late_threshold_days"], detail["default_threshold_days"]) == (5, 16)
    assert detail["effective_late_threshold_days"] == 5
    assert detail["contract_terminated_on"] is None

    cleared = client.post(
        _thresholds_url(loan),
        data={"late_threshold_days": None, "default_threshold_days": None, "reason": "Error."},
        content_type="application/json",
    )
    assert cleared.status_code == 200
    assert cleared.json()["threshold_source"] == "platform"
    assert cleared.json()["loan_status"] == "active"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("late", "default", "message"),
    [
        (5, None, "Enter both"),
        (16, 16, "before the Default day"),
        (20, 400, None),
    ],
)
def test_contract_days_must_be_a_usable_pair(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
    late: int,
    default: int | None,
    message: str | None,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    client = Client()
    client.force_login(cast(Any, admin_user))
    response = client.post(
        _thresholds_url(loan),
        data={"late_threshold_days": late, "default_threshold_days": default, "reason": "x"},
        content_type="application/json",
    )
    assert response.status_code == 400
    if message:
        assert message in response.json()["detail"]
    loan.refresh_from_db()
    assert cast(Any, loan).late_threshold_days is None


@pytest.mark.django_db
def test_defaulted_loan_keeps_its_days(
    admin_user: Model, investor_one: Model, investor_two: Model
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    assert _scan_and_declare(admin_user, loan, _day(60)) == "defaulted"
    client = Client()
    client.force_login(cast(Any, admin_user))
    response = client.post(
        _thresholds_url(loan),
        data={"late_threshold_days": 30, "default_threshold_days": 90, "reason": "Contract."},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "defaulted cannot change" in response.json()["detail"]


@pytest.mark.django_db
def test_contract_termination_is_a_separate_recorded_stage(
    admin_user: Model,
    investor_one: Model,
    investor_two: Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loan = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    _freeze_today(monkeypatch, _day(70))
    client = Client()
    client.force_login(cast(Any, admin_user))
    payload = {"terminated_on": _day(65).isoformat(), "note": "Termination letter sent."}

    # Not before the loan is late or in default.
    refused = client.post(_termination_url(loan), data=payload, content_type="application/json")
    assert refused.status_code == 400
    assert "late or in default" in refused.json()["detail"]

    assert _scan_and_declare(admin_user, loan, _day(60)) == "defaulted"
    future = client.post(
        _termination_url(loan),
        data={**payload, "terminated_on": _day(71).isoformat()},
        content_type="application/json",
    )
    assert future.status_code == 400

    response = client.post(_termination_url(loan), data=payload, content_type="application/json")
    assert response.status_code == 200, response.content
    assert response.json()["contract_terminated_on"] == _day(65).isoformat()
    loan.refresh_from_db()
    # The status stays Default: termination and recovery are separate stages.
    assert cast(Any, loan).status == "defaulted"
    events = apps.get_model("loans", "LoanEvent").objects.filter(
        loan=loan, event_type="contract_terminated"
    )
    assert events.count() == 1
    assert events.get().note == "Termination letter sent."
    assert DomainEvent.objects.filter(event_type="LoanContractTerminated").count() == 1

    # The same date again changes nothing; another date is refused.
    record_loan_contract_termination(
        RecordLoanContractTerminationCommand(
            actor=admin_user, loan_id=str(loan.pk), terminated_on=_day(65), note="Again."
        )
    )
    assert events.count() == 1
    with pytest.raises(ServicingValidationError, match="already recorded"):
        record_loan_contract_termination(
            RecordLoanContractTerminationCommand(
                actor=admin_user, loan_id=str(loan.pk), terminated_on=_day(66), note="Other."
            )
        )

    # Investors see the date on their investment.
    _approve_financial_access(investor_one)
    investor = Client()
    investor.force_login(cast(Any, investor_one))
    portfolio = investor.get("/api/v1/investor/portal/portfolio/")
    assert portfolio.status_code == 200, portfolio.content
    loans = [holding["loan"] for holding in portfolio.json()["holdings"]]
    assert loans[0]["contract_terminated_on"] == _day(65).isoformat()


@pytest.mark.django_db
def test_existing_contracts_keep_day_5_and_day_16_after_the_migration(
    admin_user: Model, investor_one: Model, investor_two: Model
) -> None:
    """Audit G-01: the data migration gives every loan with a contract its old days."""
    from importlib import import_module

    migration = import_module(
        "backend.apps.loans.migrations.0025_keep_existing_contract_status_days"
    )
    loans_services = import_module("backend.apps.loans.services")
    loans_tests = import_module("backend.apps.loans.tests.test_loans")
    loan_model = apps.get_model("loans", "Loan")
    existing = _funded_loan_with_holdings(admin_user, investor_one, investor_two)
    draft = loans_services.create_loan(
        loans_tests._loan_command(admin_user, loans_tests._borrower(admin_user))
    )
    own_days = loans_services.create_loan(
        loans_tests._loan_command(admin_user, loans_tests._borrower(admin_user))
    )
    loan_model.objects.filter(pk=own_days.pk).update(
        status="active", late_threshold_days=20, default_threshold_days=90
    )

    migration.keep_existing_contract_days(apps, None)

    existing.refresh_from_db()
    draft.refresh_from_db()
    own_days.refresh_from_db()
    days = cast(Any, existing)
    assert (days.late_threshold_days, days.default_threshold_days) == (5, 16)
    assert (draft.late_threshold_days, draft.default_threshold_days) == (None, None)
    assert (own_days.late_threshold_days, own_days.default_threshold_days) == (20, 90)
    event = (
        apps.get_model("loans", "LoanEvent")
        .objects.filter(loan=existing, event_type="status_thresholds_changed")
        .get()
    )
    assert event.metadata["effective"] == {"late_days": 5, "default_days": 16, "source": "loan"}
    # The loan behaves as before U33-DEC-09: Late on day 5, Default on day 16.
    assert _scan(admin_user, existing, _day(4)) == "active"
    assert _scan(admin_user, existing, _day(5)) == "late"
    assert _scan(admin_user, existing, _day(16)) == "late"
    assert _scan_and_declare(admin_user, existing, _day(16)) == "defaulted"
