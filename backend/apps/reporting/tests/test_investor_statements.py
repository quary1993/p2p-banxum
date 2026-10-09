"""Investor statement, tax period, admin report filter and redaction checks (audit round 2)."""

from __future__ import annotations

import base64
import csv
import io
import json
import zipfile
from datetime import date, datetime, time, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model, Q, Sum
from freezegun import freeze_time
from pypdf import PdfReader

from backend.apps.platform_core.domain.time import business_date, business_timezone, now_utc
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.tests.factories import issue_sensitive_action_test_code
from backend.apps.reporting.models import (
    ReportOutputFormat,
    ReportPeriodPreset,
    ReportRedactionMode,
    ReportType,
)
from backend.apps.reporting.services import (
    GenerateInvestorSelfServiceReportCommand,
    GenerateReportCommand,
    ReportingValidationError,
    generate_investor_self_service_report,
    generate_report,
)


@pytest.fixture
def admin_user() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="statement-admin@example.test",
            password="AdminPass123!",
            full_name="Statement Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def superadmin_user() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_superuser(
            email="statement-superadmin@example.test",
            password="AdminPass123!",
            full_name="Statement Superadmin",
        ),
    )


@pytest.fixture
def investor() -> Model:
    return cast(
        Model,
        get_user_model().objects.create_user(
            email="statement-investor@example.test",
            full_name="Anna Müller",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


def _at(value: date, hour: int = 10) -> datetime:
    return datetime.combine(value, time(hour=hour), tzinfo=business_timezone())


def _approve_lender(investor: Model) -> None:
    now = datetime.now(tz=business_timezone())
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


def _deposit(admin_user: Model, investor: Model, *, amount_minor: int, value_date: date) -> None:
    ledger: Any = import_module("backend.apps.ledger.services")
    ledger.declare_lender_deposit(
        ledger.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency="CHF",
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier="CH00GARANTASTATEMENT",
            payer_name="Anna Müller",
            payer_account_identifier="CH9300762011623852957",
            bank_reference=f"BANK-STATEMENT-{value_date.isoformat()}",
            payment_reference=f"INV-{investor.pk}",
            evidence_reference=f"statement:{value_date.isoformat()}",
            notes="Matched for statement test.",
            idempotency_key=f"statement-deposit-{value_date.isoformat()}",
        )
    )


def _loan(admin_user: Model, *, title: str, funding_deadline: date) -> Any:
    borrower = apps.get_model("entities", "BorrowerEntity").objects.create(
        legal_name="Alpine Equipment AG",
        year_founded=2015,
        kyb_status="approved",
        compliance_hold=False,
        country="Switzerland",
        created_by_admin_id=admin_user.pk,
    )
    return apps.get_model("loans", "Loan").objects.create(
        borrower=borrower,
        status="published",
        title=title,
        investor_summary="Statement test loan.",
        purpose="working_capital",
        original_principal_minor=50_000_00,
        principal_minor=50_000_00,
        currency=Currency.objects.get(code="CHF"),
        interest_rate_bps=1_200,
        term_months=6,
        repayment_type="equal_installments",
        loan_start_date=funding_deadline,
        funding_deadline=funding_deadline,
        first_payment_date=funding_deadline + timedelta(days=30),
        collateral_type="real_estate",
        collateral_value_minor=100_000_00,
        risk_rating="BBB",
        borrower_success_fee_bps=200,
        total_scheduled_principal_minor=50_000_00,
        created_by_admin_id=admin_user.pk,
        published_at=_at(funding_deadline - timedelta(days=20)),
    )


def _ledger_balance_minor(investor: Model, currency: str, end_date: date) -> int:
    totals = (
        apps.get_model("ledger", "LedgerPosting")
        .objects.filter(
            account__account_type="investor_balance_liability",
            account__owner_id=str(investor.pk),
            currency__code=currency,
            journal_entry__value_date__lte=end_date,
        )
        .aggregate(
            credits=Sum("amount_minor", filter=Q(side="credit")),
            debits=Sum("amount_minor", filter=Q(side="debit")),
        )
    )
    return int(totals["credits"] or 0) - int(totals["debits"] or 0)


def _csv_rows(content: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content)))


