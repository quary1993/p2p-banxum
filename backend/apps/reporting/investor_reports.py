"""IP of Webby-Soft SRL. The design's investor reports (IMPLEMENTATION_PLAN 18.3, #/reports).

An investor creates four reports for a period and a currency, as PDF or CSV:

- Account statement: money received, invested, sent back and withdrawn (the existing statement).
- Portfolio report: the investments, what is outstanding and their status, as of today.
- Interest and repayments: every payment credited, split into principal and interest.
- Tax report: interest received per borrower country and currency. It is information for the
  investor's tax return, not an official tax certificate (Vlad, E-09).

The platform also creates a monthly account statement for each investor with activity. Each
report is kept as issued (InvestorReportDocument) and announced with a "Document ready" notice.
EUR and CHF are always reported separately; amounts are never converted.
"""

from __future__ import annotations

import base64
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model, Q

from backend.apps.platform_core.domain.money import minor_units_to_decimal
from backend.apps.platform_core.domain.time import business_date, business_timezone, now_utc
from backend.apps.platform_core.services.events import OutboxCommand, enqueue_outbox_message
from backend.apps.reporting import services as reporting
from backend.apps.reporting.models import (
    InvestorReportDocument,
    InvestorReportKind,
    ReportOutputFormat,
    ReportType,
)

DOCUMENT_READY_TOPIC = "notice.document_ready"
TAX_REPORT_NOTICE = (
    "This report is information for your tax return. It is not an official tax certificate. "
    "Interest is shown in the currency in which it was paid, per borrower country, without "
    "conversion. Check the rules that apply to you with your tax office or adviser."
)
REPORT_KIND_TYPES = {
    InvestorReportKind.ACCOUNT_STATEMENT: ReportType.PARTICIPANT_ACCOUNT_STATEMENT,
    InvestorReportKind.MONTHLY_STATEMENT: ReportType.PARTICIPANT_ACCOUNT_STATEMENT,
    InvestorReportKind.PORTFOLIO: ReportType.INVESTOR_PORTFOLIO,
    InvestorReportKind.INTEREST_REPAYMENTS: ReportType.INVESTOR_INTEREST_REPAYMENTS,
    InvestorReportKind.TAX: ReportType.INVESTOR_TAX_REPORT,
}
REPORT_CURRENCIES = ("EUR", "CHF")
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


class InvestorReportError(RuntimeError):
    pass


def _model(app_label: str, model_name: str) -> Any:
    return reporting._external_model(app_label, model_name)


def _minor_units(code: str) -> int:
    units = (
        _model("platform_core", "Currency")
        .objects.filter(code=code)
        .values_list("minor_units", flat=True)
        .first()
    )
    return 2 if units is None else int(units)


def _major(amount_minor: int, code: str) -> Decimal:
    units = _minor_units(code)
    quantum = Decimal(1).scaleb(-units)
    return minor_units_to_decimal(int(amount_minor), minor_units=units).quantize(quantum)


def _country(loan: Any) -> str:
    if str(getattr(loan, "product_type", "direct")) == "originator_claim":
        profile = getattr(loan, "originator_profile", None)
        return str(getattr(profile, "borrower_country", "") or "").upper()
    return str(getattr(getattr(loan, "borrower", None), "country", "") or "").upper()


def _currency_filter(filters: dict[str, Any]) -> str:
    return str(filters.get("currency", "") or "").upper()


def _date_text(value: date) -> str:
    return reporting._statement_date_text(value)


def _period_text(start_date: date, end_date: date) -> str:
    return f"{_date_text(start_date)} to {_date_text(end_date)}"


@dataclass(frozen=True, slots=True)
class _Table:
    heading: str
    columns: tuple[tuple[str, float, str], ...]
    rows: list[list[str]]
    total: list[str] | None = None


def _amount_text(value: Decimal | int | None, code: str) -> str:
    if value is None:
        return ""
    minor = int(value) if isinstance(value, int) else int(value.scaleb(_minor_units(code)))
    return reporting._major_amount_text(minor, _minor_units(code))


# --- Portfolio report ---------------------------------------------------------------------------

PORTFOLIO_COLUMNS = [
    "Investment",
    "Project",
    "Borrower country",
    "Currency",
    "Invested on",
    "Invested",
    "Outstanding",
    "Interest received",
    "Status",
]


