from __future__ import annotations

import base64
import calendar
import csv
import hashlib
import io
import json
import textwrap
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from django.apps import apps
from django.db import transaction
from django.db.models import Model

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.time import (
    business_timezone,
    calendar_day_difference,
    now_utc,
)
from backend.apps.platform_core.models import AuditEvent
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event
from backend.apps.reporting.models import (
    ReportEvent,
    ReportEventType,
    ReportOutputFormat,
    ReportPeriodPreset,
    ReportRedactionMode,
    ReportRun,
    ReportType,
)


class ReportingError(ValueError):
    pass


class ReportingAuthorizationError(ReportingError):
    pass


class ReportingValidationError(ReportingError):
    pass


REPORT_DEFINITION_VERSION = "reporting-v2"
CSV_CONTENT_TYPE = "text/csv; charset=utf-8"
PDF_CONTENT_TYPE = "application/pdf"
ZIP_CONTENT_TYPE = "application/zip"
TEXT_CONTENT_ENCODING = "text"
BASE64_CONTENT_ENCODING = "base64"
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
CSV_FORMULA_LEADING_CHARS = ("\t", "\r", "\n")
ANNUAL_TAX_INFORMATION_DISCLAIMER = (
    "This report is informational only and is not tax advice. Final tax treatment remains "
    "the responsibility of the participant and its advisors."
)

REVENUE_ACCOUNT_TYPES = frozenset(
    {
        "garanta_accrued_revenue",
        "platform_fee_revenue",
        "fx_fee_revenue",
        "fx_gain_loss",
    }
)
PII_OWNER_TYPES = frozenset({"investor"})
DEFAULT_EXPOSURE_LOAN_STATUSES = frozenset({"late", "defaulted", "written_off"})


@dataclass(frozen=True, slots=True)
class GenerateReportCommand:
    actor: Model
    report_type: str
    start_date: date | None = None
    end_date: date | None = None
    period_preset: str = ReportPeriodPreset.CUSTOM
    period_anchor_date: date | None = None
    output_format: str = ReportOutputFormat.CSV
    redaction_mode: str = ReportRedactionMode.REDACTED
    filters: dict[str, Any] | None = None
    destination_note: str = ""
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReportPeriod:
    start_date: date
    end_date: date
    preset: str
    anchor_date: date | None = None


@dataclass(frozen=True, slots=True)
class ReportDataset:
    columns: list[str]
    rows: list[dict[str, Any]]
    source_counts: dict[str, int]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RenderedReport:
    content_type: str
    filename: str
    content: str
    content_encoding: str
    content_sha256: str
    included_files: list[dict[str, str]]


@dataclass(frozen=True, slots=True)
class GeneratedReportArtifact:
    report_run: ReportRun
    content_type: str
    filename: str
    content: str
    manifest: dict[str, Any]
    content_encoding: str = TEXT_CONTENT_ENCODING


def _external_model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def _ledger_model(model_name: str) -> Any:
    return _external_model("ledger", model_name)


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise ReportingAuthorizationError("Only an active admin can generate reports.")


def _report_type(value: str) -> str:
    try:
        return str(ReportType(value))
    except ValueError as exc:
        raise ReportingValidationError(f"Unsupported report type: {value}") from exc


def _output_format(value: str) -> str:
    try:
        return str(ReportOutputFormat(value))
    except ValueError as exc:
        raise ReportingValidationError(f"Unsupported report output format: {value}") from exc


def _redaction_mode(value: str) -> str:
    try:
        return str(ReportRedactionMode(value))
    except ValueError as exc:
        raise ReportingValidationError(f"Unsupported report redaction mode: {value}") from exc


def _period_preset(value: str) -> str:
    try:
        return str(ReportPeriodPreset(value))
    except ValueError as exc:
        raise ReportingValidationError(f"Unsupported report period preset: {value}") from exc


def _validate_date_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ReportingValidationError("Report end date must be on or after start date.")


def _resolve_report_period(
    *,
    start_date: date | None,
    end_date: date | None,
    period_preset: str,
    period_anchor_date: date | None,
    as_of: datetime,
) -> ReportPeriod:
    preset = _period_preset(period_preset)
    if preset == ReportPeriodPreset.CUSTOM:
        if start_date is None or end_date is None:
            raise ReportingValidationError(
                "Custom report periods require both start_date and end_date."
            )
        _validate_date_range(start_date, end_date)
        return ReportPeriod(start_date=start_date, end_date=end_date, preset=preset)

    anchor = period_anchor_date or as_of.astimezone(business_timezone()).date()
    if preset == ReportPeriodPreset.DAILY:
        resolved_start = anchor
        resolved_end = anchor
    elif preset == ReportPeriodPreset.WEEKLY:
        resolved_start = anchor - timedelta(days=anchor.weekday())
        resolved_end = resolved_start + timedelta(days=6)
    elif preset == ReportPeriodPreset.MONTHLY:
        resolved_start = anchor.replace(day=1)
        resolved_end = anchor.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])
    elif preset == ReportPeriodPreset.QUARTERLY:
        start_month = ((anchor.month - 1) // 3) * 3 + 1
        end_month = start_month + 2
        resolved_start = date(anchor.year, start_month, 1)
        resolved_end = date(
            anchor.year,
            end_month,
            calendar.monthrange(anchor.year, end_month)[1],
        )
    elif preset in {ReportPeriodPreset.YEARLY, ReportPeriodPreset.CALENDAR_YEAR}:
        resolved_start = date(anchor.year, 1, 1)
        resolved_end = date(anchor.year, 12, 31)
    else:
        raise ReportingValidationError(f"Unsupported report period preset: {preset}")
    return ReportPeriod(
        start_date=resolved_start,
        end_date=resolved_end,
        preset=preset,
        anchor_date=anchor,
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _redacted_identifier(value: Any, *, redaction_mode: str) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    if redaction_mode == ReportRedactionMode.FULL:
        return raw
    return "REDACTED"


def _redacted_text(value: Any, *, redaction_mode: str) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    if redaction_mode == ReportRedactionMode.FULL:
        return raw
    return "REDACTED"


def _redacted_json(value: Any, *, redaction_mode: str) -> str:
    if redaction_mode == ReportRedactionMode.FULL:
        return _stable_json(value or {})
    return "{}"


def _date_time_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    timezone = business_timezone()
    return (
        datetime.combine(start_date, time.min, tzinfo=timezone),
        datetime.combine(end_date, time.max, tzinfo=timezone),
    )


def _csv_cell(value: Any) -> str | int:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return value
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, dict | list):
        value = _stable_json(value)
    text = str(value)
    stripped = text.lstrip(" \t\r\n")
    if (
        text.startswith(CSV_FORMULA_LEADING_CHARS)
        or text.startswith(CSV_FORMULA_PREFIXES)
        or stripped.startswith(CSV_FORMULA_PREFIXES)
    ):
        return f"'{text}"
    return text


def _rows_to_csv(*, columns: list[str], rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _csv_cell(row.get(column)) for column in columns})
    return buffer.getvalue()


def _content_checksum_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _report_filename(
    *,
    report_type: str,
    start_date: date,
    end_date: date,
    extension: str,
) -> str:
    return f"{report_type}_{start_date.isoformat()}_{end_date.isoformat()}.{extension}"


def _apply_currency_filter(
    queryset: Any, filters: dict[str, Any], field_name: str = "currency"
) -> Any:
    currency_filter = str(filters.get("currency", "")).upper()
    if currency_filter:
        queryset = queryset.filter(**{f"{field_name}__code": currency_filter})
    return queryset


def _account_owner_id(account: Model, *, redaction_mode: str) -> str:
    owner_type = str(getattr(account, "owner_type", "") or "")
    owner_id = getattr(account, "owner_id", "") or ""
    if owner_type in PII_OWNER_TYPES:
        return _redacted_identifier(owner_id, redaction_mode=redaction_mode)
    return str(owner_id)


def _ledger_sign(side: str, amount_minor: int) -> int:
    return amount_minor if side == "debit" else -amount_minor


def _bexio_mapping_for_account(
    *,
    account_type: str,
    event_type: str,
    filters: dict[str, Any],
) -> dict[str, str]:
    mapping = filters.get("bexio_mapping") or filters.get("accounting_mapping") or {}
    if not isinstance(mapping, dict):
        mapping = {}
    account_type_mapping = mapping.get("account_types", {})
    event_type_mapping = mapping.get("event_types", {})
    if not isinstance(account_type_mapping, dict):
        account_type_mapping = {}
    if not isinstance(event_type_mapping, dict):
        event_type_mapping = {}
    configured = {}
    if isinstance(account_type_mapping.get(account_type), dict):
        configured.update(account_type_mapping[account_type])
    if isinstance(event_type_mapping.get(event_type), dict):
        configured.update(event_type_mapping[event_type])
    account_code = str(configured.get("account_code", ""))
    tax_code = str(configured.get("tax_code", ""))
    label = str(configured.get("label", ""))
    return {
        "bexio_account_code": account_code,
        "bexio_tax_code": tax_code,
        "bexio_label": label,
        "mapping_status": "configured" if account_code else "unmapped",
    }


