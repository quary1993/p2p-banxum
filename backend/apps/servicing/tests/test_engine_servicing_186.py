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
    admin_user: Model,
    investors: list[Model],
    *,
    repayment_type: str = "custom_schedule",
    shares: tuple[int, ...] = SHARES,
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
    for index, (investor, share) in enumerate(zip(investors, shares, strict=True)):
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
        with pytest.raises(engine.EngineServicingError, match="borrower payment was recorded"):
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


def _fractions_account_balance() -> int:
    posting_model = apps.get_model("ledger", "LedgerPosting")
    rows = posting_model.objects.filter(account__account_type="undistributed_fractions")
    credit = rows.filter(side="credit").aggregate(total=Sum("amount_minor"))["total"] or 0
    debit = rows.filter(side="debit").aggregate(total=Sum("amount_minor"))["total"] or 0
    return int(credit) - int(debit)


def _stored_fractions(loan: Model) -> Decimal:
    return sum(
        (
            Decimal(row.interest_fraction) + Decimal(row.penalty_fraction)
            for row in InvestorDistributionFraction.objects.filter(loan=cast(Any, loan))
        ),
        Decimal(0),
    )


@pytest.mark.django_db
def test_a_carry_crossing_pays_out_of_the_fractions_account(
    admin_user: Model, investors: list[Model]
) -> None:
    """Audit S5-2: when the carried fractions reach a whole cent, the investors get more cents
    than this payment's interest has; the difference comes out of the fractions account."""
    loan = _engine_loan(admin_user, investors)
    rows = list(
        apps.get_model("loans", "LoanInstallment")
        .objects.filter(loan=loan, schedule_version=1)
        .order_by("installment_number")
    )
    released_total = 0
    for row in rows[:-1]:
        due = cast(date, row.due_date)
        with at(due):
            result = _pay(
                admin_user, loan, int(row.total_minor), due, f"crossing-{row.installment_number}"
            )
        allocation = result.repayment_event.metadata["allocation"]
        credited = sum(
            line.interest_minor
            for line in InvestorRepaymentDistributionLine.objects.filter(
                repayment_event=result.repayment_event
            )
        )
        released_total += max(0, credited - int(allocation["interest_minor"]))
        # The fractions account holds exactly the whole cents of the stored fractions.
        assert _fractions_account_balance() == int(_stored_fractions(loan).quantize(Decimal(1)))
        assert _fractions_account_balance() >= 0
    # Eleven payments of three investors with cent fractions cross at least once.
    assert released_total > 0


@pytest.mark.django_db
def test_the_distribution_releases_a_crossing_instead_of_a_negative_kept_amount(
    admin_user: Model, investors: list[Model]
) -> None:
    """Audit S5-2, the example of the report: two equal investors, 0.5 cent carried each, and a
    payment of 1 cent of interest: 2 cents are credited, 1 comes from the fractions."""
    loan = _engine_loan(admin_user, investors[:2], shares=(5_000_00, 5_000_00))
    holdings = list(apps.get_model("holdings", "InvestorLoanHolding").objects.filter(loan=loan))
    for holding in holdings:
        InvestorDistributionFraction.objects.create(
            loan=cast(Any, loan),
            investor_user_id=holding.investor_user_id,
            currency_id="CHF",
            interest_fraction=Decimal("0.5"),
            penalty_fraction=Decimal(0),
        )

    distribution = engine._engine_distribution(
        loan=loan,
        holdings=holdings,
        principal_minor=0,
        interest_minor=1,
        penalty_minor=0,
        final_payment=False,
    )

    assert sum(line.interest_minor for line in distribution.lines) == 2
    assert distribution.withheld_minor == 0
    assert distribution.released_minor == 1
    assert all(values == (Decimal(0), Decimal(0)) for values in distribution.fractions.values())


@pytest.mark.django_db
def test_final_cents_keep_interest_and_penalty_apart(
    admin_user: Model, investors: list[Model]
) -> None:
    """Audit S5-9: at the final payment a carried penalty fraction is paid as penalty, not as
    interest."""
    loan = _engine_loan(admin_user, investors[:2], shares=(5_000_00, 5_000_00))
    holdings = list(apps.get_model("holdings", "InvestorLoanHolding").objects.filter(loan=loan))
    for holding in holdings:
        InvestorDistributionFraction.objects.create(
            loan=cast(Any, loan),
            investor_user_id=holding.investor_user_id,
            currency_id="CHF",
            interest_fraction=Decimal("0.25"),
            penalty_fraction=Decimal("0.75"),
        )

    distribution = engine._engine_distribution(
        loan=loan,
        holdings=holdings,
        principal_minor=10_000_00,
        interest_minor=0,
        penalty_minor=0,
        final_payment=True,
    )

    # Interest pool 0.5 -> 1 cent (largest remainder, first investor); penalty pool 1.5 -> 2.
    assert sum(line.interest_minor for line in distribution.lines) == 1
    assert sum(line.penalty_minor for line in distribution.lines) == 2
    assert distribution.released_minor == 3