def _pdf_text(artifact: Any) -> str:
    pdf = base64.b64decode(artifact.content.encode("ascii"))
    text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    return " ".join(text.split())


def _statement(investor: Model, start: date, end: date, output_format: str) -> Any:
    with freeze_time("2026-04-15T10:00:00Z"):
        return generate_investor_self_service_report(
            GenerateInvestorSelfServiceReportCommand(
                actor=investor,
                report_type=ReportType.PARTICIPANT_ACCOUNT_STATEMENT,
                start_date=start,
                end_date=end,
                output_format=output_format,
            )
        )


def _build_investor_history(admin_user: Model, investor: Model) -> Any:
    """Deposit, investment, repayment, FX conversion and withdrawal through the real services."""
    ledger: Any = import_module("backend.apps.ledger.services")
    fx: Any = import_module("backend.apps.fx.services")
    fx_tests: Any = import_module("backend.apps.fx.tests.test_fx")
    _approve_lender(investor)
    with freeze_time("2026-01-05T09:00:00Z"):
        _deposit(admin_user, investor, amount_minor=10_000_00, value_date=date(2026, 1, 5))
    loan = _loan(admin_user, title="Alpine Equipment Loan", funding_deadline=date(2026, 2, 20))
    with freeze_time("2026-01-10T09:00:00Z"):
        ledger.reserve_investor_balance_for_investment(
            ledger.ReserveInvestmentBalanceCommand(
                actor=admin_user,
                investor_user_id=str(investor.pk),
                loan_id=str(loan.pk),
                amount_minor=6_000_00,
                currency="CHF",
                loan_funding_deadline=date(2026, 2, 20),
                source_type="primary_investment_order",
                source_id="statement-order",
                idempotency_key="statement-reserve",
                as_of=_at(date(2026, 1, 10)),
            )
        )
    with freeze_time("2026-02-27T09:00:00Z"):
        ledger.declare_borrower_repayment_distribution(
            ledger.DeclareBorrowerRepaymentDistributionCommand(
                actor=admin_user,
                loan_id=str(loan.pk),
                borrower_id=str(loan.borrower_id),
                amount_minor=1_060_00,
                currency="CHF",
                booking_date=date(2026, 2, 27),
                value_date=date(2026, 2, 27),
                collection_account_identifier="CH00GARANTASTATEMENT",
                payer_name="Alpine Equipment AG",
                source_type="borrower_repayment_event",
                source_id="statement-repayment",
                distribution_lines=[
                    ledger.InvestorBalanceCreditLineCommand(
                        investor_user_id=str(investor.pk),
                        amount_minor=1_060_00,
                        principal_minor=1_000_00,
                        interest_minor=60_00,
                    )
                ],
                payer_account_identifier="CH22BORROWER",
                idempotency_key="statement-repayment",
            )
        )
    fx_at = _at(date(2026, 3, 2))
    with freeze_time("2026-03-02T09:00:00Z"):
        quote = fx.issue_fx_quote(
            fx_tests._quote_command(
                investor, amount_minor=1_000_00, idempotency_key="statement-quote", as_of=fx_at
            )
        )
        code = issue_sensitive_action_test_code(investor, "fx")
        fx.execute_fx_quote(
            fx.ExecuteFxQuoteCommand(
                actor=investor,
                quote_id=str(quote.id),
                idempotency_key="statement-fx",
                as_of=fx_at,
                sensitive_action_code_id=code.code_id,
                sensitive_action_code=code.raw_code,
            )
        )
    with freeze_time("2026-03-05T09:00:00Z"):
        code = issue_sensitive_action_test_code(investor, "withdrawal")
        ledger.request_investor_withdrawal(
            ledger.RequestInvestorWithdrawalCommand(
                actor=investor,
                amount_minor=500_00,
                currency="CHF",
                destination_iban="CH9300762011623852957",
                destination_account_name="Anna Müller",
                idempotency_key="statement-withdrawal",
                sensitive_action_code_id=code.code_id,
                sensitive_action_code=code.raw_code,
            )
        )
    return loan