def _operational_subledger_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    posting_model = _ledger_model("LedgerPosting")
    columns = [
        "journal_entry_id",
        "posting_id",
        "event_type",
        "direction",
        "booking_date",
        "value_date",
        "currency",
        "account_code",
        "account_type",
        "account_owner_type",
        "account_owner_id",
        "posting_side",
        "debit_minor",
        "credit_minor",
        "gross_amount_minor",
        "net_amount_minor",
        "source_type",
        "source_id",
        "lender_user_id",
        "borrower_id",
        "loan_id",
        "bank_operation_id",
        "bank_reference",
        "evidence_reference",
        "tax_metadata_json",
        "metadata_json",
        "reversal_of_id",
        "entry_created_at",
    ]
    queryset = (
        posting_model.objects.select_related(
            "journal_entry",
            "journal_entry__bank_operation",
            "journal_entry__reversal_of",
            "account",
            "currency",
        )
        .filter(
            journal_entry__value_date__gte=start_date,
            journal_entry__value_date__lte=end_date,
        )
        .order_by(
            "journal_entry__value_date",
            "journal_entry__created_at",
            "journal_entry__id",
            "id",
        )
    )
    queryset = _apply_currency_filter(queryset, filters)

    rows: list[dict[str, Any]] = []
    for posting in list(queryset):
        entry = posting.journal_entry
        account = posting.account
        side = str(posting.side)
        owner_type = str(account.owner_type or "")
        rows.append(
            {
                "journal_entry_id": str(entry.id),
                "posting_id": str(posting.id),
                "event_type": entry.event_type,
                "direction": entry.direction,
                "booking_date": entry.booking_date,
                "value_date": entry.value_date,
                "currency": posting.currency.code,
                "account_code": account.code,
                "account_type": account.account_type,
                "account_owner_type": owner_type,
                "account_owner_id": _account_owner_id(account, redaction_mode=redaction_mode),
                "posting_side": side,
                "debit_minor": posting.amount_minor if side == "debit" else 0,
                "credit_minor": posting.amount_minor if side == "credit" else 0,
                "gross_amount_minor": entry.gross_amount_minor,
                "net_amount_minor": entry.net_amount_minor,
                "source_type": entry.source_type,
                "source_id": entry.source_id,
                "lender_user_id": _redacted_identifier(
                    entry.lender_user_id,
                    redaction_mode=redaction_mode,
                ),
                "borrower_id": str(entry.borrower_id or ""),
                "loan_id": str(entry.loan_id or ""),
                "bank_operation_id": str(entry.bank_operation_id or ""),
                "bank_reference": _redacted_identifier(
                    entry.bank_reference,
                    redaction_mode=redaction_mode,
                ),
                "evidence_reference": _redacted_identifier(
                    entry.evidence_reference,
                    redaction_mode=redaction_mode,
                ),
                "tax_metadata_json": _redacted_json(
                    entry.tax_metadata,
                    redaction_mode=redaction_mode,
                ),
                "metadata_json": _redacted_json(entry.metadata, redaction_mode=redaction_mode),
                "reversal_of_id": str(entry.reversal_of_id or ""),
                "entry_created_at": entry.created_at,
            }
        )
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"ledger_postings": len(rows)},
    )


def _trial_balance_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    posting_model = _ledger_model("LedgerPosting")
    columns = [
        "row_type",
        "currency",
        "account_code",
        "account_name",
        "account_type",
        "account_owner_type",
        "account_owner_id",
        "total_debit_minor",
        "total_credit_minor",
        "signed_balance_minor",
    ]
    queryset = (
        posting_model.objects.select_related("journal_entry", "account", "currency")
        .filter(
            journal_entry__value_date__lte=end_date,
        )
        .order_by("currency__code", "account__code", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)

    postings = list(queryset)
    grouped: dict[str, dict[str, Any]] = {}
    for posting in postings:
        account = posting.account
        key = str(account.id)
        owner_type = str(account.owner_type or "")
        if key not in grouped:
            grouped[key] = {
                "row_type": "account",
                "currency": posting.currency.code,
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.account_type,
                "account_owner_type": owner_type,
                "account_owner_id": _account_owner_id(account, redaction_mode=redaction_mode),
                "total_debit_minor": 0,
                "total_credit_minor": 0,
                "signed_balance_minor": 0,
            }
        row = grouped[key]
        if str(posting.side) == "debit":
            row["total_debit_minor"] += posting.amount_minor
            row["signed_balance_minor"] += posting.amount_minor
        else:
            row["total_credit_minor"] += posting.amount_minor
            row["signed_balance_minor"] -= posting.amount_minor
    rows = sorted(
        grouped.values(),
        key=lambda row: (str(row["currency"]), str(row["account_code"])),
    )
    totals_by_currency: dict[str, dict[str, Any]] = {}
    for row in rows:
        currency = str(row["currency"])
        if currency not in totals_by_currency:
            totals_by_currency[currency] = {
                "row_type": "currency_total",
                "currency": currency,
                "account_code": "__TOTAL__",
                "account_name": "Trial balance currency total",
                "account_type": "control_total",
                "account_owner_type": "",
                "account_owner_id": "",
                "total_debit_minor": 0,
                "total_credit_minor": 0,
                "signed_balance_minor": 0,
            }
        totals_by_currency[currency]["total_debit_minor"] += int(row["total_debit_minor"])
        totals_by_currency[currency]["total_credit_minor"] += int(row["total_credit_minor"])
        totals_by_currency[currency]["signed_balance_minor"] += int(row["signed_balance_minor"])
    rows.extend(sorted(totals_by_currency.values(), key=lambda row: str(row["currency"])))
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={
            "ledger_accounts": len(grouped),
            "ledger_postings": len(postings),
            "control_total_rows": len(totals_by_currency),
        },
    )


def _garanta_accrued_revenue_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    del redaction_mode
    posting_model = _ledger_model("LedgerPosting")
    columns = [
        "currency",
        "account_type",
        "event_type",
        "total_credit_minor",
        "total_debit_minor",
        "net_revenue_minor",
        "entry_count",
    ]
    queryset = (
        posting_model.objects.select_related("journal_entry", "account", "currency")
        .filter(
            account__account_type__in=REVENUE_ACCOUNT_TYPES,
            journal_entry__value_date__gte=start_date,
            journal_entry__value_date__lte=end_date,
        )
        .order_by("currency__code", "account__account_type", "journal_entry__event_type", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)

    postings = list(queryset)
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for posting in postings:
        key = (
            str(posting.currency.code),
            str(posting.account.account_type),
            str(posting.journal_entry.event_type),
        )
        if key not in grouped:
            grouped[key] = {
                "currency": key[0],
                "account_type": key[1],
                "event_type": key[2],
                "total_credit_minor": 0,
                "total_debit_minor": 0,
                "net_revenue_minor": 0,
                "entry_count": 0,
            }
        row = grouped[key]
        if str(posting.side) == "credit":
            row["total_credit_minor"] += posting.amount_minor
            row["net_revenue_minor"] += posting.amount_minor
        else:
            row["total_debit_minor"] += posting.amount_minor
            row["net_revenue_minor"] -= posting.amount_minor
        row["entry_count"] += 1
    rows = sorted(
        grouped.values(),
        key=lambda row: (row["currency"], row["account_type"], row["event_type"]),
    )
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"ledger_postings": len(postings)},
    )


def _bexio_accounting_export_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    posting_model = _ledger_model("LedgerPosting")
    columns = [
        "row_level",
        "booking_date",
        "value_date",
        "currency",
        "journal_entry_id",
        "posting_id",
        "event_type",
        "source_type",
        "source_id",
        "posting_side",
        "amount_minor",
        "ledger_account_code",
        "ledger_account_type",
        "ledger_owner_type",
        "ledger_owner_id",
        "bexio_account_code",
        "bexio_tax_code",
        "bexio_label",
        "mapping_status",
        "lender_user_id",
        "borrower_id",
        "loan_id",
        "bank_reference",
        "evidence_reference",
        "tax_metadata_json",
        "reversal_of_id",
    ]
    queryset = (
        posting_model.objects.select_related(
            "journal_entry",
            "journal_entry__reversal_of",
            "account",
            "currency",
        )
        .filter(
            journal_entry__value_date__gte=start_date,
            journal_entry__value_date__lte=end_date,
        )
        .order_by(
            "journal_entry__value_date", "journal_entry__created_at", "journal_entry__id", "id"
        )
    )
    queryset = _apply_currency_filter(queryset, filters)
    rows: list[dict[str, Any]] = []
    for posting in list(queryset):
        entry = posting.journal_entry
        account = posting.account
        bexio_mapping = _bexio_mapping_for_account(
            account_type=str(account.account_type),
            event_type=str(entry.event_type),
            filters=filters,
        )
        rows.append(
            {
                "row_level": "transaction_line",
                "booking_date": entry.booking_date,
                "value_date": entry.value_date,
                "currency": posting.currency.code,
                "journal_entry_id": str(entry.id),
                "posting_id": str(posting.id),
                "event_type": entry.event_type,
                "source_type": entry.source_type,
                "source_id": entry.source_id,
                "posting_side": posting.side,
                "amount_minor": posting.amount_minor,
                "ledger_account_code": account.code,
                "ledger_account_type": account.account_type,
                "ledger_owner_type": account.owner_type,
                "ledger_owner_id": _account_owner_id(account, redaction_mode=redaction_mode),
                **bexio_mapping,
                "lender_user_id": _redacted_identifier(
                    entry.lender_user_id,
                    redaction_mode=redaction_mode,
                ),
                "borrower_id": str(entry.borrower_id or ""),
                "loan_id": str(entry.loan_id or ""),
                "bank_reference": _redacted_identifier(
                    entry.bank_reference,
                    redaction_mode=redaction_mode,
                ),
                "evidence_reference": _redacted_identifier(
                    entry.evidence_reference,
                    redaction_mode=redaction_mode,
                ),
                "tax_metadata_json": _redacted_json(
                    entry.tax_metadata,
                    redaction_mode=redaction_mode,
                ),
                "reversal_of_id": str(entry.reversal_of_id or ""),
            }
        )
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"ledger_postings": len(rows)},
        notes=[
            "Bexio account and tax mappings are filter/config driven. Unmapped rows must be "
            "completed with accountant-approved chart and tax-code mapping before production "
            "import."
        ],
    )