def test_the_garanta_part_of_a_penalty_is_rounded_down() -> None:
    """Audit S5-9 rule: Garanta's part is rounded down; the investors get the rest."""

    class _Loan:
        penalty_investor_share_bps = 5_000

    assert engine._penalty_investors_part(cast(Any, _Loan()), 3) == 2
    assert engine._penalty_investors_part(cast(Any, _Loan()), 5) == 3
    _Loan.penalty_investor_share_bps = 10_000
    assert engine._penalty_investors_part(cast(Any, _Loan()), 7) == 7
    _Loan.penalty_investor_share_bps = 0
    assert engine._penalty_investors_part(cast(Any, _Loan()), 7) == 0


@pytest.mark.django_db
def test_an_error_after_the_ledger_posting_rolls_everything_back(
    admin_user: Model,
    investors: list[Model],
    monkeypatch: pytest.MonkeyPatch,
    row_locks_need_a_transaction: None,
) -> None:
    """Audit S5-1: the ledger posting, the events, the penalty state, the fractions and the
    holdings are one transaction. A failure after the posting leaves nothing behind."""
    loan = _engine_loan(admin_user, investors)
    journal_model = apps.get_model("ledger", "LedgerJournalEntry")
    lot_model = apps.get_model("ledger", "InvestorBalanceLot")
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    principal_before = sorted(
        holding_model.objects.filter(loan=loan).values_list("current_principal_minor", flat=True)
    )
    journals_before = journal_model.objects.count()

    def fail(*_args: Any, **_kwargs: Any) -> None:
        assert journal_model.objects.count() == journals_before + 1  # the posting was made
        raise RuntimeError("forced failure after the ledger posting")

    original = engine._save_fractions
    monkeypatch.setattr(engine, "_save_fractions", fail)
    with at(date(2027, 1, 15)), pytest.raises(RuntimeError, match="forced failure"):
        _pay(admin_user, loan, 1_001_92, date(2027, 1, 15), "engine-rollback")

    assert journal_model.objects.count() == journals_before
    assert not lot_model.objects.exists()
    assert not BorrowerRepaymentEvent.objects.filter(loan=loan).exists()
    assert not InvestorDistributionFraction.objects.filter(loan=cast(Any, loan)).exists()
    assert (
        sorted(
            holding_model.objects.filter(loan=loan).values_list(
                "current_principal_minor", flat=True
            )
        )
        == principal_before
    )
    # The same request then succeeds (the row-lock check of the fixture stays on).
    monkeypatch.setattr(engine, "_save_fractions", original)
    with at(date(2027, 1, 15)):
        result = _pay(admin_user, loan, 1_001_92, date(2027, 1, 15), "engine-rollback")
    assert result.repayment_event.amount_minor == 1_001_92


def _expense_with(admin_user: Model, loan: Model, **changes: Any) -> Any:
    values: dict[str, Any] = {
        "actor": admin_user,
        "loan_id": str(loan.pk),
        "amount_minor": 300_00,
        "value_date": date(2027, 2, 10),
        "note": "Lawyer's notice",
        "evidence_reference": "INV-2027-17",
        "idempotency_key": "expense-replay",
    }
    values.update(changes)
    return engine.record_loan_expense(engine.RecordLoanExpenseCommand(**values))


@pytest.mark.django_db
def test_a_payment_cannot_be_dated_before_a_recorded_expense(
    admin_user: Model, investors: list[Model]
) -> None:
    """Audit S5-3: the expense moves the position to its value date, so a receipt dated
    before it cannot pay it."""
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 2, 12)):
        _expense_with(admin_user, loan)
        state = apps.get_model("servicing", "LoanPenaltyState").objects.get(loan=loan)
        with pytest.raises(ServicingValidationError, match="before the last recorded"):
            _pay(admin_user, loan, 1_001_92, date(2027, 2, 5), "engine-backdated")
        later = _pay(admin_user, loan, 1_001_92, date(2027, 2, 11), "engine-after-expense")

    assert state.through_date == date(2027, 2, 10)
    # The receipt after the expense pays the expense first (expenses, then the oldest row).
    assert later.repayment_event.fees_applied_minor == 300_00