def _holding_status(holding: Any) -> str:
    loan_status = str(getattr(holding.loan, "status", ""))
    if str(holding.status) == "transferred":
        return "Sold"
    if str(holding.status) == "closed":
        return {"repaid": "Repaid", "written_off": "Written off"}.get(loan_status, "Closed")
    return {
        "late": "Late",
        "defaulted": "Default",
        "written_off": "Written off",
        "funded": "Funded, payments not started",
        "repaid": "Repaid",
    }.get(loan_status, "On schedule")


def _interest_by_holding(investor_user_id: str, holding_ids: list[str]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    if not investor_user_id or not holding_ids:
        return {}
    for model in (
        _model("servicing", "InvestorRepaymentDistributionLine"),
        _model("originator_claims", "InvestorOriginatorRepaymentDistributionLine"),
    ):
        for holding_id, interest in model.objects.filter(
            investor_user_id=investor_user_id, holding_id__in=holding_ids
        ).values_list("holding_id", "interest_minor"):
            totals[str(holding_id)] += int(interest or 0)
    for holding_id, interest in (
        _model("servicing", "InvestorRecoveryDistributionLine")
        .objects.filter(investor_user_id=investor_user_id, holding_id__in=holding_ids)
        .values_list("holding_id", "contractual_interest_minor")
    ):
        totals[str(holding_id)] += int(interest or 0)
    return dict(totals)


def portfolio_dataset(
    *, start_date: date, end_date: date, redaction_mode: str, filters: dict[str, Any]
) -> reporting.ReportDataset:
    """Every investment of the investor, as of the end of the period (today)."""
    investor_user_id = str(filters.get("participant_id") or "")
    currency = _currency_filter(filters)
    # A personal report: without an investor (an admin export of every type) it has no rows.
    holdings = list(
        _model("holdings", "InvestorLoanHolding")
        .objects.filter(investor_user_id=investor_user_id or None)
        .select_related("currency", "loan", "loan__borrower", "loan__originator_profile")
        .order_by("currency__code", "assignment_effective_at", "id")
    )
    if currency:
        holdings = [holding for holding in holdings if holding.currency.code == currency]
    interest = _interest_by_holding(investor_user_id, [str(holding.pk) for holding in holdings])
    rows: list[dict[str, Any]] = []
    tables: dict[str, list[list[str]]] = defaultdict(list)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for holding in holdings:
        code = str(holding.currency.code)
        invested_on = business_date(holding.assignment_effective_at)
        received = interest.get(str(holding.pk), 0)
        status = _holding_status(holding)
        country = _country(holding.loan)
        row: dict[str, Any] = {
            "Investment": str(holding.pk),
            "Project": str(holding.loan.title),
            "Borrower country": country,
            "Currency": code,
            "Invested on": invested_on,
            "Invested": _major(int(holding.original_principal_minor), code),
            "Outstanding": _major(int(holding.current_principal_minor), code),
            "Interest received": _major(received, code),
            "Status": status,
        }
        rows.append(row)
        tables[code].append(
            [
                str(holding.loan.title),
                country,
                _date_text(invested_on),
                _amount_text(int(holding.original_principal_minor), code),
                _amount_text(int(holding.current_principal_minor), code),
                _amount_text(received, code),
                status,
            ]
        )
        totals[code][0] += int(holding.original_principal_minor)
        totals[code][1] += int(holding.current_principal_minor)
        totals[code][2] += received
    columns = (
        ("Project", 250.0, "left"),
        ("Country", 60.0, "left"),
        ("Invested on", 74.0, "left"),
        ("Invested", 92.0, "right"),
        ("Outstanding", 92.0, "right"),
        ("Interest received", 92.0, "right"),
        ("Status", reporting.PDF_CONTENT_WIDTH - 660.0, "left"),
    )
    presentation_tables = [
        _Table(
            heading=f"{code} investments",
            columns=columns,
            rows=tables[code],
            total=[
                "Total",
                "",
                "",
                _amount_text(totals[code][0], code),
                _amount_text(totals[code][1], code),
                _amount_text(totals[code][2], code),
                "",
            ],
        )
        for code in sorted(tables, key=_currency_rank)
    ]
    return reporting.ReportDataset(
        columns=PORTFOLIO_COLUMNS,
        rows=rows,
        source_counts={"holdings": len(rows)},
        notes=[
            f"Your investments on {_date_text(end_date)}. Outstanding is the principal still "
            "owed to you. EUR and CHF are reported separately."
        ],
        presentation={
            "investor_table": {
                "title": "Portfolio report",
                "period_text": f"As of {_date_text(end_date)}",
                "participant_id": investor_user_id,
                "tables": presentation_tables,
            }
        },
    )


# --- Interest and repayments ------------------------------------------------------------------

INCOME_COLUMNS = [
    "Date",
    "Project",
    "Borrower country",
    "Currency",
    "Type",
    "Principal",
    "Interest",
    "Late interest and charges",
    "Fees",
    "Credited",
]


@dataclass(frozen=True, slots=True)
class _Payment:
    value_date: date
    loan: Any
    currency: str
    kind: str
    principal: int
    interest: int
    late: int
    fees: int
    credited: int


def _payments(
    *, investor_user_id: str, start_date: date, end_date: date, currency: str
) -> list[_Payment]:
    """Payments credited to the investor in the period, by value date."""
    payments: list[_Payment] = []
    if not investor_user_id:
        # A personal report: without an investor (an admin export of every type) it has no rows.
        return payments
    repayment_lines = (
        _model("servicing", "InvestorRepaymentDistributionLine")
        .objects.filter(
            investor_user_id=investor_user_id,
            repayment_event__value_date__gte=start_date,
            repayment_event__value_date__lte=end_date,
        )
        .select_related(
            "currency",
            "repayment_event",
            "holding__loan__borrower",
            "holding__loan__originator_profile",
        )
    )
    for line in repayment_lines:
        payments.append(
            _Payment(
                value_date=line.repayment_event.value_date,
                loan=line.holding.loan,
                currency=str(line.currency.code),
                kind="Repayment",
                principal=int(line.principal_minor),
                interest=int(line.interest_minor),
                late=0,
                fees=int(line.fee_minor),
                credited=int(line.amount_minor),
            )
        )
    originator_lines = (
        _model("originator_claims", "InvestorOriginatorRepaymentDistributionLine")
        .objects.filter(
            investor_user_id=investor_user_id,
            repayment__value_date__gte=start_date,
            repayment__value_date__lte=end_date,
        )
        .select_related(
            "currency", "repayment", "holding__loan__borrower", "holding__loan__originator_profile"
        )
    )
    for line in originator_lines:
        payments.append(
            _Payment(
                value_date=line.repayment.value_date,
                loan=line.holding.loan,
                currency=str(line.currency.code),
                kind="Repayment",
                principal=int(line.principal_minor),
                interest=int(line.interest_minor),
                late=int(line.penalty_minor),
                fees=0,
                credited=int(line.amount_minor),
            )
        )
    recovery_lines = (
        _model("servicing", "InvestorRecoveryDistributionLine")
        .objects.filter(
            investor_user_id=investor_user_id,
            recovery_event__value_date__gte=start_date,
            recovery_event__value_date__lte=end_date,
        )
        .select_related(
            "currency",
            "recovery_event",
            "holding__loan__borrower",
            "holding__loan__originator_profile",
        )
    )
    for line in recovery_lines:
        payments.append(
            _Payment(
                value_date=line.recovery_event.value_date,
                loan=line.holding.loan,
                currency=str(line.currency.code),
                kind="Recovery",
                principal=int(line.principal_minor),
                interest=int(line.contractual_interest_minor),
                late=int(line.default_interest_minor) + int(line.penalties_minor),
                fees=0,
                credited=int(line.amount_minor),
            )
        )
    if currency:
        payments = [payment for payment in payments if payment.currency == currency]
    return sorted(payments, key=lambda payment: (payment.currency, payment.value_date))


def _currency_rank(code: str) -> tuple[int, str]:
    return (0 if code == "EUR" else 1 if code == "CHF" else 2, code)


def interest_repayments_dataset(
    *, start_date: date, end_date: date, redaction_mode: str, filters: dict[str, Any]
) -> reporting.ReportDataset:
    investor_user_id = str(filters.get("participant_id") or "")
    payments = _payments(
        investor_user_id=investor_user_id,
        start_date=start_date,
        end_date=end_date,
        currency=_currency_filter(filters),
    )
    rows: list[dict[str, Any]] = []
    tables: dict[str, list[list[str]]] = defaultdict(list)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for payment in payments:
        code = payment.currency
        rows.append(
            {
                "Date": payment.value_date,
                "Project": str(payment.loan.title),
                "Borrower country": _country(payment.loan),
                "Currency": code,
                "Type": payment.kind,
                "Principal": _major(payment.principal, code),
                "Interest": _major(payment.interest, code),
                "Late interest and charges": _major(payment.late, code),
                "Fees": _major(payment.fees, code),
                "Credited": _major(payment.credited, code),
            }
        )
        tables[code].append(
            [
                _date_text(payment.value_date),
                f"{payment.loan.title} ({payment.kind.lower()})",
                _amount_text(payment.principal, code),
                _amount_text(payment.interest, code),
                _amount_text(payment.late, code),
                _amount_text(payment.fees, code),
                _amount_text(payment.credited, code),
            ]
        )
        for index, value in enumerate(
            (payment.principal, payment.interest, payment.late, payment.fees, payment.credited)
        ):
            totals[code][index] += value
    columns = (
        ("Date", 66.0, "left"),
        ("Project", 266.0, "left"),
        ("Principal", 86.0, "right"),
        ("Interest", 86.0, "right"),
        ("Late interest", 86.0, "right"),
        ("Fees", 70.0, "right"),
        ("Credited", reporting.PDF_CONTENT_WIDTH - 660.0, "right"),
    )
    presentation_tables = [
        _Table(
            heading=f"{code} payments",
            columns=columns,
            rows=tables[code],
            total=["", "Total", *(_amount_text(value, code) for value in totals[code])],
        )
        for code in sorted(tables, key=_currency_rank)
    ]
    return reporting.ReportDataset(
        columns=INCOME_COLUMNS,
        rows=rows,
        source_counts={"payments": len(rows)},
        notes=[
            "Every payment credited to your Banxum balance in the period, by value date, split "
            "into principal and interest. EUR and CHF are reported separately."
        ],
        presentation={
            "investor_table": {
                "title": "Interest and repayments",
                "period_text": _period_text(start_date, end_date),
                "participant_id": investor_user_id,
                "tables": presentation_tables,
            }
        },
    )


# --- Tax report -------------------------------------------------------------------------------

TAX_COLUMNS = [
    "Borrower country",
    "Currency",
    "Interest received",
    "Late interest and charges",
    "Payments",
]


def tax_report_dataset(
    *, start_date: date, end_date: date, redaction_mode: str, filters: dict[str, Any]
) -> reporting.ReportDataset:
    investor_user_id = str(filters.get("participant_id") or "")
    payments = _payments(
        investor_user_id=investor_user_id,
        start_date=start_date,
        end_date=end_date,
        currency=_currency_filter(filters),
    )
    grouped: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for payment in payments:
        key = (payment.currency, _country(payment.loan) or "-")
        grouped[key][0] += payment.interest
        grouped[key][1] += payment.late
        grouped[key][2] += 1
    rows: list[dict[str, Any]] = []
    tables: dict[str, list[list[str]]] = defaultdict(list)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for code, country in sorted(grouped, key=lambda key: (_currency_rank(key[0]), key[1])):
        interest, late, count = grouped[(code, country)]
        rows.append(
            {
                "Borrower country": country,
                "Currency": code,
                "Interest received": _major(interest, code),
                "Late interest and charges": _major(late, code),
                "Payments": count,
            }
        )
        tables[code].append(
            [country, _amount_text(interest, code), _amount_text(late, code), str(count)]
        )
        totals[code][0] += interest
        totals[code][1] += late
        totals[code][2] += count
    columns = (
        ("Borrower country", 260.0, "left"),
        ("Interest received", 160.0, "right"),
        ("Late interest and charges", 160.0, "right"),
        ("Payments", reporting.PDF_CONTENT_WIDTH - 580.0, "right"),
    )
    presentation_tables = [
        _Table(
            heading=f"Interest received in {code}",
            columns=columns,
            rows=tables[code],
            total=[
                "Total",
                _amount_text(totals[code][0], code),
                _amount_text(totals[code][1], code),
                str(totals[code][2]),
            ],
        )
        for code in sorted(tables, key=_currency_rank)
    ]
    return reporting.ReportDataset(
        columns=TAX_COLUMNS,
        rows=rows,
        source_counts={"payments": len(payments)},
        notes=[TAX_REPORT_NOTICE],
        presentation={
            "investor_table": {
                "title": "Tax report",
                "period_text": _period_text(start_date, end_date),
                "participant_id": investor_user_id,
                "tables": presentation_tables,
            }
        },
    )


DATASET_BUILDERS: dict[str, Callable[..., reporting.ReportDataset]] = {
    ReportType.INVESTOR_PORTFOLIO: portfolio_dataset,
    ReportType.INVESTOR_INTEREST_REPAYMENTS: interest_repayments_dataset,
    ReportType.INVESTOR_TAX_REPORT: tax_report_dataset,
}


def investor_table_pdf(*, manifest: dict[str, Any], dataset: reporting.ReportDataset) -> bytes:
    """One investor's report: an account box, the notes, one table per currency."""
    presentation = dataset.presentation["investor_table"]
    title = str(presentation["title"])
    participant_id = str(presentation.get("participant_id") or "")
    labels = reporting._investor_labels(
        [participant_id] if participant_id else [], redaction_mode="full"
    )
    label = labels.get(participant_id, {"reference": "", "name": ""})
    generated_on = business_date(datetime.fromisoformat(str(manifest["generated_at"])))
    canvas = reporting._PdfReportCanvas()
    bottom_limit = reporting.PDF_MARGIN_BOTTOM + 26
    y = reporting._pdf_page_header(canvas, report_title=title, compact=False)
    canvas.text(x=reporting.PDF_MARGIN_X, y=y, text=title, size=18, font="F2")
    canvas.text(
        x=reporting.PDF_MARGIN_X,
        y=y - 17,
        text=str(presentation["period_text"]),
        size=8.6,
        color=reporting.PDF_MUTED,
    )
    y -= 38
    currency = str(manifest.get("filters", {}).get("currency") or "")
    y = reporting._pdf_key_value_box(
        canvas,
        x=reporting.PDF_MARGIN_X,
        y=y,
        width=(reporting.PDF_CONTENT_WIDTH - 14) / 2,
        title="Account",
        items=[
            ("Investor", label["name"] or "-"),
            ("Investor reference", label["reference"] or "-"),
            ("Period", str(presentation["period_text"])),
            ("Currency", currency or "EUR and CHF, reported separately"),
            ("Created on", _date_text(generated_on)),
        ],
    )
    y = reporting._pdf_notes_box(canvas, y=y - 14, notes=dataset.notes)
    tables: list[_Table] = presentation["tables"]

    def new_page() -> float:
        canvas.new_page()
        return reporting._pdf_page_header(canvas, report_title=title, compact=True)

    if not tables:
        canvas.text(
            x=reporting.PDF_MARGIN_X,
            y=y - 8,
            text="Nothing to report for this period.",
            size=9,
            font="F2",
        )
    for table in tables:
        if y < bottom_limit + 70:
            y = new_page()
        canvas.text(
            x=reporting.PDF_MARGIN_X,
            y=y - 4,
            text=table.heading,
            size=11.5,
            font="F2",
            color=reporting.PDF_PRIMARY,
        )
        y = reporting._statement_table_header(canvas, y=y - 12, columns=table.columns)
        body: list[tuple[list[str], bool]] = [(row, False) for row in table.rows]
        if table.total is not None:
            body.append((table.total, True))
        for index, (cells, bold) in enumerate(body):
            height = reporting._statement_row_height(cells, bold=bold, columns=table.columns)
            if y - height < bottom_limit:
                y = new_page()
                canvas.text(
                    x=reporting.PDF_MARGIN_X,
                    y=y - 4,
                    text=f"{table.heading} (continued)",
                    size=9,
                    font="F2",
                    color=reporting.PDF_PRIMARY,
                )
                y = reporting._statement_table_header(canvas, y=y - 12, columns=table.columns)
            fill = (
                reporting.PDF_TOTAL_FILL
                if bold
                else (reporting.PDF_ROW_ALT_FILL if index % 2 == 0 else (255, 255, 255))
            )
            y = reporting._statement_table_row(
                canvas, y=y, cells=cells, bold=bold, fill=fill, columns=table.columns
            )
        y -= 22
    page_count = len(canvas.pages)
    for page_number in range(1, page_count + 1):
        reporting._pdf_footer(
            canvas,
            page_number=page_number,
            page_count=page_count,
            label=(
                f"{settings.PLATFORM_BRAND_NAME} {title.lower()} for information. "
                f"Operator: {settings.LEGAL_OPERATOR_NAME}."
            ),
        )
    return reporting._pdf_document_bytes(canvas)


# --- Kept reports -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateInvestorReportCommand:
    actor: Model
    kind: str
    start_date: date
    end_date: date
    output_format: str = ReportOutputFormat.PDF
    currency: str = ""
    audit_actor: Model | None = None
    automatic: bool = False
    as_of: datetime | None = None


def _title(kind: str, start_date: date, end_date: date) -> str:
    label = str(InvestorReportKind(kind).label)
    if kind == InvestorReportKind.MONTHLY_STATEMENT:
        return f"Account statement {_MONTHS[start_date.month - 1]} {start_date.year}"
    if kind == InvestorReportKind.PORTFOLIO:
        return f"{label} as of {_date_text(end_date)}"
    return label


def report_payload(document: InvestorReportDocument) -> dict[str, Any]:
    return {
        "id": str(document.pk),
        "kind": str(document.kind),
        "title": _title(str(document.kind), document.start_date, document.end_date),
        "currency": str(document.currency),
        "start_date": document.start_date,
        "end_date": document.end_date,
        "output_format": str(document.output_format),
        "filename": str(document.filename),
        "issued_at": document.issued_at,
        "automatic": bool(document.automatic),
    }


def _enqueue_document_ready(document: InvestorReportDocument, *, user: Any) -> None:
    """In-app "Document ready" notice (never emailed), opening Reports."""
    title = _title(str(document.kind), document.start_date, document.end_date)
    message = enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"report-ready:{document.pk}",
            topic=DOCUMENT_READY_TOPIC,
            payload={
                "user_id": str(document.investor_user_id),
                "email": str(getattr(user, "email", "") or ""),
                "subject": "Document ready",
                "body_text": f"Your {title} is ready.",
                "metadata": {
                    "navigation_target": "reports",
                    "navigation_target_id": "",
                    "report_id": str(document.pk),
                    "category": "neutral",
                },
            },
        )
    )
    # Not an email topic, so no sender picks it up: done once it is listed.
    outbox_model = type(message)
    outbox_model.objects.filter(pk=message.pk).update(status="processed", processed_at=now_utc())