def _bank_operations_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    bank_operation_model = _ledger_model("BankOperation")
    columns = [
        "bank_operation_id",
        "operation_type",
        "status",
        "booking_date",
        "value_date",
        "currency",
        "amount_minor",
        "collection_account_identifier",
        "payer_name",
        "payer_account_identifier",
        "payee_name",
        "payee_account_identifier",
        "bank_reference",
        "payment_reference",
        "linked_object_type",
        "linked_object_id",
        "evidence_reference",
        "confirmed_by_admin_id",
        "confirmed_at",
        "notes",
        "metadata_json",
    ]
    queryset = (
        bank_operation_model.objects.select_related("currency")
        .filter(value_date__gte=start_date, value_date__lte=end_date)
        .order_by("value_date", "confirmed_at", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)
    operation_type = str(filters.get("operation_type", ""))
    if operation_type:
        queryset = queryset.filter(operation_type=operation_type)
    rows = [
        {
            "bank_operation_id": str(operation.id),
            "operation_type": operation.operation_type,
            "status": operation.status,
            "booking_date": operation.booking_date,
            "value_date": operation.value_date,
            "currency": operation.currency.code,
            "amount_minor": operation.amount_minor,
            "collection_account_identifier": _redacted_text(
                operation.collection_account_identifier,
                redaction_mode=redaction_mode,
            ),
            "payer_name": _redacted_text(operation.payer_name, redaction_mode=redaction_mode),
            "payer_account_identifier": _redacted_text(
                operation.payer_account_identifier,
                redaction_mode=redaction_mode,
            ),
            "payee_name": _redacted_text(operation.payee_name, redaction_mode=redaction_mode),
            "payee_account_identifier": _redacted_text(
                operation.payee_account_identifier,
                redaction_mode=redaction_mode,
            ),
            "bank_reference": _redacted_text(
                operation.bank_reference, redaction_mode=redaction_mode
            ),
            "payment_reference": _redacted_text(
                operation.payment_reference,
                redaction_mode=redaction_mode,
            ),
            "linked_object_type": operation.linked_object_type,
            "linked_object_id": operation.linked_object_id,
            "evidence_reference": _redacted_text(
                operation.evidence_reference,
                redaction_mode=redaction_mode,
            ),
            "confirmed_by_admin_id": str(operation.confirmed_by_admin_id),
            "confirmed_at": operation.confirmed_at,
            "notes": _redacted_text(operation.notes, redaction_mode=redaction_mode),
            "metadata_json": _redacted_json(operation.metadata, redaction_mode=redaction_mode),
        }
        for operation in list(queryset)
    ]
    return ReportDataset(columns=columns, rows=rows, source_counts={"bank_operations": len(rows)})


def _reconciliation_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    snapshot_model = _ledger_model("ReconciliationSnapshot")
    columns = [
        "snapshot_id",
        "as_of_date",
        "currency",
        "bank_stated_balance_minor",
        "investor_balance_liability_minor",
        "garanta_accrued_revenue_minor",
        "suspense_unmatched_cash_minor",
        "pending_exception_balance_minor",
        "reconciliation_difference_minor",
        "created_by_admin_id",
        "created_at",
        "notes",
        "metadata_json",
    ]
    queryset = (
        snapshot_model.objects.select_related("currency")
        .filter(as_of_date__gte=start_date, as_of_date__lte=end_date)
        .order_by("as_of_date", "currency__code", "created_at", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)
    rows = [
        {
            "snapshot_id": str(snapshot.id),
            "as_of_date": snapshot.as_of_date,
            "currency": snapshot.currency.code,
            "bank_stated_balance_minor": snapshot.bank_stated_balance_minor,
            "investor_balance_liability_minor": snapshot.investor_balance_liability_minor,
            "garanta_accrued_revenue_minor": snapshot.garanta_accrued_revenue_minor,
            "suspense_unmatched_cash_minor": snapshot.suspense_unmatched_cash_minor,
            "pending_exception_balance_minor": snapshot.pending_exception_balance_minor,
            "reconciliation_difference_minor": snapshot.reconciliation_difference_minor,
            "created_by_admin_id": str(snapshot.created_by_admin_id),
            "created_at": snapshot.created_at,
            "notes": _redacted_text(snapshot.notes, redaction_mode=redaction_mode),
            "metadata_json": _redacted_json(snapshot.metadata, redaction_mode=redaction_mode),
        }
        for snapshot in list(queryset)
    ]
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"reconciliation_snapshots": len(rows)},
    )


def _investor_balances_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    lot_model = _ledger_model("InvestorBalanceLot")
    _, end_dt = _date_time_bounds(start_date, end_date)
    columns = [
        "balance_lot_id",
        "investor_user_id",
        "currency",
        "source_type",
        "source_id",
        "status",
        "received_at",
        "investment_deadline_at",
        "withdrawal_deadline_at",
        "age_days_as_of_end_date",
        "original_amount_minor",
        "available_amount_minor",
        "invested_amount_minor",
        "converted_amount_minor",
        "withdrawn_amount_minor",
        "penalized_amount_minor",
        "source_journal_entry_id",
        "lineage_json",
    ]
    queryset = (
        lot_model.objects.select_related("currency", "source_journal_entry")
        .filter(received_at__lte=end_dt)
        .order_by("currency__code", "investor_user_id", "received_at", "created_at", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)
    investor_id = str(filters.get("investor_user_id", "") or filters.get("participant_id", ""))
    if investor_id:
        queryset = queryset.filter(investor_user_id=investor_id)
    rows = [
        {
            "balance_lot_id": str(lot.id),
            "investor_user_id": _redacted_identifier(
                lot.investor_user_id,
                redaction_mode=redaction_mode,
            ),
            "currency": lot.currency.code,
            "source_type": lot.source_type,
            "source_id": lot.source_id,
            "status": lot.status,
            "received_at": lot.received_at,
            "investment_deadline_at": lot.investment_deadline_at,
            "withdrawal_deadline_at": lot.withdrawal_deadline_at,
            "age_days_as_of_end_date": calendar_day_difference(lot.received_at, end_dt),
            "original_amount_minor": lot.original_amount_minor,
            "available_amount_minor": lot.available_amount_minor,
            "invested_amount_minor": lot.invested_amount_minor,
            "converted_amount_minor": lot.converted_amount_minor,
            "withdrawn_amount_minor": lot.withdrawn_amount_minor,
            "penalized_amount_minor": lot.penalized_amount_minor,
            "source_journal_entry_id": str(lot.source_journal_entry_id),
            "lineage_json": _redacted_json(lot.lineage, redaction_mode=redaction_mode),
        }
        for lot in list(queryset)
    ]
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"investor_balance_lots": len(rows)},
    )


def _balance_ageing_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    del start_date
    lot_model = _ledger_model("InvestorBalanceLot")
    _, end_dt = _date_time_bounds(end_date, end_date)
    columns = [
        "balance_lot_id",
        "investor_user_id",
        "currency",
        "status",
        "source_type",
        "available_amount_minor",
        "received_at",
        "age_days",
        "investment_deadline_at",
        "withdrawal_deadline_at",
        "days_until_investment_deadline",
        "days_until_withdrawal_deadline",
        "ageing_bucket",
        "action_required",
    ]
    queryset = (
        lot_model.objects.select_related("currency")
        .filter(available_amount_minor__gt=0, received_at__lte=end_dt)
        .order_by("withdrawal_deadline_at", "investment_deadline_at", "received_at", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)
    rows: list[dict[str, Any]] = []
    for lot in list(queryset):
        age_days = calendar_day_difference(lot.received_at, end_dt)
        investment_days_left = (lot.investment_deadline_at.date() - end_date).days
        withdrawal_days_left = (lot.withdrawal_deadline_at.date() - end_date).days
        if lot.status == "penalty_mode" or withdrawal_days_left < 0:
            bucket = "day_60_plus_penalty_or_withdraw_required"
            action = "withdraw_or_forced_withdrawal"
        elif withdrawal_days_left <= 2:
            bucket = "day_58_to_60"
            action = "urgent_withdrawal_reminder"
        elif withdrawal_days_left <= 7:
            bucket = "day_53_to_57"
            action = "withdrawal_reminder"
        elif investment_days_left < 0:
            bucket = "withdraw_only"
            action = "withdrawal_or_fx_only"
        else:
            bucket = "investable"
            action = "none"
        rows.append(
            {
                "balance_lot_id": str(lot.id),
                "investor_user_id": _redacted_identifier(
                    lot.investor_user_id,
                    redaction_mode=redaction_mode,
                ),
                "currency": lot.currency.code,
                "status": lot.status,
                "source_type": lot.source_type,
                "available_amount_minor": lot.available_amount_minor,
                "received_at": lot.received_at,
                "age_days": age_days,
                "investment_deadline_at": lot.investment_deadline_at,
                "withdrawal_deadline_at": lot.withdrawal_deadline_at,
                "days_until_investment_deadline": investment_days_left,
                "days_until_withdrawal_deadline": withdrawal_days_left,
                "ageing_bucket": bucket,
                "action_required": action,
            }
        )
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"investor_balance_lots": len(rows)},
    )


