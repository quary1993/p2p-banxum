"""IP of Webby-Soft SRL. 18.6: servicing of an engine loan, end to end.

The loan is the example of "BANXUM: Interest, Late Payments, Penalties And Default" (validated
2026-11-18): CHF 10,000 at 12%, payout Tuesday 15 December 2026, monthly rows of CHF 900
principal, penalty X 0.05% per day, Late 15 / Default 60 days, no grace. Three investors hold
3,333.33 / 3,333.33 / 3,333.34, so their shares of interest and penalties have cent fractions.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model, Sum
from django.test import Client

from backend.apps.platform_core.models import Currency, OutboxMessage, PlatformSetting
from backend.apps.platform_core.tests.qa_clock import qa_clock
from backend.apps.servicing import engine
from backend.apps.servicing.models import (
    BorrowerRepaymentEvent,
    InvestorDistributionFraction,
    InvestorRepaymentDistributionLine,
    LoanDefaultDeclaration,
)
from backend.apps.servicing.services import (
    RecordBorrowerRepaymentCommand,
    ScanLoanServicingStatusesCommand,
    ServicingValidationError,
    get_loan_repayment_schedule_snapshots,
    record_borrower_repayment,
    scan_loan_servicing_statuses,
)

PAYOUT = date(2026, 12, 15)
SHARES = (3_333_33, 3_333_33, 3_333_34)


@contextmanager
def at(day: date) -> Iterator[None]:
    with qa_clock(datetime(day.year, day.month, day.day, 11, 0, tzinfo=UTC)):
        yield


def _user(email: str, **extra: Any) -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            password="EnginePass123!",
            full_name=email.split("@")[0],
            status="active",
            **extra,
        ),
    )


@pytest.fixture
def admin_user(db: None) -> Model:
    return _user("engine-admin@example.test", account_type="admin", is_staff=True)


@pytest.fixture
def superadmin(db: None) -> Model:
    return _user(
        "engine-super@example.test", account_type="admin", is_staff=True, is_superuser=True
    )


@pytest.fixture
def investors(db: None) -> list[Model]:
    return [
        _user(f"engine-investor-{index}@example.test", account_type="natural_person_lender")
        for index in range(3)
    ]


def _engine_loan(
    admin_user: Model, investors: list[Model], *, repayment_type: str = "custom_schedule"
) -> Model:
    for key, value in (
        ("servicing.late_threshold_days", 15),
        ("servicing.default_threshold_days", 60),
    ):
        PlatformSetting.objects.update_or_create(
            key=key, defaults={"value": value, "value_type": "integer"}
        )
    loans_services: Any = import_module("backend.apps.loans.services")
    currency = Currency.objects.get(code="CHF")
    borrower = apps.get_model("entities", "BorrowerEntity").objects.create(
        legal_name="Engine Borrower AG",
        year_founded=2018,
        kyb_status="approved",
        compliance_hold=False,
        country="Switzerland",
        created_by_admin_id=admin_user.pk,
    )
    manual = None
    if repayment_type == "custom_schedule":
        manual = [
            loans_services.ManualScheduleRowCommand(
                due_date=import_module(
                    "backend.apps.platform_core.domain.interest_engine"
                ).add_months_from_anchor(PAYOUT, number),
                principal_minor=900_00 if number < 12 else 100_00,
                interest_minor=0,
            )
            for number in range(1, 13)
        ]
    rows = loans_services.generate_engine_schedule(
        principal_minor=10_000_00,
        currency="CHF",
        term_months=12,
        annual_interest_bps=1_200,
        repayment_type=repayment_type,
        payout_date=PAYOUT,
        frequency="monthly",
        interest_only_months=0,
        grace_business_days=0,
        manual_schedule_rows=manual,
    )
    loan = apps.get_model("loans", "Loan").objects.create(
        borrower=borrower,
        status="active",
        title="Engine Loan",
        investor_summary="Engine test loan.",
        purpose="working_capital",
        original_principal_minor=10_000_00,
        principal_minor=10_000_00,
        currency=currency,
        interest_rate_bps=1_200,
        term_months=12,
        repayment_type=repayment_type,
        loan_start_date=PAYOUT,
        payout_date=PAYOUT,
        funding_deadline=date(2026, 12, 10),
        first_payment_date=rows[0].due_date,
        collateral_type="real_estate",
        collateral_value_minor=20_000_00,
        risk_rating="BBB",
        committed_principal_minor=10_000_00,
        total_scheduled_principal_minor=10_000_00,
        interest_convention="act_365_fixed",
        payment_frequency="monthly",
        penalty_daily_rate_percent=Decimal("0.05"),
        created_by_admin_id=admin_user.pk,
    )
    installment_model = apps.get_model("loans", "LoanInstallment")
    for row in rows:
        installment_model.objects.create(
            loan=loan,
            schedule_version=1,
            installment_number=row.installment_number,
            due_date=row.due_date,
            principal_minor=row.principal_minor,
            interest_minor=row.interest_minor,
            total_minor=row.total_minor,
            metadata=dict(row.metadata or {}),
        )
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    for index, (investor, share) in enumerate(zip(investors, SHARES, strict=True)):
        holding_model.objects.create(
            loan=loan,
            investor_user_id=investor.pk,
            source_type="primary_market",
            source_id=f"engine-order-{index}",
            status="active",
            original_principal_minor=share,
            current_principal_minor=share,
            currency=currency,
            loan_share_ppm=333_333,
            assignment_effective_at="2026-12-15T00:00:00Z",
            created_by_admin_id=admin_user.pk,
            idempotency_key=f"engine-holding-{index}",
        )
    return cast(Model, loan)


def _pay(admin_user: Model, loan: Model, amount_minor: int, value_date: date, key: str) -> Any:
    return record_borrower_repayment(
        RecordBorrowerRepaymentCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=amount_minor,
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier="CH00GARANTALEDGER",
            payer_name="Engine Borrower AG",
            payer_account_identifier="CH22BORROWER",
            bank_reference=f"BANK-{key}",
            evidence_reference=f"statement:{key}",
            idempotency_key=key,
        )
    )


def _expense(admin_user: Model, loan: Model, value_date: date) -> Any:
    return engine.record_loan_expense(
        engine.RecordLoanExpenseCommand(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=300_00,
            value_date=value_date,
            note="Lawyer's notice",
            evidence_reference="INV-2027-17",
            idempotency_key=f"expense-{value_date.isoformat()}",
        )
    )


@pytest.mark.django_db
def test_case_c_pending_due_late_expense_and_the_catch_up_payment(
    admin_user: Model, investors: list[Model]
) -> None:
    loan = _engine_loan(admin_user, investors)
    labels = {}
    row_statuses = {}
    for day in (date(2027, 1, 15), date(2027, 1, 19), date(2027, 1, 20), date(2027, 1, 30)):
        with at(day):
            status = engine.engine_status(loan)
            labels[day] = (status.label, status.days_late)
            snapshot = get_loan_repayment_schedule_snapshots(loans=[loan], as_of_date=day)
            row_statuses[day] = snapshot[str(loan.pk)][0].status
    with at(date(2027, 1, 18)):
        with pytest.raises(engine.EngineServicingError, match="Due"):
            _expense(admin_user, loan, date(2027, 1, 18))
    with at(date(2027, 2, 1)):
        _expense(admin_user, loan, date(2027, 2, 1))
    with at(date(2027, 2, 10)):
        preview = engine.preview_engine_payment(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=1_316_29,
            value_date=date(2027, 2, 10),
        )
        result = _pay(admin_user, loan, 1_316_29, date(2027, 2, 10), "engine-c-1")
        position = engine.servicing_position_payload(loan)

    assert labels == {
        date(2027, 1, 15): ("pending", 0),
        date(2027, 1, 19): ("pending", 4),
        date(2027, 1, 20): ("due", 5),
        date(2027, 1, 30): ("late", 15),
    }
    # The schedule rows the investors see carry the same window (t .. t+2 business days).
    assert row_statuses == {
        date(2027, 1, 15): "pending",
        date(2027, 1, 19): "pending",
        date(2027, 1, 20): "due",
        date(2027, 1, 30): "overdue",
    }
    assert (preview["expenses_minor"], preview["penalty_minor"]) == (300_00, 1_35 + 13_02)
    assert (preview["interest_minor"], preview["principal_minor"]) == (101_92, 900_00)
    assert preview["to_garanta_minor"] == 300_00
    event = result.repayment_event
    assert (event.fees_applied_minor, event.penalties_applied_minor) == (300_00, 14_37)
    assert (event.interest_applied_minor, event.principal_applied_minor) == (101_92, 900_00)
    lines = InvestorRepaymentDistributionLine.objects.filter(repayment_event=event)
    assert lines.aggregate(total=Sum("principal_minor"))["total"] == 900_00
    paid_interest = lines.aggregate(total=Sum("interest_minor"))["total"]
    paid_penalty = lines.aggregate(total=Sum("penalty_minor"))["total"]
    fractions = InvestorDistributionFraction.objects.filter(loan=cast(Any, loan))
    carried = sum(
        (Decimal(row.interest_fraction) + Decimal(row.penalty_fraction) for row in fractions),
        Decimal(0),
    )
    # Whole cents to the investors; the rest is carried (and sits on the fractions account).
    assert paid_interest + paid_penalty + carried == 101_92 + 14_37
    assert carried < 2 * len(investors)
    loan.refresh_from_db()
    assert str(cast(Any, loan).status) == "active"
    assert position["status"] == "on_schedule"
    assert position["expenses"][0]["owed_minor"] == 0


@pytest.mark.django_db
def test_case_d_default_is_declared_by_the_admin_never_by_the_scan(
    admin_user: Model, superadmin: Model, investors: list[Model]
) -> None:
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 2, 1)):
        _expense(admin_user, loan, date(2027, 2, 1))
    with at(date(2027, 3, 16)):
        scan_loan_servicing_statuses(
            ScanLoanServicingStatusesCommand(actor=admin_user, as_of_date=date(2027, 3, 16))
        )
        task = apps.get_model("admin_ops", "AdminTask").objects.get(related_object_id=str(loan.pk))
    loan.refresh_from_db()
    with at(date(2027, 3, 15)):
        with pytest.raises(engine.EngineServicingError, match="60 days"):
            engine.declare_loan_default(
                engine.DeclareLoanDefaultCommand(actor=admin_user, loan_id=str(loan.pk))
            )
    with at(date(2027, 3, 19)):
        declaration = engine.declare_loan_default(
            engine.DeclareLoanDefaultCommand(actor=admin_user, loan_id=str(loan.pk), note="Call")
        )
    with at(date(2027, 3, 31)):
        result = _pay(admin_user, loan, 2_000_00, date(2027, 3, 31), "engine-d-1")
        with pytest.raises(engine.EngineServicingError, match="super admin"):
            engine.cancel_loan_default(
                engine.CancelLoanDefaultCommand(
                    actor=admin_user, loan_id=str(loan.pk), reason="Declared by mistake."
                )
            )
        with pytest.raises(engine.EngineServicingError, match="payment or an expense"):
            engine.cancel_loan_default(
                engine.CancelLoanDefaultCommand(
                    actor=superadmin, loan_id=str(loan.pk), reason="Declared by mistake."
                )
            )
        position = engine.servicing_position_payload(loan)

    assert task.title.startswith("Default can be declared")
    assert str(cast(Any, loan).status) == "late"
    assert (declaration.whole_principal_minor, declaration.whole_interest_minor) == (
        10_000_00,
        270_15 + 12_00,
    )
    assert declaration.frozen_penalty_minor == 56_29
    event = result.repayment_event
    assert event.fees_applied_minor == 300_00
    assert event.penalties_applied_minor == 56_29 + 63_49
    assert (event.interest_applied_minor, event.principal_applied_minor) == (282_15, 1_298_07)
    loan.refresh_from_db()
    assert str(cast(Any, loan).status) == "defaulted"
    assert position["status"] == "default"
    assert position["principal_owed_minor"] == 8_701_93


@pytest.mark.django_db
def test_a_super_admin_cancels_a_default_and_the_payment_plan_returns(
    admin_user: Model, superadmin: Model, investors: list[Model]
) -> None:
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 3, 19)):
        engine.declare_loan_default(
            engine.DeclareLoanDefaultCommand(actor=admin_user, loan_id=str(loan.pk))
        )
        engine.cancel_loan_default(
            engine.CancelLoanDefaultCommand(
                actor=superadmin, loan_id=str(loan.pk), reason="The payment had arrived on time."
            )
        )
        status = engine.engine_status(loan)
    with at(date(2027, 3, 22)):
        preview = engine.preview_engine_payment(
            actor=admin_user,
            loan_id=str(loan.pk),
            amount_minor=1_001_92 + 33_06,
            value_date=date(2027, 3, 22),
        )

    loan.refresh_from_db()
    declaration = LoanDefaultDeclaration.objects.get(loan=cast(Any, loan))
    assert declaration.cancelled_at is not None
    # Every holder gets the correction notice once.
    notices = OutboxMessage.objects.filter(topic="email.loan_default_cancelled")
    assert notices.count() == len(investors)
    assert str(cast(Any, loan).status) == "late"
    assert status.label == "late" and status.default_possible
    # Installment 1 again, with its X for 16 January - 22 March (66 days): 33.06.
    assert preview["installments"][0] == {
        "installment_number": 1,
        "due_date": "2027-01-15",
        "penalty_minor": 33_06,
        "interest_minor": 101_92,
        "principal_minor": 900_00,
    }


@pytest.mark.django_db
def test_an_early_payment_recalculates_the_later_installments_with_the_same_maturity(
    admin_user: Model, investors: list[Model]
) -> None:
    loan = _engine_loan(admin_user, investors, repayment_type="equal_installments")
    rows = list(
        apps.get_model("loans", "LoanInstallment")
        .objects.filter(loan=loan, schedule_version=1)
        .order_by("installment_number")
    )
    with at(date(2027, 1, 12)):
        result = _pay(admin_user, loan, int(rows[0].total_minor), date(2027, 1, 12), "engine-early")

    loan.refresh_from_db()
    new_rows = list(
        apps.get_model("loans", "LoanInstallment")
        .objects.filter(loan=loan, schedule_version=cast(Any, loan).schedule_version)
        .order_by("installment_number")
    )
    assert cast(Any, loan).schedule_version == 2
    assert result.repayment_event.interest_applied_minor == 92_05
    assert [row.installment_number for row in new_rows] == list(range(2, 13))
    assert new_rows[-1].due_date == rows[-1].due_date
    assert new_rows[0].total_minor < rows[1].total_minor
    holdings_principal = (
        apps.get_model("holdings", "InvestorLoanHolding")
        .objects.filter(loan=loan)
        .aggregate(total=Sum("current_principal_minor"))["total"]
    )
    assert holdings_principal == sum(int(row.principal_minor) for row in new_rows)


@pytest.mark.django_db
def test_the_last_payment_pays_the_carried_cents(admin_user: Model, investors: list[Model]) -> None:
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 1, 15)):
        _pay(admin_user, loan, 1_001_92, date(2027, 1, 15), "engine-final-1")
        carried = sum(
            (
                Decimal(row.interest_fraction) + Decimal(row.penalty_fraction)
                for row in InvestorDistributionFraction.objects.filter(loan=cast(Any, loan))
            ),
            Decimal(0),
        )
        # Everything else on the same day: no interest built up since the due date.
        result = _pay(admin_user, loan, 9_100_00, date(2027, 1, 15), "engine-final-2")

    final_lines = [
        line
        for line in InvestorRepaymentDistributionLine.objects.filter(
            repayment_event=result.repayment_event
        )
    ]
    fractions = list(InvestorDistributionFraction.objects.filter(loan=cast(Any, loan)))
    loan.refresh_from_db()
    assert carried == int(carried) and carried > 0
    assert sum(row.final_paid_minor for row in fractions) == int(carried)
    assert all(Decimal(row.interest_fraction) == 0 for row in fractions)
    assert sum(line.interest_minor for line in final_lines) == int(carried)
    assert str(cast(Any, loan).status) == "repaid"


@pytest.mark.django_db
def test_admin_api_position_expenses_and_default(admin_user: Model, investors: list[Model]) -> None:
    loan = _engine_loan(admin_user, investors)
    client = Client()
    client.force_login(cast(Any, admin_user))
    base = f"/api/v1/servicing/admin/loans/{loan.pk}"
    with at(date(2027, 2, 1)):
        position = client.get(f"{base}/servicing-position/")
        created = client.post(
            f"{base}/expenses/",
            data={
                "amount_minor": 300_00,
                "value_date": "2027-02-01",
                "note": "Lawyer's notice",
                "idempotency_key": "api-expense-1",
            },
            content_type="application/json",
        )
        preview = client.post(
            f"{base}/payment-preview/",
            data={"amount_minor": 1_316_29, "value_date": "2027-02-01"},
            content_type="application/json",
        )
        early_default = client.post(
            f"{base}/default-declaration/", data={}, content_type="application/json"
        )
    investor_client = Client()
    investor_client.force_login(cast(Any, investors[0]))

    assert position.status_code == 200
    assert position.json()["status"] == "late" and position.json()["interest_engine"] is True
    assert created.status_code == 201 and created.json()["owed_minor"] == 300_00
    assert preview.status_code == 200 and preview.json()["expenses_minor"] == 300_00
    assert early_default.status_code == 400
    assert investor_client.get(f"{base}/servicing-position/").status_code == 403


@pytest.mark.django_db
def test_a_payment_more_than_what_is_owed_is_refused(
    admin_user: Model, investors: list[Model]
) -> None:
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 1, 15)):
        with pytest.raises(ServicingValidationError, match="more than everything"):
            _pay(admin_user, loan, 20_000_00, date(2027, 1, 15), "engine-too-much")
    assert not BorrowerRepaymentEvent.objects.filter(loan=loan).exists()


@pytest.mark.django_db
def test_an_engine_payment_runs_in_one_transaction(
    admin_user: Model, investors: list[Model], row_locks_need_a_transaction: None
) -> None:
    """Audit S1-1 follow-up: the loan row lock and the postings need one transaction."""
    loan = _engine_loan(admin_user, investors, repayment_type="equal_installments")
    first = (
        apps.get_model("loans", "LoanInstallment")
        .objects.filter(loan=loan, schedule_version=1)
        .order_by("installment_number")
        .first()
    )
    with at(date(2027, 1, 12)):
        result = _pay(
            admin_user, loan, int(cast(Any, first).total_minor), date(2027, 1, 12), "engine-atomic"
        )
    assert result.repayment_event.interest_applied_minor == 92_05