def create_investor_report(command: CreateInvestorReportCommand) -> dict[str, Any]:
    """Generate, keep and announce one report of the investor."""
    try:
        kind = InvestorReportKind(command.kind)
    except ValueError as exc:
        raise InvestorReportError("Choose a report type.") from exc
    currency = command.currency.upper().strip()
    if currency and currency not in REPORT_CURRENCIES:
        raise InvestorReportError("Choose EUR, CHF or both currencies.")
    if command.output_format not in {ReportOutputFormat.PDF, ReportOutputFormat.CSV}:
        raise InvestorReportError("Choose PDF or CSV.")
    start_date, end_date = command.start_date, command.end_date
    today = business_date(command.as_of or now_utc())
    if kind == InvestorReportKind.PORTFOLIO:
        # The portfolio is always as of today (design: "As of …").
        start_date = end_date = today
    if end_date < start_date:
        raise InvestorReportError("The period must end on or after its first day.")
    if end_date > today:
        raise InvestorReportError("A report cannot end after today.")
    with transaction.atomic():
        artifact = reporting.generate_investor_self_service_report(
            reporting.GenerateInvestorSelfServiceReportCommand(
                actor=command.actor,
                participant_actor=command.actor,
                audit_actor=command.audit_actor or command.actor,
                report_type=REPORT_KIND_TYPES[kind],
                start_date=start_date,
                end_date=end_date,
                output_format=command.output_format,
                as_of=command.as_of,
                extra_filters={"currency": currency} if currency else None,
            )
        )
        document = _keep_document(
            artifact,
            investor=command.actor,
            kind=kind,
            currency=currency,
            start_date=start_date,
            end_date=end_date,
            output_format=command.output_format,
            issued_at=command.as_of or now_utc(),
            automatic=command.automatic,
            created_by=command.audit_actor or command.actor,
        )
    return report_payload(document)