@pytest.mark.django_db
def test_investor_statement_is_signed_formatted_and_reconciles_to_ledger(
    admin_user: Model,
    investor: Model,
) -> None:
    # A-45 / JOURNEY-06: the statement was a raw liability ledger dump in cents with reversed
    # signs, internal columns and loan ids only.
    _build_investor_history(admin_user, investor)
    start, end = date(2026, 2, 1), date(2026, 3, 31)

    rows = _csv_rows(_statement(investor, start, end, "csv").content)
    chf = [row for row in rows if row["currency"] == "CHF"]
    eur = [row for row in rows if row["currency"] == "EUR"]
    assert [row["row_type"] for row in chf] == [
        "opening_balance",
        "movement",
        "movement",
        "movement",
        "closing_balance",
    ]
    # Opening = deposit 10'000.00 - investment 6'000.00 before the period.
    assert chf[0]["balance"] == "4000.00"
    repayment, exchange, withdrawal = chf[1:4]
    assert repayment["description"] == "Repayment from Alpine Equipment Loan"
    assert repayment["loan"] == "Alpine Equipment Loan"
    assert repayment["value_date"] == "2026-02-27"
    assert (repayment["amount"], repayment["principal"], repayment["interest"]) == (
        "1060.00",
        "1000.00",
        "60.00",
    )
    assert repayment["balance"] == "5060.00"
    assert exchange["description"] == "Currency exchange CHF to EUR"
    assert exchange["amount"] == "-1000.00"
    assert exchange["balance"] == "4060.00"
    assert withdrawal["movement_type"] == "withdrawal"
    assert withdrawal["amount"] == "-500.00"
    assert withdrawal["balance"] == "3560.00"
    assert chf[-1]["balance"] == "3560.00"
    # Rate 1.10, fee 1.5 %: 1'100.00 gross, 16.50 fee, 1'083.50 credited.
    assert [row["amount"] for row in eur if row["row_type"] == "movement"] == ["1083.50"]
    assert eur[1]["fees"] == "16.50"
    assert eur[-1]["balance"] == "1083.50"
    # Running and closing balances reconcile to the investor's ledger account.
    assert chf[-1]["balance"] == f"{_ledger_balance_minor(investor, 'CHF', end) / 100:.2f}"
    assert eur[-1]["balance"] == f"{_ledger_balance_minor(investor, 'EUR', end) / 100:.2f}"
    content = _statement(investor, start, end, "csv").content
    for internal in ("investor_balance_liability", "journal_entry_id", "posting_id", "credit"):
        assert internal not in content
    assert "406000" not in content and "'-" not in content

    pdf = _pdf_text(_statement(investor, start, end, "pdf"))
    for expected in (
        "Account statement",
        "Anna Müller",
        "01 Feb 2026 to 31 Mar 2026",
        "CHF account",
        "Opening balance",
        "4'000.00",
        "Repayment from Alpine Equipment Loan",
        "Principal CHF 1'000.00, interest CHF 60.00.",
        "+1'060.00",
        "-1'000.00",
        "-500.00",
        "Closing balance",
        "3'560.00",
        "EUR account",
        "+1'083.50",
    ):
        assert expected in pdf, expected
    for internal in ("investor_balance_liability", "Journal Entry", "406000", "Amount Minor"):
        assert internal not in pdf

    # The year to date starts at zero and includes the deposit and the investment.
    year = _csv_rows(_statement(investor, date(2026, 1, 1), end, "csv").content)
    year_chf = [row for row in year if row["currency"] == "CHF"]
    assert year_chf[0]["balance"] == "0.00"
    assert year_chf[1]["description"] == "Deposit by bank transfer"
    assert year_chf[1]["amount"] == "10000.00"
    assert year_chf[2]["description"] == "Investment in Alpine Equipment Loan"
    assert year_chf[2]["amount"] == "-6000.00"
    assert year_chf[-1]["balance"] == "3560.00"