def _withdrawals_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    withdrawal_model = _ledger_model("InvestorWithdrawalRequest")
    start_dt, end_dt = _date_time_bounds(start_date, end_date)
    columns = [
        "withdrawal_request_id",
        "investor_user_id",
        "status",
        "currency",
        "amount_minor",
        "destination_iban",
        "destination_account_name",
        "is_forced",
        "requested_at",
        "finalized_at",
        "cancelled_at",
        "bank_operation_id",
        "request_journal_entry_id",
        "finalization_journal_entry_id",
        "cancellation_journal_entry_id",
        "bank_reference",
        "payment_reference",
        "evidence_reference",
        "metadata_json",
    ]
    queryset = (
        withdrawal_model.objects.select_related("currency")
        .filter(requested_at__gte=start_dt, requested_at__lte=end_dt)
        .order_by("requested_at", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)
    status_filter = str(filters.get("status", ""))
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    rows = [
        {
            "withdrawal_request_id": str(withdrawal.id),
            "investor_user_id": _redacted_identifier(
                withdrawal.investor_user_id,
                redaction_mode=redaction_mode,
            ),
            "status": withdrawal.status,
            "currency": withdrawal.currency.code,
            "amount_minor": withdrawal.amount_minor,
            "destination_iban": _redacted_text(
                withdrawal.destination_iban,
                redaction_mode=redaction_mode,
            ),
            "destination_account_name": _redacted_text(
                withdrawal.destination_account_name,
                redaction_mode=redaction_mode,
            ),
            "is_forced": withdrawal.is_forced,
            "requested_at": withdrawal.requested_at,
            "finalized_at": withdrawal.finalized_at,
            "cancelled_at": withdrawal.cancelled_at,
            "bank_operation_id": str(withdrawal.bank_operation_id or ""),
            "request_journal_entry_id": str(withdrawal.request_journal_entry_id or ""),
            "finalization_journal_entry_id": str(withdrawal.finalization_journal_entry_id or ""),
            "cancellation_journal_entry_id": str(withdrawal.cancellation_journal_entry_id or ""),
            "bank_reference": _redacted_text(
                withdrawal.bank_reference,
                redaction_mode=redaction_mode,
            ),
            "payment_reference": _redacted_text(
                withdrawal.payment_reference,
                redaction_mode=redaction_mode,
            ),
            "evidence_reference": _redacted_text(
                withdrawal.evidence_reference,
                redaction_mode=redaction_mode,
            ),
            "metadata_json": _redacted_json(withdrawal.metadata, redaction_mode=redaction_mode),
        }
        for withdrawal in list(queryset)
    ]
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"investor_withdrawal_requests": len(rows)},
    )


def _loan_funding_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    del redaction_mode
    loan_model = _external_model("loans", "Loan")
    order_model = _external_model("marketplace_primary", "PrimaryInvestmentOrder")
    close_model = _external_model("marketplace_primary", "PrimaryLoanClose")
    columns = [
        "loan_id",
        "borrower_id",
        "title",
        "status",
        "currency",
        "principal_minor",
        "committed_principal_minor",
        "funding_deadline",
        "published_at",
        "order_count",
        "pending_order_count",
        "allocated_order_count",
        "allocated_amount_minor",
        "closed_at",
        "close_type",
        "accepted_principal_minor",
        "borrower_success_fee_minor",
        "borrower_disbursement_payable_minor",
    ]
    queryset = (
        loan_model.objects.select_related("currency")
        .filter(funding_deadline__gte=start_date, funding_deadline__lte=end_date)
        .order_by("funding_deadline", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)
    rows: list[dict[str, Any]] = []
    for loan in list(queryset):
        orders = list(order_model.objects.filter(loan_id=loan.id))
        close = close_model.objects.filter(loan_id=loan.id).order_by("-closed_at").first()
        allocated_amount = sum(int(order.allocated_amount_minor) for order in orders)
        rows.append(
            {
                "loan_id": str(loan.id),
                "borrower_id": str(loan.borrower_id),
                "title": loan.title,
                "status": loan.status,
                "currency": loan.currency.code,
                "principal_minor": loan.principal_minor,
                "committed_principal_minor": loan.committed_principal_minor,
                "funding_deadline": loan.funding_deadline,
                "published_at": loan.published_at,
                "order_count": len(orders),
                "pending_order_count": sum(1 for order in orders if order.status == "pending"),
                "allocated_order_count": sum(
                    1
                    for order in orders
                    if order.status
                    in {"balance_allocated", "partially_allocated", "closed_invested"}
                ),
                "allocated_amount_minor": allocated_amount,
                "closed_at": getattr(close, "closed_at", None),
                "close_type": getattr(close, "close_type", ""),
                "accepted_principal_minor": getattr(close, "accepted_principal_minor", 0) or 0,
                "borrower_success_fee_minor": getattr(close, "borrower_success_fee_minor", 0) or 0,
                "borrower_disbursement_payable_minor": getattr(
                    close,
                    "borrower_disbursement_payable_minor",
                    0,
                )
                or 0,
            }
        )
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"loans": len(rows)},
    )


def _repayment_status_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    del redaction_mode
    installment_model = _external_model("loans", "LoanInstallment")
    repayment_model = _external_model("servicing", "BorrowerRepaymentEvent")
    columns = [
        "loan_id",
        "borrower_id",
        "loan_status",
        "currency",
        "schedule_version",
        "installment_id",
        "installment_number",
        "due_date",
        "scheduled_principal_minor",
        "scheduled_interest_minor",
        "scheduled_total_minor",
        "paid_principal_minor",
        "paid_interest_minor",
        "paid_future_principal_minor",
        "paid_total_minor",
        "outstanding_minor",
        "days_past_due_as_of_end_date",
        "repayment_status_bucket",
    ]
    queryset = (
        installment_model.objects.select_related("loan", "loan__currency")
        .filter(due_date__gte=start_date, due_date__lte=end_date)
        .order_by("due_date", "loan_id", "installment_number", "id")
    )
    queryset = _apply_currency_filter(queryset, filters, field_name="loan__currency")
    rows: list[dict[str, Any]] = []
    for installment in list(queryset):
        repayments = list(repayment_model.objects.filter(installment_id=installment.id))
        paid_principal = sum(int(event.principal_applied_minor) for event in repayments)
        paid_interest = sum(int(event.interest_applied_minor) for event in repayments)
        paid_future_principal = sum(
            int(event.future_principal_applied_minor) for event in repayments
        )
        paid_total = sum(int(event.amount_minor) for event in repayments)
        outstanding = max(0, int(installment.total_minor) - paid_principal - paid_interest)
        days_past_due = max(0, (end_date - installment.due_date).days) if outstanding else 0
        if outstanding == 0:
            bucket = "paid"
        elif days_past_due >= 16:
            bucket = "default_threshold"
        elif days_past_due >= 5:
            bucket = "late_threshold"
        elif installment.due_date < end_date:
            bucket = "past_due_under_late_threshold"
        else:
            bucket = "due_or_upcoming"
        rows.append(
            {
                "loan_id": str(installment.loan_id),
                "borrower_id": str(installment.loan.borrower_id),
                "loan_status": installment.loan.status,
                "currency": installment.loan.currency.code,
                "schedule_version": installment.schedule_version,
                "installment_id": str(installment.id),
                "installment_number": installment.installment_number,
                "due_date": installment.due_date,
                "scheduled_principal_minor": installment.principal_minor,
                "scheduled_interest_minor": installment.interest_minor,
                "scheduled_total_minor": installment.total_minor,
                "paid_principal_minor": paid_principal,
                "paid_interest_minor": paid_interest,
                "paid_future_principal_minor": paid_future_principal,
                "paid_total_minor": paid_total,
                "outstanding_minor": outstanding,
                "days_past_due_as_of_end_date": days_past_due,
                "repayment_status_bucket": bucket,
            }
        )
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"loan_installments": len(rows)},
    )


def _default_exposure_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    del start_date, end_date
    holding_model = _external_model("holdings", "InvestorLoanHolding")
    columns = [
        "holding_id",
        "investor_user_id",
        "loan_id",
        "borrower_id",
        "loan_status",
        "currency",
        "current_principal_minor",
        "original_principal_minor",
        "loan_share_ppm",
        "assignment_effective_at",
        "holding_status",
        "risk_rating",
        "collateral_type",
    ]
    statuses = filters.get("loan_statuses") or list(DEFAULT_EXPOSURE_LOAN_STATUSES)
    if not isinstance(statuses, list):
        statuses = list(DEFAULT_EXPOSURE_LOAN_STATUSES)
    queryset = (
        holding_model.objects.select_related("loan", "loan__currency")
        .filter(loan__status__in=statuses, current_principal_minor__gt=0)
        .order_by("loan__status", "loan_id", "investor_user_id", "id")
    )
    queryset = _apply_currency_filter(queryset, filters, field_name="currency")
    rows = [
        {
            "holding_id": str(holding.id),
            "investor_user_id": _redacted_identifier(
                holding.investor_user_id,
                redaction_mode=redaction_mode,
            ),
            "loan_id": str(holding.loan_id),
            "borrower_id": str(holding.loan.borrower_id),
            "loan_status": holding.loan.status,
            "currency": holding.currency.code,
            "current_principal_minor": holding.current_principal_minor,
            "original_principal_minor": holding.original_principal_minor,
            "loan_share_ppm": holding.loan_share_ppm,
            "assignment_effective_at": holding.assignment_effective_at,
            "holding_status": holding.status,
            "risk_rating": holding.loan.risk_rating,
            "collateral_type": holding.loan.collateral_type,
        }
        for holding in list(queryset)
    ]
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"investor_loan_holdings": len(rows)},
    )