def _keep_document(
    artifact: Any,
    *,
    investor: Any,
    kind: str,
    currency: str,
    start_date: date,
    end_date: date,
    output_format: str,
    issued_at: datetime,
    automatic: bool,
    created_by: Any,
) -> InvestorReportDocument:
    """Keep the issued file (append-only) and announce it in the app."""
    document: InvestorReportDocument = InvestorReportDocument.objects.create(
        investor_user_id=investor.pk,
        kind=kind,
        currency=currency,
        start_date=start_date,
        end_date=end_date,
        output_format=output_format,
        filename=artifact.filename,
        content_type=artifact.content_type,
        content_encoding=artifact.content_encoding,
        content=artifact.content,
        content_sha256=str(artifact.manifest["content_sha256"]),
        issued_at=issued_at,
        automatic=automatic,
        report_run=artifact.report_run,
        created_by_user_id=created_by.pk,
    )
    _enqueue_document_ready(document, user=investor)
    return document


def create_automatic_monthly_statement(
    *, investor: Any, start_date: date, end_date: date, as_of: datetime
) -> dict[str, Any]:
    """Audit S2-3: the month's statement through the system path (no self-service access
    check), kept as an automatic document."""
    with transaction.atomic():
        artifact = reporting.generate_investor_scheduled_statement(
            reporting.GenerateInvestorScheduledStatementCommand(
                participant_actor=investor,
                start_date=start_date,
                end_date=end_date,
                as_of=as_of,
            )
        )
        document = _keep_document(
            artifact,
            investor=investor,
            kind=InvestorReportKind.MONTHLY_STATEMENT,
            currency="",
            start_date=start_date,
            end_date=end_date,
            output_format=ReportOutputFormat.PDF,
            issued_at=as_of,
            automatic=True,
            created_by=investor,
        )
    return report_payload(document)