@pytest.mark.django_db
def test_statement_and_tax_information_refuse_periods_that_have_not_ended(
    superadmin_user: Model,
    investor: Model,
) -> None:
    # JOURNEY-16: tax information for 2027 claimed principal outstanding on 2027-12-31.
    _approve_lender(investor)
    today = business_date(now_utc())
    for start, end in (
        (date(today.year + 1, 1, 1), date(today.year + 1, 12, 31)),
        (date(today.year, 1, 1), date(today.year, 12, 31)),
        (date(today.year, 1, 1), today),
    ):
        with pytest.raises(ReportingValidationError, match="period that has ended"):
            generate_investor_self_service_report(
                GenerateInvestorSelfServiceReportCommand(
                    actor=investor,
                    report_type=ReportType.ANNUAL_TAX_INFORMATION,
                    start_date=start,
                    end_date=end,
                    output_format=ReportOutputFormat.CSV,
                )
            )
    with pytest.raises(ReportingValidationError, match="period that has ended"):
        generate_report(
            GenerateReportCommand(
                actor=superadmin_user,
                report_type=ReportType.ANNUAL_TAX_INFORMATION,
                period_preset=ReportPeriodPreset.CALENDAR_YEAR,
                period_anchor_date=today,
                filters={"participant_type": "garanta"},
            )
        )
    with pytest.raises(ReportingValidationError, match="cannot end after today"):
        generate_investor_self_service_report(
            GenerateInvestorSelfServiceReportCommand(
                actor=investor,
                report_type=ReportType.PARTICIPANT_ACCOUNT_STATEMENT,
                start_date=date(today.year, 1, 1),
                end_date=today + timedelta(days=1),
                output_format=ReportOutputFormat.CSV,
            )
        )
    last_year = generate_investor_self_service_report(
        GenerateInvestorSelfServiceReportCommand(
            actor=investor,
            report_type=ReportType.ANNUAL_TAX_INFORMATION,
            start_date=date(today.year - 1, 1, 1),
            end_date=date(today.year - 1, 12, 31),
            output_format=ReportOutputFormat.CSV,
        )
    )
    assert "no_account_activity_in_period" in last_year.content


@pytest.mark.django_db
def test_loan_funding_report_follows_funding_events_and_names_lo_borrowers(
    admin_user: Model,
    investor: Model,
) -> None:
    # JOURNEY-17: the report selected loans by funding deadline only, so a period with
    # investments but no deadline was empty, and LO rows printed borrower_id "None".
    originator_tests: Any = import_module(
        "backend.apps.originator_claims.tests.test_originator_claims"
    )
    today = business_date(now_utc())
    result = originator_tests._create_par_subscription_loan(
        admin_user=admin_user, today=today, suffix="FUNDING"
    )
    originator_tests._allocate_par_subscription(
        admin_user=admin_user,
        investor=investor,
        loan=result.loan,
        today=today,
        amount_minor=200_000,
        suffix="FUNDING",
    )
    deadline = cast(Any, result.loan).funding_deadline
    assert deadline > today

    artifact = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.LOAN_FUNDING,
            start_date=today,
            end_date=today,
        )
    )
    rows = _csv_rows(artifact.content)
    row = next(item for item in rows if item["loan_id"] == str(cast(Any, result.loan).pk))
    assert row["product_type"] == "originator_claim"
    assert row["borrower_id"] == ""
    assert row["borrower_name"] == "Subscription borrower FUNDING"
    assert row["loan_originator"] == "Subscription Originator FUNDING"
    assert row["orders_in_period"] == "1"
    assert row["ordered_amount_in_period_minor"] == "200000"
    assert "None" not in {value for item in rows for value in item.values()}
    assert any("investment order was placed" in note for note in artifact.manifest["notes"])

    pdf = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.LOAN_FUNDING,
            start_date=today,
            end_date=today,
            output_format=ReportOutputFormat.PDF,
        )
    )
    assert "investment order was placed" in _pdf_text(pdf)

    # A period with no funding event for this loan does not list it.
    empty = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.LOAN_FUNDING,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=30),
        )
    )
    assert str(cast(Any, result.loan).pk) not in empty.content