def _recovery_write_off_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    del redaction_mode
    recovery_model = _external_model("servicing", "LoanRecoveryEvent")
    writeoff_model = _external_model("servicing", "LoanWriteOffEvent")
    columns = [
        "row_type",
        "event_id",
        "loan_id",
        "borrower_id",
        "currency",
        "value_date",
        "gross_recovered_minor",
        "externally_deducted_costs_minor",
        "net_received_minor",
        "third_party_costs_minor",
        "recovery_fee_minor",
        "net_available_for_distribution_minor",
        "principal_minor",
        "contractual_interest_minor",
        "default_interest_minor",
        "fees_minor",
        "penalties_minor",
        "other_costs_minor",
        "rounding_difference_minor",
        "total_written_off_minor",
        "evidence_reference",
        "notes",
    ]
    rows: list[dict[str, Any]] = []
    recovery_queryset = (
        recovery_model.objects.select_related("currency")
        .filter(value_date__gte=start_date, value_date__lte=end_date)
        .order_by("value_date", "created_at", "id")
    )
    recovery_queryset = _apply_currency_filter(recovery_queryset, filters)
    for event in list(recovery_queryset):
        rows.append(
            {
                "row_type": "recovery",
                "event_id": str(event.id),
                "loan_id": str(event.loan_id),
                "borrower_id": str(event.borrower_id),
                "currency": event.currency.code,
                "value_date": event.value_date,
                "gross_recovered_minor": event.gross_recovered_minor,
                "externally_deducted_costs_minor": event.externally_deducted_costs_minor,
                "net_received_minor": event.net_received_minor,
                "third_party_costs_minor": event.third_party_costs_from_received_minor,
                "recovery_fee_minor": event.recovery_fee_minor,
                "net_available_for_distribution_minor": event.net_available_for_distribution_minor,
                "principal_minor": event.principal_recovered_minor,
                "contractual_interest_minor": event.contractual_interest_recovered_minor,
                "default_interest_minor": event.default_interest_recovered_minor,
                "fees_minor": 0,
                "penalties_minor": event.penalties_recovered_minor,
                "other_costs_minor": event.other_costs_recovered_minor,
                "rounding_difference_minor": event.rounding_difference_minor,
                "total_written_off_minor": 0,
                "evidence_reference": event.evidence_reference,
                "notes": event.notes,
            }
        )
    start_dt, end_dt = _date_time_bounds(start_date, end_date)
    writeoff_queryset = (
        writeoff_model.objects.select_related("currency")
        .filter(written_off_at__gte=start_dt, written_off_at__lte=end_dt)
        .order_by("written_off_at", "id")
    )
    writeoff_queryset = _apply_currency_filter(writeoff_queryset, filters)
    for event in list(writeoff_queryset):
        rows.append(
            {
                "row_type": "write_off",
                "event_id": str(event.id),
                "loan_id": str(event.loan_id),
                "borrower_id": str(event.borrower_id),
                "currency": event.currency.code,
                "value_date": event.written_off_at.date(),
                "gross_recovered_minor": 0,
                "externally_deducted_costs_minor": 0,
                "net_received_minor": 0,
                "third_party_costs_minor": 0,
                "recovery_fee_minor": 0,
                "net_available_for_distribution_minor": 0,
                "principal_minor": event.written_off_principal_minor,
                "contractual_interest_minor": event.written_off_contractual_interest_minor,
                "default_interest_minor": event.written_off_default_interest_minor,
                "fees_minor": event.written_off_fees_minor,
                "penalties_minor": event.written_off_penalties_minor,
                "other_costs_minor": 0,
                "rounding_difference_minor": 0,
                "total_written_off_minor": event.total_written_off_minor,
                "evidence_reference": event.evidence_reference,
                "notes": event.notes,
            }
        )
    rows.sort(key=lambda row: (str(row["value_date"]), str(row["row_type"]), str(row["event_id"])))
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={
            "loan_recovery_events": recovery_queryset.count(),
            "loan_write_off_events": writeoff_queryset.count(),
        },
    )


def _fx_activity_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    fx_exchange_model = _external_model("fx", "FxExchange")
    fx_settlement_model = _external_model("fx", "FxExternalSettlement")
    start_dt, end_dt = _date_time_bounds(start_date, end_date)
    columns = [
        "row_type",
        "event_id",
        "investor_user_id",
        "source_currency",
        "target_currency",
        "source_amount_minor",
        "gross_target_amount_minor",
        "target_amount_minor",
        "fee_minor",
        "rate",
        "executed_or_declared_at",
        "value_date",
        "expected_sold_amount_minor",
        "expected_bought_amount_minor",
        "sold_amount_minor",
        "bought_amount_minor",
        "sold_currency_residual_minor",
        "bought_currency_residual_minor",
        "bank_reference",
        "evidence_reference",
    ]
    rows: list[dict[str, Any]] = []
    exchange_queryset = (
        fx_exchange_model.objects.select_related("source_currency", "target_currency")
        .filter(executed_at__gte=start_dt, executed_at__lte=end_dt)
        .order_by("executed_at", "id")
    )
    pair = str(filters.get("pair", ""))
    if pair and "/" in pair:
        source, target = [part.strip().upper() for part in pair.split("/", 1)]
        exchange_queryset = exchange_queryset.filter(
            source_currency__code=source,
            target_currency__code=target,
        )
    for exchange in list(exchange_queryset):
        rows.append(
            {
                "row_type": "internal_exchange",
                "event_id": str(exchange.id),
                "investor_user_id": _redacted_identifier(
                    exchange.investor_user_id,
                    redaction_mode=redaction_mode,
                ),
                "source_currency": exchange.source_currency.code,
                "target_currency": exchange.target_currency.code,
                "source_amount_minor": exchange.source_amount_minor,
                "gross_target_amount_minor": exchange.gross_target_amount_minor,
                "target_amount_minor": exchange.target_amount_minor,
                "fee_minor": exchange.fee_minor,
                "rate": exchange.rate,
                "executed_or_declared_at": exchange.executed_at,
                "value_date": exchange.executed_at.date(),
                "expected_sold_amount_minor": 0,
                "expected_bought_amount_minor": 0,
                "sold_amount_minor": 0,
                "bought_amount_minor": 0,
                "sold_currency_residual_minor": 0,
                "bought_currency_residual_minor": 0,
                "bank_reference": "",
                "evidence_reference": "",
            }
        )
    settlement_queryset = (
        fx_settlement_model.objects.select_related("sold_currency", "bought_currency")
        .filter(value_date__gte=start_date, value_date__lte=end_date)
        .order_by("value_date", "declared_at", "id")
    )
    if pair and "/" in pair:
        source, target = [part.strip().upper() for part in pair.split("/", 1)]
        settlement_queryset = settlement_queryset.filter(
            sold_currency__code=source,
            bought_currency__code=target,
        )
    for settlement in list(settlement_queryset):
        rows.append(
            {
                "row_type": "external_settlement",
                "event_id": str(settlement.id),
                "investor_user_id": "",
                "source_currency": settlement.sold_currency.code,
                "target_currency": settlement.bought_currency.code,
                "source_amount_minor": 0,
                "gross_target_amount_minor": 0,
                "target_amount_minor": 0,
                "fee_minor": settlement.expected_fee_minor,
                "rate": settlement.actual_rate,
                "executed_or_declared_at": settlement.declared_at,
                "value_date": settlement.value_date,
                "expected_sold_amount_minor": settlement.expected_sold_amount_minor,
                "expected_bought_amount_minor": settlement.expected_bought_amount_minor,
                "sold_amount_minor": settlement.sold_amount_minor,
                "bought_amount_minor": settlement.bought_amount_minor,
                "sold_currency_residual_minor": settlement.sold_currency_residual_minor,
                "bought_currency_residual_minor": settlement.bought_currency_residual_minor,
                "bank_reference": _redacted_text(
                    settlement.bank_reference,
                    redaction_mode=redaction_mode,
                ),
                "evidence_reference": _redacted_text(
                    settlement.evidence_reference,
                    redaction_mode=redaction_mode,
                ),
            }
        )
    rows.sort(key=lambda row: (str(row["value_date"]), str(row["row_type"]), str(row["event_id"])))
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={
            "fx_exchanges": exchange_queryset.count(),
            "fx_external_settlements": settlement_queryset.count(),
        },
    )


def _kyc_status_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    case_model = _external_model("kyc_compliance", "KycVerificationCase")
    start_dt, end_dt = _date_time_bounds(start_date, end_date)
    columns = [
        "case_id",
        "subject_type",
        "user_id",
        "subject_reference",
        "provider",
        "provider_environment",
        "status",
        "risk_classification",
        "detected_flags_json",
        "provider_session_id",
        "provider_verification_id",
        "provider_report_id",
        "aml_screening_id",
        "provider_subject_id",
        "decision_at",
        "manual_review_required",
        "blocking_reason",
        "created_at",
        "updated_at",
    ]
    queryset = case_model.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt).order_by(
        "created_at", "id"
    )
    subject_type = str(filters.get("subject_type", ""))
    if subject_type:
        queryset = queryset.filter(subject_type=subject_type)
    status_filter = str(filters.get("status", ""))
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    rows = [
        {
            "case_id": str(case.id),
            "subject_type": case.subject_type,
            "user_id": _redacted_identifier(case.user_id, redaction_mode=redaction_mode),
            "subject_reference": _redacted_identifier(
                case.subject_reference,
                redaction_mode=redaction_mode,
            ),
            "provider": case.provider,
            "provider_environment": case.provider_environment,
            "status": case.status,
            "risk_classification": case.risk_classification,
            "detected_flags_json": _redacted_json(
                case.detected_flags,
                redaction_mode=redaction_mode,
            ),
            "provider_session_id": _redacted_identifier(
                case.provider_session_id,
                redaction_mode=redaction_mode,
            ),
            "provider_verification_id": _redacted_identifier(
                case.provider_verification_id,
                redaction_mode=redaction_mode,
            ),
            "provider_report_id": _redacted_identifier(
                case.provider_report_id,
                redaction_mode=redaction_mode,
            ),
            "aml_screening_id": _redacted_identifier(
                case.aml_screening_id,
                redaction_mode=redaction_mode,
            ),
            "provider_subject_id": _redacted_identifier(
                case.provider_subject_id,
                redaction_mode=redaction_mode,
            ),
            "decision_at": case.decision_at,
            "manual_review_required": case.manual_review_required,
            "blocking_reason": _redacted_text(case.blocking_reason, redaction_mode=redaction_mode),
            "created_at": case.created_at,
            "updated_at": case.updated_at,
        }
        for case in list(queryset)
    ]
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"kyc_verification_cases": len(rows)},
        notes=[
            "Formal provider-native KYC/AML reports remain generated by Didit; this export covers "
            "locally retained platform evidence and status fields."
        ],
    )


def _audit_log_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    start_dt, end_dt = _date_time_bounds(start_date, end_date)
    columns = [
        "audit_event_id",
        "occurred_at",
        "actor_type",
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "request_id",
        "metadata_json",
    ]
    queryset = AuditEvent.objects.filter(
        occurred_at__gte=start_dt, occurred_at__lte=end_dt
    ).order_by(
        "occurred_at",
        "id",
    )
    action = str(filters.get("action", ""))
    if action:
        queryset = queryset.filter(action=action)
    rows = [
        {
            "audit_event_id": str(event.id),
            "occurred_at": event.occurred_at,
            "actor_type": event.actor_type,
            "actor_id": _redacted_identifier(event.actor_id, redaction_mode=redaction_mode),
            "action": event.action,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "request_id": event.request_id,
            "metadata_json": _redacted_json(event.metadata, redaction_mode=redaction_mode),
        }
        for event in list(queryset)
    ]
    return ReportDataset(columns=columns, rows=rows, source_counts={"audit_events": len(rows)})