def list_investor_reports(*, investor_user_id: str) -> list[dict[str, Any]]:
    return [
        report_payload(document)
        for document in InvestorReportDocument.objects.filter(
            investor_user_id=investor_user_id
        ).order_by("-issued_at", "-id")
    ]


def investor_report_file(*, investor_user_id: str, report_id: str) -> dict[str, Any]:
    document = InvestorReportDocument.objects.filter(
        pk=report_id, investor_user_id=investor_user_id
    ).first()
    if document is None:
        raise InvestorReportError("Report not found.")
    return {
        "content_type": str(document.content_type),
        "filename": str(document.filename),
        "content_encoding": str(document.content_encoding),
        "content": str(document.content),
        "content_sha256": str(document.content_sha256),
        "manifest": dict(document.report_run.manifest or {}),
    }


def investor_report_bytes(*, investor_user_id: str, report_id: str) -> tuple[bytes, str, str]:
    """The kept file as bytes, its content type and file name (for the in-app reader)."""
    payload = investor_report_file(investor_user_id=investor_user_id, report_id=report_id)
    content = str(payload["content"])
    data = (
        base64.b64decode(content.encode("ascii"))
        if payload["content_encoding"] == reporting.BASE64_CONTENT_ENCODING
        else content.encode("utf-8")
    )
    return data, str(payload["content_type"]), str(payload["filename"])