@pytest.mark.django_db
def test_redacted_reports_hide_investor_identifiers_in_every_column(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
) -> None:
    # JOURNEY-18: redacted exports hid investor_user_id but kept the investor id inside
    # linked_object_id, lot source ids and ledger account codes.
    _build_investor_history(admin_user, investor)
    reference = str(cast(Any, investor).investor_reference)
    identifiers = {str(investor.pk), cast(Any, investor).email, reference}
    assert reference
    for report_type in ReportType.values:
        for output_format in (ReportOutputFormat.CSV, ReportOutputFormat.ZIP):
            artifact = generate_report(
                GenerateReportCommand(
                    actor=superadmin_user,
                    report_type=report_type,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 3, 31),
                    output_format=output_format,
                    redaction_mode=ReportRedactionMode.REDACTED,
                    filters={"participant_type": "lender", "participant_id": str(investor.pk)}
                    if report_type
                    in {ReportType.PARTICIPANT_ACCOUNT_STATEMENT, ReportType.ANNUAL_TAX_INFORMATION}
                    else {},
                )
            )
            if output_format == ReportOutputFormat.ZIP:
                archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(artifact.content)))
                text = " ".join(
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in archive.namelist()
                    if not name.endswith(".pdf")
                )
            else:
                text = artifact.content
            text += json.dumps(artifact.manifest, default=str)
            for identifier in identifiers:
                assert identifier not in text, (report_type, output_format, identifier)

    # Full mode still shows them to a superadmin.
    full = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.BANK_OPERATIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            redaction_mode=ReportRedactionMode.FULL,
        )
    )
    assert str(investor.pk) in full.content


@pytest.mark.django_db
def test_borrower_tax_information_uses_the_fee_booked_at_disbursement(
    superadmin_user: Model,
    admin_user: Model,
) -> None:
    # FINCODE-09: the report used the fee planned at funding close (2 %) and called the full
    # principal the "net disbursement".
    ledger: Any = import_module("backend.apps.ledger.services")
    ledger_tests: Any = import_module("backend.apps.ledger.tests.test_ledger_foundation")
    loan_id, borrower_id = ledger_tests._closed_primary_loan_funding(admin_user)
    with freeze_time("2026-01-02T12:00:00Z"):
        ledger.finalize_borrower_disbursement(
            ledger_tests._disbursement_command(
                admin_user,
                loan_id,
                borrower_id,
                amount_minor=99_000_00,
                fee_minor=1_000_00,
                override_note="Fee reduced at payout.",
                idempotency_key="tax-disbursement-override",
            )
        )
    artifact = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.ANNUAL_TAX_INFORMATION,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            filters={"participant_type": "borrower", "participant_id": str(borrower_id)},
        )
    )
    amounts = {row["category"]: int(row["amount_minor"]) for row in _csv_rows(artifact.content)}
    assert amounts["borrower_success_fee"] == 1_000_00
    assert amounts["principal_received"] == 100_000_00
    assert amounts["net_disbursement_paid"] == 99_000_00
    assert "net_disbursement_payable" not in amounts


def _year_end_loan(admin_user: Model, investor: Model, other: Model) -> Model:
    """Active loan whose first installment falls due on 31 Dec 2025."""
    currency = Currency.objects.get(code="CHF")
    borrower = apps.get_model("entities", "BorrowerEntity").objects.create(
        legal_name="Year End Borrower AG",
        year_founded=2018,
        kyb_status="approved",
        compliance_hold=False,
        country="Switzerland",
        created_by_admin_id=admin_user.pk,
    )
    loan = apps.get_model("loans", "Loan").objects.create(
        borrower=borrower,
        status="active",
        title="Year End Loan",
        investor_summary="Year-end test loan.",
        purpose="working_capital",
        original_principal_minor=30_000_00,
        principal_minor=30_000_00,
        currency=currency,
        interest_rate_bps=1_000,
        term_months=2,
        repayment_type="equal_installments",
        loan_start_date=date(2025, 11, 30),
        funding_deadline=date(2025, 11, 30),
        first_payment_date=date(2025, 12, 31),
        collateral_type="real_estate",
        collateral_value_minor=60_000_00,
        risk_rating="BBB",
        borrower_success_fee_bps=200,
        committed_principal_minor=30_000_00,
        total_scheduled_principal_minor=30_000_00,
        created_by_admin_id=admin_user.pk,
    )
    installment_model = apps.get_model("loans", "LoanInstallment")
    for number, due_date, principal, interest in (
        (1, date(2025, 12, 31), 3_000_00, 300_00),
        (2, date(2026, 1, 31), 27_000_00, 200_00),
    ):
        installment_model.objects.create(
            loan=loan,
            schedule_version=1,
            installment_number=number,
            due_date=due_date,
            principal_minor=principal,
            interest_minor=interest,
            total_minor=principal + interest,
        )
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    for holder, amount, share in ((investor, 10_000_00, 333_333), (other, 20_000_00, 666_667)):
        holding_model.objects.create(
            loan=loan,
            investor_user_id=holder.pk,
            source_type="primary_market",
            source_id=f"year-end-order-{holder.pk}",
            status="active",
            original_principal_minor=amount,
            current_principal_minor=amount,
            currency=currency,
            loan_share_ppm=share,
            assignment_effective_at=_at(date(2025, 12, 1)),
            created_by_admin_id=admin_user.pk,
            idempotency_key=f"year-end-holding-{holder.pk}",
        )
    return cast(Model, loan)