@pytest.mark.django_db
def test_an_expense_cannot_be_dated_into_the_pending_days(
    admin_user: Model, investors: list[Model]
) -> None:
    """Audit S5-3: the loan must have been Due on the expense's value date, not only today."""
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 2, 1)):  # Late today; 16 January was in the Pending days
        with pytest.raises(engine.EngineServicingError, match="On the value date"):
            _expense_with(admin_user, loan, value_date=date(2027, 1, 16))
        accepted = _expense_with(admin_user, loan, value_date=date(2027, 1, 21))
    assert accepted.value_date == date(2027, 1, 21)


def test_the_allocation_never_pays_an_expense_dated_after_the_payment() -> None:
    """Audit S5-3, the defensive rule of the pure engine."""
    ie = import_module("backend.apps.platform_core.domain.interest_engine")
    position = ie.LoanPosition(
        through_date=date(2027, 1, 20),
        penalty_rate=Decimal("0.0005"),
        installments=[
            ie.OpenInstallment(
                key="1:2027-01-15",
                number=1,
                due_date=date(2027, 1, 15),
                interest_start=PAYOUT,
                principal_owed=900_00,
                interest_owed=101_92,
                original_due_date=date(2027, 1, 15),
            )
        ],
        expenses=[ie.OpenExpense(key="later", value_date=date(2027, 2, 10), amount_owed=300_00)],
    )
    allocation = ie.allocate_payment(
        position,
        amount_minor=500_00,
        value_date=date(2027, 2, 5),
        annual_rate_bps=1_200,
        kind="custom",
    )
    assert allocation.expenses_minor == 0
    assert position.expenses[0].amount_owed == 300_00


@pytest.mark.django_db
def test_an_expense_key_is_bound_to_its_request(admin_user: Model, investors: list[Model]) -> None:
    """Audit S5-8: the same request returns the same expense; another amount, date, note or
    loan with the same key is refused."""
    loan = _engine_loan(admin_user, investors)
    other_loan_id = "8f1c1d0e-4b7a-4e43-9a55-2f3c9c1b7d10"
    with at(date(2027, 2, 12)):
        first = _expense_with(admin_user, loan)
        replay = _expense_with(admin_user, loan)
        refused = []
        for changes in (
            {"amount_minor": 301_00},
            {"value_date": date(2027, 2, 11)},
            {"note": "Another notice"},
            {"loan_id": other_loan_id},
        ):
            with pytest.raises(engine.EngineServicingError, match="different expense request"):
                _expense_with(admin_user, loan, **changes)
            refused.append(changes)

    assert replay.id == first.id
    assert len(refused) == 4
    assert apps.get_model("servicing", "LoanExpense").objects.count() == 1