def investor_report_summary(*, investor_user_id: str, year: int | None) -> dict[str, Any]:
    """The Reports page summary: invested, principal repaid and interest received per currency."""
    if year is None:
        start_date, end_date = date(2000, 1, 1), business_date(now_utc())
    else:
        start_date, end_date = date(year, 1, 1), date(year, 12, 31)
    payments = _payments(
        investor_user_id=investor_user_id, start_date=start_date, end_date=end_date, currency=""
    )
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"invested_minor": 0, "principal_repaid_minor": 0, "interest_received_minor": 0}
    )
    for payment in payments:
        totals[payment.currency]["principal_repaid_minor"] += payment.principal
        totals[payment.currency]["interest_received_minor"] += payment.interest + payment.late
    # Audit S2-5: local (Europe/Zurich) midnights, like the payment periods; not UTC.
    zone = business_timezone()
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=zone)
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=zone)
    for holding in (
        _model("holdings", "InvestorLoanHolding")
        .objects.filter(
            investor_user_id=investor_user_id,
            assignment_effective_at__gte=start_dt,
            assignment_effective_at__lt=end_dt,
        )
        .select_related("currency")
    ):
        totals[str(holding.currency.code)]["invested_minor"] += int(
            holding.original_principal_minor
        )
    currencies = sorted(set(totals) | set(REPORT_CURRENCIES), key=_currency_rank)
    return {
        "year": year,
        "start_date": start_date,
        "end_date": end_date,
        "currencies": [{"currency": code, **totals[code]} for code in currencies],
    }