def _failed_outbox_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    outbox_model = _external_model("platform_core", "OutboxMessage")
    start_dt, end_dt = _date_time_bounds(start_date, end_date)
    columns = [
        "outbox_message_id",
        "idempotency_key",
        "topic",
        "status",
        "attempts",
        "next_attempt_at",
        "processed_at",
        "last_error",
        "payload_json",
        "created_at",
        "updated_at",
    ]
    statuses = filters.get("statuses") or ["dead_letter"]
    if not isinstance(statuses, list):
        statuses = ["dead_letter"]
    queryset = (
        outbox_model.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt,
            status__in=statuses,
        )
        .order_by("created_at", "id")
    )
    topic = str(filters.get("topic", ""))
    if topic:
        queryset = queryset.filter(topic=topic)
    rows = [
        {
            "outbox_message_id": str(message.id),
            "idempotency_key": message.idempotency_key,
            "topic": message.topic,
            "status": message.status,
            "attempts": message.attempts,
            "next_attempt_at": message.next_attempt_at,
            "processed_at": message.processed_at,
            "last_error": _redacted_text(message.last_error, redaction_mode=redaction_mode),
            "payload_json": _redacted_json(message.payload, redaction_mode=redaction_mode),
            "created_at": message.created_at,
            "updated_at": message.updated_at,
        }
        for message in list(queryset)
    ]
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"outbox_messages": len(rows)},
        notes=[
            "This report is the failed-delivery foundation for email/provider/background jobs. "
            "Topic-specific email delivery reports will become richer once the communications "
            "module stores provider delivery metadata."
        ],
    )


def _participant_account_statement_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    participant_type = str(filters.get("participant_type", "lender")).lower()
    participant_id = str(filters.get("participant_id", "") or "")
    posting_model = _ledger_model("LedgerPosting")
    columns = [
        "participant_type",
        "participant_id",
        "statement_section",
        "booking_date",
        "value_date",
        "currency",
        "journal_entry_id",
        "posting_id",
        "event_type",
        "source_type",
        "source_id",
        "account_type",
        "posting_side",
        "amount_minor",
        "signed_amount_minor",
        "tax_treatment_hint",
        "loan_id",
        "borrower_id",
        "bank_reference",
        "evidence_reference",
    ]
    queryset = (
        posting_model.objects.select_related("journal_entry", "account", "currency")
        .filter(
            journal_entry__value_date__gte=start_date,
            journal_entry__value_date__lte=end_date,
        )
        .order_by("journal_entry__value_date", "journal_entry__created_at", "id")
    )
    queryset = _apply_currency_filter(queryset, filters)
    if participant_type == "lender":
        if participant_id:
            queryset = queryset.filter(journal_entry__lender_user_id=participant_id)
        else:
            queryset = queryset.filter(journal_entry__lender_user_id__isnull=False)
    elif participant_type == "borrower":
        if participant_id:
            queryset = queryset.filter(journal_entry__borrower_id=participant_id)
        else:
            queryset = queryset.filter(journal_entry__borrower_id__isnull=False)
    elif participant_type == "garanta":
        queryset = queryset.filter(account__account_type__in=REVENUE_ACCOUNT_TYPES)
    else:
        raise ReportingValidationError(
            "participant_account_statement participant_type must be lender, borrower, or garanta."
        )

    rows: list[dict[str, Any]] = []
    for posting in list(queryset):
        entry = posting.journal_entry
        account_type = str(posting.account.account_type)
        event_type = str(entry.event_type)
        if account_type in REVENUE_ACCOUNT_TYPES:
            section = "garanta_revenue"
            tax_hint = "income_or_cost_subject_to_accountant_mapping"
        elif any(
            marker in event_type
            for marker in (
                "deposit",
                "withdrawal",
                "principal",
                "funding",
                "disbursement",
                "escrow",
                "settlement",
            )
        ):
            section = "principal_or_settlement_movement"
            tax_hint = "information_only_principal_or_client_money"
        elif "repayment" in event_type:
            section = "repayment_or_distribution"
            tax_hint = "split_interest_principal_from_source_lines_where_applicable"
        else:
            section = "ledger_activity"
            tax_hint = "review_source_tax_metadata"
        participant = participant_id
        if participant_type == "lender":
            participant = str(entry.lender_user_id or participant_id)
        elif participant_type == "borrower":
            participant = str(entry.borrower_id or participant_id)
        rows.append(
            {
                "participant_type": participant_type,
                "participant_id": _redacted_identifier(
                    participant,
                    redaction_mode=redaction_mode,
                )
                if participant_type == "lender"
                else participant,
                "statement_section": section,
                "booking_date": entry.booking_date,
                "value_date": entry.value_date,
                "currency": posting.currency.code,
                "journal_entry_id": str(entry.id),
                "posting_id": str(posting.id),
                "event_type": entry.event_type,
                "source_type": entry.source_type,
                "source_id": entry.source_id,
                "account_type": account_type,
                "posting_side": posting.side,
                "amount_minor": posting.amount_minor,
                "signed_amount_minor": _ledger_sign(str(posting.side), int(posting.amount_minor)),
                "tax_treatment_hint": tax_hint,
                "loan_id": str(entry.loan_id or ""),
                "borrower_id": str(entry.borrower_id or ""),
                "bank_reference": _redacted_identifier(
                    entry.bank_reference,
                    redaction_mode=redaction_mode,
                ),
                "evidence_reference": _redacted_identifier(
                    entry.evidence_reference,
                    redaction_mode=redaction_mode,
                ),
            }
        )
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"ledger_postings": len(rows)},
    )