@pytest.mark.django_db
def test_lender_tax_information_groups_direct_interest_by_value_date(
    admin_user: Model,
    investor: Model,
) -> None:
    # FINCODE-14: a repayment with value date 31 Dec recorded on 4 Jan landed in the next year.
    servicing: Any = import_module("backend.apps.servicing.services")
    factory: Any = import_module("backend.apps.servicing.tests.test_servicing_repayments")
    other = get_user_model().objects.create_user(
        email="statement-other@example.test",
        full_name="Other Investor",
        account_type="natural_person_lender",
        status="active",
    )
    _approve_lender(investor)
    loan = _year_end_loan(admin_user, investor, other)
    with freeze_time("2026-01-04T12:00:00Z"):
        servicing.record_borrower_repayment(
            factory._repayment_command(
                admin_user,
                loan,
                booking_date=date(2025, 12, 31),
                value_date=date(2025, 12, 31),
                idempotency_key="tax-year-end-repayment",
            )
        )

    def year(start: date, end: date) -> dict[str, int]:
        with freeze_time("2026-02-01T12:00:00Z"):
            artifact = generate_investor_self_service_report(
                GenerateInvestorSelfServiceReportCommand(
                    actor=investor,
                    report_type=ReportType.ANNUAL_TAX_INFORMATION,
                    start_date=start,
                    end_date=end,
                    output_format=ReportOutputFormat.CSV,
                )
            )
        return {row["category"]: int(row["amount_minor"]) for row in _csv_rows(artifact.content)}

    year_2025 = year(date(2025, 1, 1), date(2025, 12, 31))
    january_2026 = year(date(2026, 1, 1), date(2026, 1, 31))
    # One third of 300.00 interest and 3'000.00 principal belongs to this investor.
    assert year_2025["interest_received_or_credited"] == 100_00
    assert year_2025["principal_repaid"] == 1_000_00
    assert "interest_received_or_credited" not in january_2026


@pytest.mark.django_db
def test_statement_lists_money_in_first_when_entries_share_a_timestamp(
    admin_user: Model,
    investor: Model,
) -> None:
    # A pinned QA clock gives every entry of the day the same recording time. The order must
    # still be sensible: money in before money out, so the running balance cannot dip.
    ledger: Any = import_module("backend.apps.ledger.services")
    _approve_lender(investor)
    loan = _loan(admin_user, title="Same Day Loan", funding_deadline=date(2026, 2, 20))
    with freeze_time("2026-01-04T09:00:00Z"):
        _deposit(admin_user, investor, amount_minor=1_000_00, value_date=date(2026, 1, 4))
    with freeze_time("2026-01-05T09:00:00Z"):
        ledger.reserve_investor_balance_for_investment(
            ledger.ReserveInvestmentBalanceCommand(
                actor=admin_user,
                investor_user_id=str(investor.pk),
                loan_id=str(loan.pk),
                amount_minor=600_00,
                currency="CHF",
                loan_funding_deadline=date(2026, 2, 20),
                source_type="primary_investment_order",
                source_id="same-day-order",
                idempotency_key="same-day-reserve",
                as_of=_at(date(2026, 1, 5)),
            )
        )
        _deposit(admin_user, investor, amount_minor=500_00, value_date=date(2026, 1, 5))
    rows = _csv_rows(_statement(investor, date(2026, 1, 5), date(2026, 1, 31), "csv").content)
    movements = [row for row in rows if row["row_type"] == "movement"]
    assert rows[0]["balance"] == "1000.00"
    assert [row["amount"] for row in movements] == ["500.00", "-600.00"]
    assert [row["balance"] for row in movements] == ["1500.00", "900.00"]