MONTHLY_STATEMENT_TASK_TYPE = "InvestorMonthlyStatement"


def generate_monthly_statements(*, as_of: datetime, actor: Any = None) -> dict[str, Any]:
    """On the 1st (and later days, idempotently): last month's statement for each investor with
    money movements in that month. Audit S2-3: generated with system authority, so an investor
    whose access has ended still gets the statement; a failure opens one operations task per
    investor and month (``actor`` is the scheduled-job admin who opens it)."""
    today = business_date(as_of)
    first_of_month = today.replace(day=1)
    end_date = first_of_month - timedelta(days=1)
    start_date = end_date.replace(day=1)
    month = start_date.isoformat()[:7]
    posting_model = _model("ledger", "LedgerPosting")
    investor_ids = {
        str(owner_id)
        for owner_id in posting_model.objects.filter(
            account__owner_type="investor",
            account__account_type="investor_balance_liability",
            journal_entry__value_date__gte=start_date,
            journal_entry__value_date__lte=end_date,
        ).values_list("account__owner_id", flat=True)
    }
    existing = set(
        InvestorReportDocument.objects.filter(
            kind=InvestorReportKind.MONTHLY_STATEMENT, start_date=start_date, automatic=True
        ).values_list("investor_user_id", flat=True)
    )
    user_model = _model("accounts_auth", "User")
    created = 0
    failed: list[str] = []
    for user in user_model.objects.filter(pk__in=investor_ids).exclude(
        Q(pk__in=list(existing))
    ):
        try:
            create_automatic_monthly_statement(
                investor=user, start_date=start_date, end_date=end_date, as_of=as_of
            )
            created += 1
        except IntegrityError:
            # A parallel run kept this month's statement first: nothing is missing.
            continue
        except (reporting.ReportingError, InvestorReportError) as exc:
            failed.append(str(user.pk))
            _open_statement_failure_task(actor=actor, investor=user, month=month, error=exc)
    return {
        "month": month,
        "statements_created": created,
        "statements_failed": len(failed),
        "failed_investor_ids": failed,
    }


def _open_statement_failure_task(
    *, actor: Any, investor: Any, month: str, error: Exception
) -> None:
    """One operations task per investor and month; the next daily run retries the statement."""
    if actor is None:
        return
    admin_ops: Any = import_module("backend.apps.admin_ops.services")
    admin_ops.ensure_related_admin_task(
        actor=actor,
        task_type="reporting",
        related_object_type=MONTHLY_STATEMENT_TASK_TYPE,
        related_object_id=f"{investor.pk}:{month}",
        title=f"Monthly statement {month} not generated",
        priority="high",
        notes=(
            f"The automatic account statement for {month} could not be generated for investor "
            f"{investor.pk}: {error}. The daily job retries it; close this task when the "
            "statement is in the investor's Reports."
        ),
    )


__all__ = [
    "DATASET_BUILDERS",
    "DOCUMENT_READY_TOPIC",
    "TAX_REPORT_NOTICE",
    "CreateInvestorReportCommand",
    "InvestorReportError",
    "create_automatic_monthly_statement",
    "create_investor_report",
    "generate_monthly_statements",
    "investor_report_bytes",
    "investor_report_file",
    "investor_report_summary",
    "investor_table_pdf",
    "list_investor_reports",
]