@pytest.mark.django_db
def test_the_portfolio_shows_the_penalty_of_a_direct_loan(
    admin_user: Model, investors: list[Model], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit S5-9: the penalty X paid to an investor on a direct engine loan is in the
    portfolio totals (before, only Loan Originator penalties were counted)."""
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 2, 10)):
        # 1,001.92 for the 15 January row and 13.02 of penalty X (26 days late).
        result = _pay(admin_user, loan, 1_014_94, date(2027, 2, 10), "penalty-1")
    lines = InvestorRepaymentDistributionLine.objects.filter(
        repayment_event=result.repayment_event, investor_user_id=investors[0].pk
    )
    expected = int(lines.aggregate(total=Sum("penalty_minor"))["total"] or 0)
    portal: Any = import_module("backend.apps.investor_portal.services")
    monkeypatch.setattr(portal, "_require_financial_access", lambda actor: str(actor.pk))

    portfolio = portal.get_investor_portfolio(actor=investors[0], include_inactive=True)

    assert result.repayment_event.penalties_applied_minor == 13_02
    assert expected > 0
    holding = portfolio["holdings"][0]
    assert holding["received_penalty_minor"] == expected


@pytest.mark.django_db
def test_a_catch_up_receipt_shows_the_investor_share_of_each_installment(
    admin_user: Model, investors: list[Model]
) -> None:
    """Audit S5-10: a receipt that pays two whole rows and part of a third gives each investor
    one line per installment (with that installment's share), on one balance lot."""
    loan = _engine_loan(admin_user, investors)
    day = date(2027, 3, 20)
    with at(day):
        status = engine.engine_status(loan)
        # Everything due (rows of 15 January, 15 February and 15 March with penalties) less 500.
        amount = status.due_now_minor - 500_00
        result = _pay(admin_user, loan, amount, day, "catch-up")
    events = list(
        BorrowerRepaymentEvent.objects.filter(loan=loan).order_by("installment__installment_number")
    )
    investor_lines = list(
        InvestorRepaymentDistributionLine.objects.filter(
            investor_user_id=investors[0].pk
        ).select_related("repayment_event__installment")
    )
    by_number = {
        int(line.repayment_event.installment.installment_number): line for line in investor_lines
    }
    portal: Any = import_module("backend.apps.investor_portal.services")
    received = portal._received_payments_by_holding(
        investor_user_id=str(investors[0].pk),
        holding_ids=[str(investor_lines[0].holding_id)],
    )[str(investor_lines[0].holding_id)]

    assert [int(event.installment.installment_number) for event in events] == [1, 2, 3]
    assert sorted(by_number) == [1, 2, 3]
    # Rows 1 and 2 are paid in full: about a third of 900 principal each; row 3 in part.
    assert by_number[1].principal_minor == by_number[2].principal_minor
    assert 0 < by_number[3].principal_minor < by_number[1].principal_minor
    assert len({line.balance_lot_id for line in investor_lines}) == 1
    lot = investor_lines[0].balance_lot
    assert sum(line.amount_minor for line in investor_lines) == int(lot.original_amount_minor)
    assert [row["installment_number"] for row in received] == [1, 2, 3]
    # The components of all investors on all events add up to the receipt's.
    every_line = InvestorRepaymentDistributionLine.objects.filter(
        repayment_event__loan=loan
    ).aggregate(principal=Sum("principal_minor"))
    assert (
        every_line["principal"] == result.repayment_event.metadata["allocation"]["principal_minor"]
    )


@pytest.mark.django_db
def test_a_final_write_off_pays_the_carried_cents(
    admin_user: Model, investors: list[Model]
) -> None:
    """Audit S5-12: after a partial payment, a Default and the final write-off, the whole cents
    kept for the investors leave the fractions account to their balances."""
    services: Any = import_module("backend.apps.servicing.services")
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 1, 15)):
        _pay(admin_user, loan, 1_001_92, date(2027, 1, 15), "before-default")
    kept = _fractions_account_balance()
    with at(date(2027, 4, 20)):  # the 15 February row is more than 60 days late
        engine.declare_loan_default(
            engine.DeclareLoanDefaultCommand(actor=admin_user, loan_id=str(loan.pk))
        )
        remaining = int(
            apps.get_model("holdings", "InvestorLoanHolding")
            .objects.filter(loan=loan, status="active")
            .aggregate(total=Sum("current_principal_minor"))["total"]
        )
        write_off = services.record_loan_write_off(
            services.RecordLoanWriteOffCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                written_off_principal_minor=remaining,
                reason="Insolvency closed without dividend.",
                idempotency_key="write-off-1",
            )
        )
    lots = apps.get_model("ledger", "InvestorBalanceLot").objects.filter(
        source_id__startswith=f"{write_off.id}:fractions:"
    )
    fractions = InvestorDistributionFraction.objects.filter(loan=cast(Any, loan))

    assert kept > 0
    assert _fractions_account_balance() == 0
    assert sum(int(lot.original_amount_minor) for lot in lots) == kept
    assert all(Decimal(row.interest_fraction) == 0 for row in fractions)
    assert sum(int(row.final_paid_minor) for row in fractions) == kept


@pytest.mark.django_db
def test_garanta_penalty_part_and_repaid_expenses_use_two_accounts(
    admin_user: Model, investors: list[Model]
) -> None:
    """Audit step 5 (D7): repaid recovery expenses and Garanta's part of penalty X are posted to
    two ledger accounts (different economic and tax meaning)."""
    loan = _engine_loan(admin_user, investors)
    cast(Any, loan).penalty_investor_share_bps = 5_000
    loan.save(update_fields=["penalty_investor_share_bps"])
    with at(date(2027, 2, 1)):
        _expense(admin_user, loan, date(2027, 2, 1))
    with at(date(2027, 2, 10)):
        result = _pay(admin_user, loan, 1_316_29, date(2027, 2, 10), "garanta-split")
    posting_model = apps.get_model("ledger", "LedgerPosting")

    def credited(account_type: str) -> int:
        return int(
            posting_model.objects.filter(
                account__account_type=account_type, side="credit"
            ).aggregate(total=Sum("amount_minor"))["total"]
            or 0
        )

    penalty = int(result.repayment_event.penalties_applied_minor)
    investors_penalty = int(
        InvestorRepaymentDistributionLine.objects.filter(repayment_event__loan=loan).aggregate(
            total=Sum("penalty_minor")
        )["total"]
    )
    assert penalty == 14_37
    assert credited("garanta_recovery_receivable") == 300_00
    # Garanta's half rounded down (7.18); the investors' part is the rest (7.19), minus the
    # fractions kept for them.
    assert credited("garanta_penalty_income") == 7_18
    assert investors_penalty <= penalty - 7_18