def _annual_tax_information_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    participant_type = str(filters.get("participant_type", "lender")).lower()
    participant_id = str(filters.get("participant_id", "") or "")
    columns = [
        "participant_type",
        "participant_id",
        "currency",
        "section",
        "category",
        "amount_minor",
        "source_count",
        "tax_relevant",
        "income_or_cost",
        "notes",
    ]
    rows: list[dict[str, Any]] = []

    def add_row(
        *,
        currency: str,
        section: str,
        category: str,
        amount_minor: int,
        source_count: int,
        tax_relevant: bool,
        income_or_cost: str,
        notes: str = "",
    ) -> None:
        rows.append(
            {
                "participant_type": participant_type,
                "participant_id": _redacted_identifier(
                    participant_id or "all",
                    redaction_mode=redaction_mode,
                )
                if participant_type == "lender"
                else participant_id or "all",
                "currency": currency,
                "section": section,
                "category": category,
                "amount_minor": amount_minor,
                "source_count": source_count,
                "tax_relevant": tax_relevant,
                "income_or_cost": income_or_cost,
                "notes": notes,
            }
        )

    if participant_type == "lender":
        repayment_line_model = _external_model("servicing", "InvestorRepaymentDistributionLine")
        recovery_line_model = _external_model("servicing", "InvestorRecoveryDistributionLine")
        fx_exchange_model = _external_model("fx", "FxExchange")
        purchase_model = _external_model("secondary_market", "SecondaryMarketPurchase")
        holding_model = _external_model("holdings", "InvestorLoanHolding")
        start_dt, end_dt = _date_time_bounds(start_date, end_date)

        repayment_queryset = repayment_line_model.objects.select_related("currency").filter(
            occurred_at__gte=start_dt,
            occurred_at__lte=end_dt,
        )
        recovery_queryset = recovery_line_model.objects.select_related("currency").filter(
            occurred_at__gte=start_dt,
            occurred_at__lte=end_dt,
        )
        fx_queryset = fx_exchange_model.objects.select_related(
            "source_currency", "target_currency"
        ).filter(
            executed_at__gte=start_dt,
            executed_at__lte=end_dt,
        )
        purchase_queryset = purchase_model.objects.select_related("currency").filter(
            purchased_at__gte=start_dt,
            purchased_at__lte=end_dt,
        )
        holding_queryset = holding_model.objects.select_related("currency").all()
        if participant_id:
            repayment_queryset = repayment_queryset.filter(investor_user_id=participant_id)
            recovery_queryset = recovery_queryset.filter(investor_user_id=participant_id)
            fx_queryset = fx_queryset.filter(investor_user_id=participant_id)
            purchase_queryset = purchase_queryset.filter(
                buyer_user_id=participant_id
            ) | purchase_queryset.model.objects.select_related("currency").filter(
                seller_user_id=participant_id,
                purchased_at__gte=start_dt,
                purchased_at__lte=end_dt,
            )
            holding_queryset = holding_queryset.filter(investor_user_id=participant_id)

        grouped: dict[tuple[str, str, str], dict[str, int]] = {}

        def bump(currency: str, section: str, category: str, amount: int) -> None:
            key = (currency, section, category)
            grouped.setdefault(key, {"amount": 0, "count": 0})
            grouped[key]["amount"] += int(amount)
            grouped[key]["count"] += 1

        for line in list(repayment_queryset):
            bump(
                line.currency.code,
                "tax_summary",
                "interest_received_or_credited",
                line.interest_minor,
            )
            bump(line.currency.code, "information_only", "principal_repaid", line.principal_minor)
            if line.fee_minor:
                bump(line.currency.code, "tax_summary", "lender_payment_fees_paid", line.fee_minor)
        for line in list(recovery_queryset):
            bump(
                line.currency.code, "information_only", "principal_recovered", line.principal_minor
            )
            bump(
                line.currency.code,
                "tax_summary",
                "contractual_interest_recovered",
                line.contractual_interest_minor,
            )
            bump(
                line.currency.code,
                "tax_summary",
                "default_interest_recovered",
                line.default_interest_minor,
            )
            bump(line.currency.code, "tax_summary", "penalties_recovered", line.penalties_minor)
            bump(line.currency.code, "tax_summary", "other_recovery_costs", line.other_costs_minor)
        for exchange in list(fx_queryset):
            bump(exchange.target_currency.code, "tax_summary", "fx_fees_paid", exchange.fee_minor)
            bump(
                exchange.source_currency.code,
                "information_only",
                "fx_source_converted",
                exchange.source_amount_minor,
            )
            bump(
                exchange.target_currency.code,
                "information_only",
                "fx_target_credited",
                exchange.target_amount_minor,
            )
        for purchase in list(purchase_queryset):
            if str(purchase.buyer_user_id) == participant_id or not participant_id:
                bump(
                    purchase.currency.code,
                    "tax_summary",
                    "secondary_market_taker_fees_paid",
                    purchase.taker_fee_minor,
                )
                bump(
                    purchase.currency.code,
                    "information_only",
                    "secondary_market_purchase_price",
                    purchase.transfer_price_minor,
                )
            if str(purchase.seller_user_id) == participant_id or not participant_id:
                bump(
                    purchase.currency.code,
                    "tax_summary",
                    "secondary_market_maker_fees_paid",
                    purchase.maker_fee_minor,
                )
                bump(
                    purchase.currency.code,
                    "information_only",
                    "secondary_market_seller_net_proceeds",
                    purchase.seller_net_proceeds_minor,
                )
        outstanding_by_currency: dict[str, int] = {}
        for holding in list(holding_queryset):
            outstanding_by_currency[holding.currency.code] = outstanding_by_currency.get(
                holding.currency.code,
                0,
            ) + int(holding.current_principal_minor)
        for currency, amount in outstanding_by_currency.items():
            add_row(
                currency=currency,
                section="information_only",
                category="current_outstanding_principal",
                amount_minor=amount,
                source_count=1,
                tax_relevant=False,
                income_or_cost="information_only",
            )
        for (currency, section, category), value in sorted(grouped.items()):
            add_row(
                currency=currency,
                section=section,
                category=category,
                amount_minor=value["amount"],
                source_count=value["count"],
                tax_relevant=section == "tax_summary",
                income_or_cost="income_or_cost" if section == "tax_summary" else "information_only",
            )
    elif participant_type == "borrower":
        repayment_model = _external_model("servicing", "BorrowerRepaymentEvent")
        close_model = _external_model("marketplace_primary", "PrimaryLoanClose")
        repayment_queryset = repayment_model.objects.select_related("currency").filter(
            value_date__gte=start_date,
            value_date__lte=end_date,
        )
        close_queryset = close_model.objects.select_related("currency", "loan").filter(
            closed_at__gte=_date_time_bounds(start_date, end_date)[0],
            closed_at__lte=_date_time_bounds(start_date, end_date)[1],
        )
        if participant_id:
            repayment_queryset = repayment_queryset.filter(loan__borrower_id=participant_id)
            close_queryset = close_queryset.filter(loan__borrower_id=participant_id)
        by_key: dict[tuple[str, str, str], dict[str, int]] = {}

        def bump(currency: str, section: str, category: str, amount: int) -> None:
            key = (currency, section, category)
            by_key.setdefault(key, {"amount": 0, "count": 0})
            by_key[key]["amount"] += int(amount)
            by_key[key]["count"] += 1

        for event in list(repayment_queryset):
            bump(event.currency.code, "tax_summary", "interest_paid", event.interest_applied_minor)
            bump(
                event.currency.code,
                "information_only",
                "principal_repaid",
                event.principal_applied_minor + event.future_principal_applied_minor,
            )
            bump(event.currency.code, "tax_summary", "fees_paid", event.fees_applied_minor)
            bump(
                event.currency.code, "tax_summary", "penalties_paid", event.penalties_applied_minor
            )
        for close in list(close_queryset):
            bump(
                close.currency.code,
                "tax_summary",
                "borrower_success_fee",
                close.borrower_success_fee_minor,
            )
            bump(
                close.currency.code,
                "information_only",
                "principal_received",
                close.accepted_principal_minor,
            )
            bump(
                close.currency.code,
                "information_only",
                "net_disbursement_payable",
                close.borrower_disbursement_payable_minor,
            )
        for (currency, section, category), value in sorted(by_key.items()):
            add_row(
                currency=currency,
                section=section,
                category=category,
                amount_minor=value["amount"],
                source_count=value["count"],
                tax_relevant=section == "tax_summary",
                income_or_cost="cost_or_information"
                if section == "tax_summary"
                else "information_only",
            )
    elif participant_type == "garanta":
        revenue_dataset = _garanta_accrued_revenue_dataset(
            start_date=start_date,
            end_date=end_date,
            redaction_mode=redaction_mode,
            filters=filters,
        )
        for row in revenue_dataset.rows:
            add_row(
                currency=str(row["currency"]),
                section="tax_summary",
                category=f"platform_revenue:{row['account_type']}:{row['event_type']}",
                amount_minor=int(row["net_revenue_minor"]),
                source_count=int(row["entry_count"]),
                tax_relevant=True,
                income_or_cost="garanta_revenue_or_cost",
                notes=(
                    "Client-money flows are excluded; this row is derived from Garanta revenue "
                    "accounts."
                ),
            )
    else:
        raise ReportingValidationError(
            "annual_tax_information participant_type must be lender, borrower, or garanta."
        )

    rows.append(
        {
            "participant_type": participant_type,
            "participant_id": _redacted_identifier(
                participant_id or "all",
                redaction_mode=redaction_mode,
            )
            if participant_type == "lender"
            else participant_id or "all",
            "currency": "",
            "section": "disclaimer",
            "category": "informational_only_not_tax_advice",
            "amount_minor": 0,
            "source_count": 0,
            "tax_relevant": False,
            "income_or_cost": "disclaimer",
            "notes": ANNUAL_TAX_INFORMATION_DISCLAIMER,
        }
    )
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"tax_information_rows": len(rows)},
        notes=[ANNUAL_TAX_INFORMATION_DISCLAIMER],
    )


