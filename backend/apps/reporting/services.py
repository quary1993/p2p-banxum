from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.apps import apps
from django.db import transaction
from django.db.models import Model

from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.time import now_utc
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event
from backend.apps.reporting.models import (
    ReportEvent,
    ReportEventType,
    ReportOutputFormat,
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


REPORT_DEFINITION_VERSION = "reporting-v1"
CSV_CONTENT_TYPE = "text/csv; charset=utf-8"

REVENUE_ACCOUNT_TYPES = frozenset(
    {
        "garanta_accrued_revenue",
        "platform_fee_revenue",
        "fx_fee_revenue",
        "fx_gain_loss",
    }
)


@dataclass(frozen=True, slots=True)
class GenerateReportCommand:
    actor: Model
    report_type: str
    start_date: date
    end_date: date
    output_format: str = ReportOutputFormat.CSV
    redaction_mode: str = ReportRedactionMode.REDACTED
    filters: dict[str, Any] | None = None
    destination_note: str = ""
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReportDataset:
    columns: list[str]
    rows: list[dict[str, Any]]
    source_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class GeneratedReportArtifact:
    report_run: ReportRun
    content_type: str
    filename: str
    content: str
    manifest: dict[str, Any]


def _ledger_model(model_name: str) -> Any:
    return apps.get_model("ledger", model_name)


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
        output_format = str(ReportOutputFormat(value))
    except ValueError as exc:
        raise ReportingValidationError(f"Unsupported report output format: {value}") from exc
    if output_format != ReportOutputFormat.CSV:
        raise ReportingValidationError("Only CSV report output is implemented in this slice.")
    return output_format


def _redaction_mode(value: str) -> str:
    try:
        return str(ReportRedactionMode(value))
    except ValueError as exc:
        raise ReportingValidationError(f"Unsupported report redaction mode: {value}") from exc


def _validate_date_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ReportingValidationError("Report end date must be on or after start date.")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _redacted_identifier(value: Any, *, redaction_mode: str) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    if redaction_mode == ReportRedactionMode.FULL:
        return raw
    return "REDACTED"


def _redacted_json(value: Any, *, redaction_mode: str) -> str:
    if redaction_mode == ReportRedactionMode.FULL:
        return _stable_json(value or {})
    if value:
        return "{}"
    return "{}"


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
        return _stable_json(value)
    return str(value)


def _rows_to_csv(*, columns: list[str], rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _csv_cell(row.get(column)) for column in columns})
    return buffer.getvalue()


