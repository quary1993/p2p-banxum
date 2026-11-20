"""IP of Webby-Soft SRL. Audit S5-7: every new direct loan uses the 18.6 interest engine.

The earlier monthly schedule stays for the loans that existed at the release (migration 0029)
and for an explicit import of a contract signed before the engine. It is not the default of the
model, the service command or the admin API, and the API cannot choose it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any, cast

import pytest
from django.apps import apps
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.loans.models import CollateralType, InterestConvention, LoanPurpose, RiskRating
from backend.apps.loans.services import (
    ENGINE_CUTOVER_DATE,
    LoanValidationError,
    create_loan,
)
from backend.apps.loans.tests.test_loans import (  # noqa: F401
    _borrower,
    _loan_command,
    admin_user,
)


def test_the_model_default_is_the_engine() -> None:
    loan = apps.get_model("loans", "Loan")()
    assert cast(Any, loan).interest_convention == InterestConvention.ACT_365_FIXED


@pytest.mark.django_db
def test_the_service_command_creates_an_engine_loan_by_default(admin_user: Model) -> None:  # noqa: F811
    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))

    assert loan.interest_convention == InterestConvention.ACT_365_FIXED
    first = loan.installments.order_by("installment_number").first()
    assert first is not None and "interest_start" in dict(first.metadata or {})


@pytest.mark.django_db
def test_the_earlier_schedule_needs_a_contract_signed_before_the_engine(admin_user: Model) -> None:  # noqa: F811
    command = replace(
        _loan_command(admin_user, _borrower(admin_user)),
        interest_convention=InterestConvention.LEGACY_MONTHLY,
    )

    for signed_on in (None, ENGINE_CUTOVER_DATE, ENGINE_CUTOVER_DATE + timedelta(days=30)):
        with pytest.raises(LoanValidationError, match="signed before 19 November 2026"):
            create_loan(replace(command, pre_cutover_contract_signed_on=signed_on))

    imported = create_loan(replace(command, pre_cutover_contract_signed_on=date(2026, 9, 30)))
    assert imported.interest_convention == InterestConvention.LEGACY_MONTHLY
    event = imported.events.get(event_type="created")
    assert event.metadata["pre_cutover_contract_signed_on"] == "2026-09-30"
    assert event.metadata["interest_convention"] == InterestConvention.LEGACY_MONTHLY


@pytest.mark.django_db
def test_the_admin_api_cannot_choose_the_earlier_schedule(admin_user: Model) -> None:  # noqa: F811
    client = Client()
    client.force_login(cast(Any, admin_user))
    borrower = _borrower(admin_user)
    payload = {
        "borrower_id": str(borrower.pk),
        "title": "API Loan",
        "investor_summary": "API-created loan.",
        "purpose": LoanPurpose.WORKING_CAPITAL,
        "principal_minor": 1500_00,
        "currency": "CHF",
        "interest_rate_bps": 1000,
        "term_months": 6,
        "repayment_type": "equal_installments",
        "funding_deadline": (timezone.localdate() + timedelta(days=20)).isoformat(),
        "collateral_type": CollateralType.REAL_ESTATE,
        "collateral_value_minor": 3000_00,
        "risk_rating": RiskRating.A,
    }

    refused = client.post(
        "/api/v1/loans/admin/loans/",
        data={**payload, "interest_convention": "legacy_monthly"},
        content_type="application/json",
    )
    created = client.post(
        "/api/v1/loans/admin/loans/", data=payload, content_type="application/json"
    )

    assert refused.status_code == 400
    assert "interest_convention" in refused.json()
    assert created.status_code == 201
    loan = apps.get_model("loans", "Loan").objects.get(id=created.json()["id"])
    assert cast(Any, loan).interest_convention == InterestConvention.ACT_365_FIXED


@pytest.mark.django_db
def test_the_qa_catalogue_states_the_earlier_schedule_explicitly(settings: Any) -> None:
    """The QA seed still models contracts from before the engine (until the reseed at the end
    of Phase 18) and records that on every direct loan it creates."""
    from django.contrib.auth import get_user_model

    from backend.apps.platform_core.services.qa_seed import seed_qa_starting_point

    settings.ENVIRONMENT = "local"
    settings.IS_PRODUCTION = False
    settings.COMMUNICATIONS_EMAIL_PROVIDER = "mock"
    actor = get_user_model().objects.create_superuser(
        email="qa.operator@example.test", full_name="QA Operator", password=None
    )
    seed_qa_starting_point(actor=actor)

    direct = apps.get_model("loans", "Loan").objects.filter(product_type="direct")
    assert direct.exists()
    for loan in direct:
        assert cast(Any, loan).interest_convention == InterestConvention.LEGACY_MONTHLY
        created = cast(Any, loan).events.get(event_type="created")
        signed_on = date.fromisoformat(created.metadata["pre_cutover_contract_signed_on"])
        assert signed_on < ENGINE_CUTOVER_DATE


@pytest.mark.django_db
def test_the_payout_always_writes_a_confirmed_schedule_version(admin_user: Model) -> None:  # noqa: F811
    """Audit S5-11: also when the real payout day gives the same amounts and dates as the plan,
    a confirmed version is written with the payout day on every row."""
    from backend.apps.loans.models import LoanEvent, LoanInstallment
    from backend.apps.loans.services import confirm_engine_schedule_at_payout

    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    planned_version = int(loan.schedule_version)
    planned_day = loan.loan_start_date

    changed = confirm_engine_schedule_at_payout(
        loan_id=str(loan.pk), payout_date=planned_day, actor=admin_user
    )

    loan.refresh_from_db()
    rows = list(
        LoanInstallment.objects.filter(loan=loan, schedule_version=loan.schedule_version).order_by(
            "installment_number"
        )
    )
    event = LoanEvent.objects.filter(loan=loan, event_type="schedule_confirmed").latest(
        "occurred_at"
    )
    assert changed is False
    assert loan.schedule_version == planned_version + 1
    assert all(row.metadata["payout_confirmed_on"] == planned_day.isoformat() for row in rows)
    assert rows[0].metadata["interest_start"] == planned_day.isoformat()
    assert event.metadata["planned_schedule_version"] == planned_version
    assert event.metadata["schedule_changed"] is False


@pytest.mark.django_db
def test_the_payout_confirmation_compares_the_interest_start_too(admin_user: Model) -> None:  # noqa: F811
    """Audit S5-11: rows with the same amounts and dates but another interest start are a change,
    and the confirmed rows carry the real interest start."""
    from backend.apps.loans.models import LoanInstallment
    from backend.apps.loans.services import confirm_engine_schedule_at_payout

    loan = create_loan(_loan_command(admin_user, _borrower(admin_user)))
    payout_day = loan.loan_start_date
    # A current version whose rows have the same amounts and dates but a stale interest start
    # (the rows are append-only, so it is written as a new version).
    stale_version = int(loan.schedule_version) + 1
    LoanInstallment.objects.bulk_create(
        [
            LoanInstallment(
                loan=loan,
                schedule_version=stale_version,
                installment_number=row.installment_number,
                due_date=row.due_date,
                principal_minor=row.principal_minor,
                interest_minor=row.interest_minor,
                total_minor=row.total_minor,
                metadata={**dict(row.metadata or {}), "interest_start": "2000-01-01"},
            )
            for row in LoanInstallment.objects.filter(
                loan=loan, schedule_version=loan.schedule_version
            )
        ]
    )
    type(loan).objects.filter(pk=loan.pk).update(schedule_version=stale_version)

    changed = confirm_engine_schedule_at_payout(
        loan_id=str(loan.pk), payout_date=payout_day, actor=admin_user
    )

    loan.refresh_from_db()
    confirmed = LoanInstallment.objects.get(
        loan=loan, schedule_version=loan.schedule_version, installment_number=1
    )
    assert changed is True
    assert confirmed.metadata["interest_start"] == payout_day.isoformat()