def _build_dataset(
    *,
    report_type: str,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    builders = {
        ReportType.OPERATIONAL_SUBLEDGER: _operational_subledger_dataset,
        ReportType.TRIAL_BALANCE: _trial_balance_dataset,
        ReportType.GARANTA_ACCRUED_REVENUE: _garanta_accrued_revenue_dataset,
        ReportType.BEXIO_ACCOUNTING_EXPORT: _bexio_accounting_export_dataset,
        ReportType.BANK_OPERATIONS: _bank_operations_dataset,
        ReportType.RECONCILIATION: _reconciliation_dataset,
        ReportType.INVESTOR_BALANCES: _investor_balances_dataset,
        ReportType.BALANCE_AGEING: _balance_ageing_dataset,
        ReportType.WITHDRAWALS: _withdrawals_dataset,
        ReportType.LOAN_FUNDING: _loan_funding_dataset,
        ReportType.REPAYMENT_STATUS: _repayment_status_dataset,
        ReportType.DEFAULT_EXPOSURE: _default_exposure_dataset,
        ReportType.RECOVERY_WRITE_OFF: _recovery_write_off_dataset,
        ReportType.FX_ACTIVITY: _fx_activity_dataset,
        ReportType.KYC_STATUS: _kyc_status_dataset,
        ReportType.AUDIT_LOG: _audit_log_dataset,
        ReportType.FAILED_OUTBOX: _failed_outbox_dataset,
        ReportType.PARTICIPANT_ACCOUNT_STATEMENT: _participant_account_statement_dataset,
        ReportType.ANNUAL_TAX_INFORMATION: _annual_tax_information_dataset,
    }
    try:
        builder = builders[ReportType(report_type)]
    except (KeyError, ValueError) as exc:
        raise ReportingValidationError(f"Unsupported report type: {report_type}") from exc
    return builder(
        start_date=start_date,
        end_date=end_date,
        redaction_mode=redaction_mode,
        filters=filters,
    )


def _report_semantics(report_type: str) -> str:
    if report_type == ReportType.TRIAL_BALANCE:
        return "as_of_end_date_cumulative_balances_with_currency_control_totals"
    if report_type in {ReportType.INVESTOR_BALANCES, ReportType.BALANCE_AGEING}:
        return "as_of_end_date_with_lot_level_lineage"
    if report_type in {ReportType.ANNUAL_TAX_INFORMATION}:
        return "calendar_year_or_selected_period_information_only_tax_summary"
    return "inclusive_value_date_or_event_date_range"


def _pdf_escape(text: str) -> str:
    ascii_text = text.encode("latin-1", errors="replace").decode("latin-1")
    return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _dataset_pdf_lines(*, manifest: dict[str, Any], dataset: ReportDataset) -> list[str]:
    title = f"{manifest['report_type']} report"
    lines = [
        title,
        f"Period: {manifest['start_date']} to {manifest['end_date']}",
        f"Generated at: {manifest['generated_at']}",
        f"Redaction mode: {manifest['redaction_mode']}",
        f"Definition version: {manifest['definition_version']}",
        f"Row count: {manifest['row_count']}",
        f"Checksum: {manifest.get('content_sha256', 'pending')}",
        "",
    ]
    if dataset.notes:
        lines.append("Notes:")
        lines.extend(dataset.notes)
        lines.append("")
    lines.append("Columns: " + ", ".join(dataset.columns))
    lines.append("")
    for index, row in enumerate(dataset.rows, start=1):
        row_parts = [f"{column}={_csv_cell(row.get(column))}" for column in dataset.columns]
        row_line = f"{index}. " + " | ".join(str(part) for part in row_parts)
        lines.extend(textwrap.wrap(row_line, width=118) or [""])
    if not dataset.rows:
        lines.append("No rows for this period/filter.")
    return lines


def _simple_pdf_bytes(lines: list[str]) -> bytes:
    wrapped_lines: list[str] = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(line, width=118) or [""])
    page_lines = [wrapped_lines[index : index + 62] for index in range(0, len(wrapped_lines), 62)]
    if not page_lines:
        page_lines = [["No report content."]]

    objects: dict[int, bytes] = {}
    page_object_ids: list[int] = []
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    next_id = 4
    for page_number, lines_for_page in enumerate(page_lines, start=1):
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        page_object_ids.append(page_id)
        text_commands = ["BT", "/F1 8 Tf", "10 TL", "36 800 Td"]
        for line in lines_for_page:
            text_commands.append(f"({_pdf_escape(line)}) Tj")
            text_commands.append("T*")
        text_commands.extend(
            [
                "T*",
                f"(Page {page_number} of {len(page_lines)}) Tj",
                "ET",
            ]
        )
        content = "\n".join(text_commands).encode("latin-1", errors="replace")
        objects[content_id] = (
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream"
        )
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            + f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode(
                "ascii"
            )
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("ascii")

    ordered_ids = sorted(objects)
    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {0: 0}
    for object_id in ordered_ids:
        offsets[object_id] = buffer.tell()
        buffer.write(f"{object_id} 0 obj\n".encode("ascii"))
        buffer.write(objects[object_id])
        buffer.write(b"\nendobj\n")
    xref_offset = buffer.tell()
    max_id = max(ordered_ids)
    buffer.write(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for object_id in range(1, max_id + 1):
        offset = offsets.get(object_id, 0)
        status = "n" if object_id in offsets else "f"
        generation = "00000" if object_id in offsets else "65535"
        buffer.write(f"{offset:010d} {generation} {status} \n".encode("ascii"))
    buffer.write(
        f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return buffer.getvalue()


def _render_csv(
    *,
    report_type: str,
    start_date: date,
    end_date: date,
    dataset: ReportDataset,
) -> RenderedReport:
    content = _rows_to_csv(columns=dataset.columns, rows=dataset.rows)
    content_bytes = content.encode("utf-8")
    filename = _report_filename(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        extension="csv",
    )
    return RenderedReport(
        content_type=CSV_CONTENT_TYPE,
        filename=filename,
        content=content,
        content_encoding=TEXT_CONTENT_ENCODING,
        content_sha256=_content_checksum_bytes(content_bytes),
        included_files=[
            {
                "filename": filename,
                "content_type": CSV_CONTENT_TYPE,
                "sha256": _content_checksum_bytes(content_bytes),
            }
        ],
    )


def _render_pdf(
    *,
    report_type: str,
    start_date: date,
    end_date: date,
    dataset: ReportDataset,
    manifest: dict[str, Any],
) -> RenderedReport:
    filename = _report_filename(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        extension="pdf",
    )
    pdf_bytes = _simple_pdf_bytes(_dataset_pdf_lines(manifest=manifest, dataset=dataset))
    checksum = _content_checksum_bytes(pdf_bytes)
    return RenderedReport(
        content_type=PDF_CONTENT_TYPE,
        filename=filename,
        content=base64.b64encode(pdf_bytes).decode("ascii"),
        content_encoding=BASE64_CONTENT_ENCODING,
        content_sha256=checksum,
        included_files=[
            {
                "filename": filename,
                "content_type": PDF_CONTENT_TYPE,
                "sha256": checksum,
            }
        ],
    )


def _render_zip(
    *,
    report_type: str,
    start_date: date,
    end_date: date,
    dataset: ReportDataset,
    manifest: dict[str, Any],
) -> RenderedReport:
    csv_rendered = _render_csv(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        dataset=dataset,
    )
    pdf_rendered = _render_pdf(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        dataset=dataset,
        manifest=manifest,
    )
    csv_bytes = csv_rendered.content.encode("utf-8")
    pdf_bytes = base64.b64decode(pdf_rendered.content.encode("ascii"))
    zip_filename = _report_filename(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        extension="zip",
    )
    manifest_filename = "manifest.json"
    package_manifest = {
        **manifest,
        "output_format": ReportOutputFormat.ZIP,
        "package_files": [
            *csv_rendered.included_files,
            *pdf_rendered.included_files,
            {
                "filename": manifest_filename,
                "content_type": "application/json",
                "sha256": "computed_inside_zip",
            },
        ],
    }
    manifest_bytes = json.dumps(package_manifest, sort_keys=True, indent=2, default=str).encode(
        "utf-8"
    )
    package_manifest["package_files"][-1]["sha256"] = _content_checksum_bytes(manifest_bytes)
    manifest_bytes = json.dumps(package_manifest, sort_keys=True, indent=2, default=str).encode(
        "utf-8"
    )
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(csv_rendered.filename, csv_bytes)
        archive.writestr(pdf_rendered.filename, pdf_bytes)
        archive.writestr(manifest_filename, manifest_bytes)
    zip_bytes = zip_buffer.getvalue()
    checksum = _content_checksum_bytes(zip_bytes)
    return RenderedReport(
        content_type=ZIP_CONTENT_TYPE,
        filename=zip_filename,
        content=base64.b64encode(zip_bytes).decode("ascii"),
        content_encoding=BASE64_CONTENT_ENCODING,
        content_sha256=checksum,
        included_files=[
            {
                "filename": zip_filename,
                "content_type": ZIP_CONTENT_TYPE,
                "sha256": checksum,
            },
            *csv_rendered.included_files,
            *pdf_rendered.included_files,
            {
                "filename": manifest_filename,
                "content_type": "application/json",
                "sha256": _content_checksum_bytes(manifest_bytes),
            },
        ],
    )


def _render_report(
    *,
    output_format: str,
    report_type: str,
    start_date: date,
    end_date: date,
    dataset: ReportDataset,
    manifest: dict[str, Any],
) -> RenderedReport:
    if output_format == ReportOutputFormat.CSV:
        return _render_csv(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            dataset=dataset,
        )
    if output_format == ReportOutputFormat.PDF:
        return _render_pdf(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            dataset=dataset,
            manifest=manifest,
        )
    if output_format == ReportOutputFormat.ZIP:
        return _render_zip(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            dataset=dataset,
            manifest=manifest,
        )
    raise ReportingValidationError(f"Unsupported report output format: {output_format}")


@transaction.atomic
def generate_report(command: GenerateReportCommand) -> GeneratedReportArtifact:
    _require_admin_actor(command.actor)
    report_type = _report_type(command.report_type)
    output_format = _output_format(command.output_format)
    redaction_mode = _redaction_mode(command.redaction_mode)
    generated_at = command.as_of or now_utc()
    period = _resolve_report_period(
        start_date=command.start_date,
        end_date=command.end_date,
        period_preset=command.period_preset,
        period_anchor_date=command.period_anchor_date,
        as_of=generated_at,
    )
    filters = dict(command.filters or {})

    dataset = _build_dataset(
        report_type=report_type,
        start_date=period.start_date,
        end_date=period.end_date,
        redaction_mode=redaction_mode,
        filters=filters,
    )
    manifest: dict[str, Any] = {
        "report_type": report_type,
        "output_format": output_format,
        "redaction_mode": redaction_mode,
        "period_preset": period.preset,
        "period_anchor_date": period.anchor_date.isoformat() if period.anchor_date else "",
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "generated_at": generated_at.isoformat(),
        "generated_by_admin_id": str(command.actor.pk),
        "definition_version": REPORT_DEFINITION_VERSION,
        "semantics": _report_semantics(report_type),
        "filters": filters,
        "columns": dataset.columns,
        "row_count": len(dataset.rows),
        "source_counts": dataset.source_counts,
        "notes": dataset.notes,
    }
    rendered = _render_report(
        output_format=output_format,
        report_type=report_type,
        start_date=period.start_date,
        end_date=period.end_date,
        dataset=dataset,
        manifest=manifest,
    )
    manifest.update(
        {
            "content_sha256": rendered.content_sha256,
            "filename": rendered.filename,
            "content_type": rendered.content_type,
            "content_encoding": rendered.content_encoding,
            "included_files": rendered.included_files,
        }
    )
    report_run = ReportRun.objects.create(
        report_type=report_type,
        output_format=output_format,
        redaction_mode=redaction_mode,
        start_date=period.start_date,
        end_date=period.end_date,
        generated_by_admin_id=command.actor.pk,
        generated_at=generated_at,
        definition_version=REPORT_DEFINITION_VERSION,
        filters=filters,
        row_count=len(dataset.rows),
        content_sha256=rendered.content_sha256,
        manifest=manifest,
        destination_note=command.destination_note.strip(),
        metadata={
            "content_type": rendered.content_type,
            "filename": rendered.filename,
            "content_encoding": rendered.content_encoding,
            "period_preset": period.preset,
            "period_anchor_date": period.anchor_date.isoformat() if period.anchor_date else "",
        },
    )
    ReportEvent.objects.create(
        report_run=report_run,
        event_type=ReportEventType.GENERATED,
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        metadata={
            "report_type": report_type,
            "output_format": output_format,
            "redaction_mode": redaction_mode,
            "row_count": len(dataset.rows),
            "content_sha256": rendered.content_sha256,
            "content_encoding": rendered.content_encoding,
        },
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="reporting.report_generated",
            target_type="report_run",
            target_id=str(report_run.id),
            metadata={
                "report_type": report_type,
                "output_format": output_format,
                "redaction_mode": redaction_mode,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "period_preset": period.preset,
                "row_count": len(dataset.rows),
                "content_sha256": rendered.content_sha256,
                "destination_note_present": bool(command.destination_note.strip()),
            },
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="report.generated",
            aggregate_type="report_run",
            aggregate_id=str(report_run.id),
            payload={
                "report_type": report_type,
                "output_format": output_format,
                "redaction_mode": redaction_mode,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "period_preset": period.preset,
                "row_count": len(dataset.rows),
                "content_sha256": rendered.content_sha256,
            },
        )
    )
    return GeneratedReportArtifact(
        report_run=report_run,
        content_type=rendered.content_type,
        filename=rendered.filename,
        content=rendered.content,
        content_encoding=rendered.content_encoding,
        manifest=manifest,
    )