def _content_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _report_filename(*, report_type: str, start_date: date, end_date: date) -> str:
    return f"{report_type}_{start_date.isoformat()}_{end_date.isoformat()}.csv"


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
    currency_filter = str(filters.get("currency", "")).upper()
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
    if currency_filter:
        queryset = queryset.filter(currency__code=currency_filter)

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
                "account_owner_id": (
                    _redacted_identifier(account.owner_id, redaction_mode=redaction_mode)
                    if owner_type == "investor"
                    else str(account.owner_id or "")
                ),
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
    currency_filter = str(filters.get("currency", "")).upper()
    queryset = (
        posting_model.objects.select_related("journal_entry", "account", "currency")
        .filter(
            journal_entry__value_date__gte=start_date,
            journal_entry__value_date__lte=end_date,
        )
        .order_by("currency__code", "account__code", "id")
    )
    if currency_filter:
        queryset = queryset.filter(currency__code=currency_filter)

    grouped: dict[str, dict[str, Any]] = {}
    for posting in list(queryset):
        account = posting.account
        key = str(account.id)
        owner_type = str(account.owner_type or "")
        if key not in grouped:
            grouped[key] = {
                "currency": posting.currency.code,
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.account_type,
                "account_owner_type": owner_type,
                "account_owner_id": (
                    _redacted_identifier(account.owner_id, redaction_mode=redaction_mode)
                    if owner_type == "investor"
                    else str(account.owner_id or "")
                ),
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
    return ReportDataset(
        columns=columns,
        rows=rows,
        source_counts={"ledger_accounts": len(rows), "ledger_postings": int(queryset.count())},
    )


def _garanta_accrued_revenue_dataset(
    *,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
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
    currency_filter = str(filters.get("currency", "")).upper()
    queryset = (
        posting_model.objects.select_related("journal_entry", "account", "currency")
        .filter(
            account__account_type__in=REVENUE_ACCOUNT_TYPES,
            journal_entry__value_date__gte=start_date,
            journal_entry__value_date__lte=end_date,
        )
        .order_by("currency__code", "account__account_type", "journal_entry__event_type", "id")
    )
    if currency_filter:
        queryset = queryset.filter(currency__code=currency_filter)

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for posting in list(queryset):
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
        source_counts={"ledger_postings": int(queryset.count())},
    )


def _build_dataset(
    *,
    report_type: str,
    start_date: date,
    end_date: date,
    redaction_mode: str,
    filters: dict[str, Any],
) -> ReportDataset:
    if report_type == ReportType.OPERATIONAL_SUBLEDGER:
        return _operational_subledger_dataset(
            start_date=start_date,
            end_date=end_date,
            redaction_mode=redaction_mode,
            filters=filters,
        )
    if report_type == ReportType.TRIAL_BALANCE:
        return _trial_balance_dataset(
            start_date=start_date,
            end_date=end_date,
            redaction_mode=redaction_mode,
            filters=filters,
        )
    if report_type == ReportType.GARANTA_ACCRUED_REVENUE:
        return _garanta_accrued_revenue_dataset(
            start_date=start_date,
            end_date=end_date,
            redaction_mode=redaction_mode,
            filters=filters,
        )
    raise ReportingValidationError(f"Unsupported report type: {report_type}")


@transaction.atomic
def generate_report(command: GenerateReportCommand) -> GeneratedReportArtifact:
    _require_admin_actor(command.actor)
    report_type = _report_type(command.report_type)
    output_format = _output_format(command.output_format)
    redaction_mode = _redaction_mode(command.redaction_mode)
    _validate_date_range(command.start_date, command.end_date)
    filters = dict(command.filters or {})
    generated_at = command.as_of or now_utc()

    dataset = _build_dataset(
        report_type=report_type,
        start_date=command.start_date,
        end_date=command.end_date,
        redaction_mode=redaction_mode,
        filters=filters,
    )
    content = _rows_to_csv(columns=dataset.columns, rows=dataset.rows)
    checksum = _content_checksum(content)
    filename = _report_filename(
        report_type=report_type,
        start_date=command.start_date,
        end_date=command.end_date,
    )
    manifest = {
        "report_type": report_type,
        "output_format": output_format,
        "redaction_mode": redaction_mode,
        "start_date": command.start_date.isoformat(),
        "end_date": command.end_date.isoformat(),
        "generated_at": generated_at.isoformat(),
        "generated_by_admin_id": str(command.actor.pk),
        "definition_version": REPORT_DEFINITION_VERSION,
        "filters": filters,
        "columns": dataset.columns,
        "row_count": len(dataset.rows),
        "source_counts": dataset.source_counts,
        "content_sha256": checksum,
        "filename": filename,
    }
    report_run = ReportRun.objects.create(
        report_type=report_type,
        output_format=output_format,
        redaction_mode=redaction_mode,
        start_date=command.start_date,
        end_date=command.end_date,
        generated_by_admin_id=command.actor.pk,
        generated_at=generated_at,
        definition_version=REPORT_DEFINITION_VERSION,
        filters=filters,
        row_count=len(dataset.rows),
        content_sha256=checksum,
        manifest=manifest,
        destination_note=command.destination_note.strip(),
        metadata={"content_type": CSV_CONTENT_TYPE, "filename": filename},
    )
    ReportEvent.objects.create(
        report_run=report_run,
        event_type=ReportEventType.GENERATED,
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        metadata={
            "report_type": report_type,
            "redaction_mode": redaction_mode,
            "row_count": len(dataset.rows),
            "content_sha256": checksum,
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
                "start_date": command.start_date.isoformat(),
                "end_date": command.end_date.isoformat(),
                "row_count": len(dataset.rows),
                "content_sha256": checksum,
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
                "start_date": command.start_date.isoformat(),
                "end_date": command.end_date.isoformat(),
                "row_count": len(dataset.rows),
                "content_sha256": checksum,
            },
        )
    )
    return GeneratedReportArtifact(
        report_run=report_run,
        content_type=CSV_CONTENT_TYPE,
        filename=filename,
        content=content,
        manifest=manifest,
    )