@pytest.mark.django_db
def test_a_repayment_key_is_bound_to_the_garanta_penalty_split(
    admin_user: Model, investors: list[Model], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-audit R5-1: the same key with another split between Garanta's repaid expenses and
    its part of penalty X is refused; the same request returns the first result."""
    from dataclasses import replace

    ledger: Any = import_module("backend.apps.ledger.services")
    loan = _engine_loan(admin_user, investors)
    cast(Any, loan).penalty_investor_share_bps = 5_000
    loan.save(update_fields=["penalty_investor_share_bps"])
    seen: list[Any] = []
    real = ledger.declare_borrower_repayment_distribution

    def spy(command: Any) -> Any:
        seen.append(command)
        return real(command)

    monkeypatch.setattr(ledger, "declare_borrower_repayment_distribution", spy)
    with at(date(2027, 2, 1)):
        _expense(admin_user, loan, date(2027, 2, 1))
    with at(date(2027, 2, 10)):
        _pay(admin_user, loan, 1_316_29, date(2027, 2, 10), "garanta-key")
    [command] = seen
    assert command.garanta_penalty_minor > 0
    journal_model = apps.get_model("ledger", "LedgerJournalEntry")
    journals = journal_model.objects.count()

    same = real(command)
    assert journal_model.objects.count() == journals
    assert same.bank_operation.id is not None
    with pytest.raises(ledger.LedgerValidationError):
        real(replace(command, garanta_penalty_minor=command.garanta_penalty_minor - 1))
    assert journal_model.objects.count() == journals


@pytest.mark.django_db
def test_a_replayed_fraction_release_creates_no_new_lots(
    admin_user: Model, investors: list[Model], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-audit R5-2: the release of the carried cents, called again with the same source,
    returns the lots of the first call; other lines for the same source are refused."""
    from dataclasses import replace

    services: Any = import_module("backend.apps.servicing.services")
    ledger: Any = import_module("backend.apps.ledger.services")
    lot_model = apps.get_model("ledger", "InvestorBalanceLot")
    seen: list[Any] = []
    real = ledger.release_loan_cent_fractions

    def spy(command: Any) -> Any:
        seen.append(command)
        return real(command)

    monkeypatch.setattr(ledger, "release_loan_cent_fractions", spy)
    loan = _engine_loan(admin_user, investors)
    with at(date(2027, 1, 15)):
        _pay(admin_user, loan, 1_001_92, date(2027, 1, 15), "replay-before-default")
    with at(date(2027, 4, 20)):
        engine.declare_loan_default(
            engine.DeclareLoanDefaultCommand(actor=admin_user, loan_id=str(loan.pk))
        )
        remaining = int(
            apps.get_model("holdings", "InvestorLoanHolding")
            .objects.filter(loan=loan, status="active")
            .aggregate(total=Sum("current_principal_minor"))["total"]
        )
        services.record_loan_write_off(
            services.RecordLoanWriteOffCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                written_off_principal_minor=remaining,
                reason="Insolvency closed without dividend.",
                idempotency_key="replay-write-off",
            )
        )
        [command] = seen
        lots_before = lot_model.objects.count()
        first_ids = sorted(
            str(lot.id)
            for lot in lot_model.objects.filter(source_id__startswith=f"{command.source_id}:")
        )
        replayed = real(command)
        assert lot_model.objects.count() == lots_before
        assert sorted(str(credit.balance_lot.id) for credit in replayed) == first_ids
        changed = [replace(command.lines[0], interest_minor=command.lines[0].interest_minor + 1)]
        with pytest.raises(ledger.LedgerValidationError):
            real(replace(command, lines=changed + list(command.lines[1:])))
        assert lot_model.objects.count() == lots_before
