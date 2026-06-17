from __future__ import annotations

import base64
import csv
import hashlib
import io
import zipfile
from datetime import date, datetime, time
from importlib import import_module
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client

from backend.apps.platform_core.domain.time import business_timezone
from backend.apps.platform_core.models import AuditEvent, Currency, DomainEvent, OutboxMessage
from backend.apps.platform_core.models.base import AppendOnlyViolation
from backend.apps.reporting.models import (
    ReportEvent,
    ReportOutputFormat,
    ReportPeriodPreset,
    ReportRedactionMode,
    ReportRun,
    ReportType,
)
from backend.apps.reporting.services import (
    GenerateReportCommand,
    ReportingAuthorizationError,
    generate_report,
)


@pytest.fixture
def admin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="reporting-admin@example.test",
            password="AdminPass123!",
            full_name="Reporting Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


@pytest.fixture
def superadmin_user() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_superuser(
            email="reporting-superadmin@example.test",
            password="AdminPass123!",
            full_name="Reporting Superadmin",
        ),
    )


@pytest.fixture
def investor() -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email="reporting-investor@example.test",
            full_name="Reporting Investor",
            account_type="natural_person_lender",
            status="active",
            is_staff=False,
        ),
    )


def _received_at(value_date: date) -> datetime:
    return datetime.combine(value_date, time.min, tzinfo=business_timezone())


def _declare_deposit(
    admin_user: Model,
    investor: Model,
    *,
    amount_minor: int = 100_00,
    idempotency_key: str = "reporting-deposit-1",
    value_date: date = date(2026, 1, 5),
    bank_reference: str | None = None,
) -> None:
    ledger_services: Any = import_module("backend.apps.ledger.services")
    ledger_services.declare_lender_deposit(
        ledger_services.DeclareLenderDepositCommand(
            actor=admin_user,
            investor_user_id=str(investor.pk),
            amount_minor=amount_minor,
            currency="CHF",
            booking_date=value_date,
            value_date=value_date,
            collection_account_identifier="CH00GARANTAREPORT",
            payer_name="Reporting Investor",
            payer_account_identifier="CH11REPORTINVESTOR",
            bank_reference=bank_reference or f"BANK-{idempotency_key}",
            payment_reference=f"INV-{investor.pk}",
            evidence_reference=f"statement:{idempotency_key}",
            notes="Matched for reporting test.",
            idempotency_key=idempotency_key,
        )
    )


def _post_platform_fee_revenue(
    admin_user: Model,
    *,
    amount_minor: int = 25_00,
    value_date: date = date(2026, 1, 7),
    idempotency_key: str = "reporting-revenue-1",
) -> None:
    ledger_services: Any = import_module("backend.apps.ledger.services")
    currency = Currency.objects.get(code="CHF")
    collection_cash = ledger_services.get_or_create_ledger_account(
        account_type="collection_cash",
        currency=currency,
    )
    platform_fee_revenue = ledger_services.get_or_create_ledger_account(
        account_type="platform_fee_revenue",
        currency=currency,
        owner_type="garanta",
        owner_id="platform",
        name="CHF platform fee revenue",
    )
    ledger_services.post_journal_entry(
        ledger_services.PostJournalEntryCommand(
            actor=admin_user,
            event_type="secondary_market_purchase_settled",
            direction="internal",
            currency="CHF",
            gross_amount_minor=amount_minor,
            net_amount_minor=amount_minor,
            booking_date=value_date,
            value_date=value_date,
            effective_at=_received_at(value_date),
            received_at=_received_at(value_date),
            source_type="reporting_test",
            source_id=idempotency_key,
            idempotency_key=idempotency_key,
            postings=[
                ledger_services.PostingCommand(
                    account=collection_cash,
                    side="debit",
                    amount_minor=amount_minor,
                    memo="Cash received for platform fee",
                ),
                ledger_services.PostingCommand(
                    account=platform_fee_revenue,
                    side="credit",
                    amount_minor=amount_minor,
                    memo="Platform fee revenue",
                ),
            ],
        )
    )


def _csv_rows(content: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content)))


@pytest.mark.django_db
def test_operational_subledger_csv_redacts_sensitive_fields_and_logs(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)

    artifact = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.OPERATIONAL_SUBLEDGER,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            redaction_mode=ReportRedactionMode.REDACTED,
        )
    )

    rows = _csv_rows(artifact.content)
    assert artifact.report_run.row_count == 2
    assert artifact.manifest["row_count"] == 2
    assert artifact.report_run.content_sha256 == hashlib.sha256(
        artifact.content.encode("utf-8")
    ).hexdigest()
    assert {row["posting_side"] for row in rows} == {"debit", "credit"}
    assert {row["lender_user_id"] for row in rows} == {"REDACTED"}
    assert {row["bank_reference"] for row in rows} == {"REDACTED"}
    investor_owner_rows = [row for row in rows if row["account_owner_type"] == "investor"]
    assert investor_owner_rows
    assert {row["account_owner_id"] for row in investor_owner_rows} == {"REDACTED"}
    assert "BANK-reporting-deposit-1" not in artifact.content
    assert ReportRun.objects.count() == 1
    assert ReportEvent.objects.filter(event_type="generated").count() == 1
    assert AuditEvent.objects.filter(action="reporting.report_generated").count() == 1
    assert DomainEvent.objects.filter(event_type="report.generated").count() == 1


@pytest.mark.django_db
def test_operational_subledger_full_mode_keeps_source_identifiers(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor, idempotency_key="reporting-deposit-full")

    artifact = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.OPERATIONAL_SUBLEDGER,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            redaction_mode=ReportRedactionMode.FULL,
            destination_note="Full export for accountant review.",
        )
    )

    rows = _csv_rows(artifact.content)
    assert {row["lender_user_id"] for row in rows} == {str(investor.pk)}
    assert {row["bank_reference"] for row in rows} == {"BANK-reporting-deposit-full"}
    assert artifact.report_run.destination_note == "Full export for accountant review."


@pytest.mark.django_db
def test_full_exports_require_superadmin(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor, idempotency_key="reporting-deposit-full-denied")

    with pytest.raises(ReportingAuthorizationError, match="Full report exports require"):
        generate_report(
            GenerateReportCommand(
                actor=admin_user,
                report_type=ReportType.OPERATIONAL_SUBLEDGER,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                redaction_mode=ReportRedactionMode.FULL,
            )
        )


@pytest.mark.django_db
def test_sensitive_report_types_require_superadmin_even_when_redacted(
    admin_user: Model,
    superadmin_user: Model,
) -> None:
    with pytest.raises(ReportingAuthorizationError, match="requires an active superadmin"):
        generate_report(
            GenerateReportCommand(
                actor=admin_user,
                report_type=ReportType.KYC_STATUS,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                redaction_mode=ReportRedactionMode.REDACTED,
            )
        )

    artifact = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.KYC_STATUS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            redaction_mode=ReportRedactionMode.REDACTED,
        )
    )
    assert artifact.report_run.report_type == "kyc_status"


@pytest.mark.django_db
def test_operational_subledger_neutralizes_csv_formula_cells_in_full_mode(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(
        admin_user,
        investor,
        idempotency_key="reporting-deposit-formula",
        bank_reference='=HYPERLINK("https://evil.example","open")',
    )

    artifact = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.OPERATIONAL_SUBLEDGER,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            redaction_mode=ReportRedactionMode.FULL,
        )
    )

    rows = _csv_rows(artifact.content)
    assert {row["bank_reference"] for row in rows} == {
        '\'=HYPERLINK("https://evil.example","open")'
    }
    assert ',"=HYPERLINK' not in artifact.content
    assert ',"\'=HYPERLINK' in artifact.content


@pytest.mark.django_db
def test_trial_balance_is_as_of_end_date_and_adds_currency_total(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(
        admin_user,
        investor,
        amount_minor=50_00,
        idempotency_key="reporting-deposit-prior-period",
        value_date=date(2025, 12, 31),
    )
    _declare_deposit(admin_user, investor, amount_minor=100_00)
    _post_platform_fee_revenue(admin_user, amount_minor=25_00)

    artifact = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.TRIAL_BALANCE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            redaction_mode=ReportRedactionMode.FULL,
        )
    )

    rows = _csv_rows(artifact.content)
    by_account_type = {row["account_type"]: row for row in rows}
    assert artifact.manifest["semantics"] == (
        "as_of_end_date_cumulative_balances_with_currency_control_totals"
    )
    assert int(by_account_type["collection_cash"]["total_debit_minor"]) == 175_00
    assert int(by_account_type["collection_cash"]["total_credit_minor"]) == 0
    assert int(by_account_type["collection_cash"]["signed_balance_minor"]) == 175_00
    assert int(by_account_type["investor_balance_liability"]["total_credit_minor"]) == 150_00
    assert int(by_account_type["investor_balance_liability"]["signed_balance_minor"]) == -150_00
    assert int(by_account_type["platform_fee_revenue"]["total_credit_minor"]) == 25_00
    assert int(by_account_type["platform_fee_revenue"]["signed_balance_minor"]) == -25_00
    total_row = by_account_type["control_total"]
    assert total_row["row_type"] == "currency_total"
    assert total_row["account_code"] == "__TOTAL__"
    assert int(total_row["total_debit_minor"]) == 175_00
    assert int(total_row["total_credit_minor"]) == 175_00
    assert int(total_row["signed_balance_minor"]) == 0


@pytest.mark.django_db
def test_garanta_accrued_revenue_report_aggregates_revenue_accounts(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor, amount_minor=100_00)
    _post_platform_fee_revenue(admin_user, amount_minor=25_00)

    artifact = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.GARANTA_ACCRUED_REVENUE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
    )

    rows = _csv_rows(artifact.content)
    assert rows == [
        {
            "currency": "CHF",
            "account_type": "platform_fee_revenue",
            "event_type": "secondary_market_purchase_settled",
            "total_credit_minor": "2500",
            "total_debit_minor": "0",
            "net_revenue_minor": "2500",
            "entry_count": "1",
        }
    ]


@pytest.mark.django_db
def test_report_api_is_admin_only_and_returns_csv_payload(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)
    client = Client()
    client.force_login(cast(Any, investor))
    forbidden_response = client.post(
        "/api/v1/reporting/admin/reports/",
        data={
            "report_type": "operational_subledger",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
        content_type="application/json",
    )
    assert forbidden_response.status_code == 403

    client.force_login(cast(Any, admin_user))
    response = client.post(
        "/api/v1/reporting/admin/reports/",
        data={
            "report_type": "operational_subledger",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "output_format": "csv",
            "redaction_mode": "redacted",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["content_type"] == "text/csv; charset=utf-8"
    assert payload["content_encoding"] == "text"
    assert payload["filename"] == "operational_subledger_2026-01-01_2026-01-31.csv"
    assert payload["manifest"]["row_count"] == 2


@pytest.mark.django_db
def test_monthly_period_preset_resolves_dates_and_pdf_payload(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)

    artifact = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.OPERATIONAL_SUBLEDGER,
            period_preset=ReportPeriodPreset.MONTHLY,
            period_anchor_date=date(2026, 1, 15),
            output_format=ReportOutputFormat.PDF,
            redaction_mode=ReportRedactionMode.REDACTED,
        )
    )

    pdf_bytes = base64.b64decode(artifact.content.encode("ascii"))
    assert artifact.content_type == "application/pdf"
    assert artifact.content_encoding == "base64"
    assert artifact.filename == "operational_subledger_2026-01-01_2026-01-31.pdf"
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/MediaBox [0 0 842 595]" in pdf_bytes
    assert b"(BANXUM)" in pdf_bytes
    assert b"(Operational Subledger report)" in pdf_bytes
    assert b"(Table 1 of " in pdf_bytes
    assert b"(Confidential export." in pdf_bytes
    assert artifact.report_run.start_date == date(2026, 1, 1)
    assert artifact.report_run.end_date == date(2026, 1, 31)
    assert artifact.manifest["period_preset"] == "monthly"
    assert artifact.report_run.content_sha256 == hashlib.sha256(pdf_bytes).hexdigest()


@pytest.mark.django_db
def test_zip_evidence_package_contains_manifest_csv_and_pdf(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)

    artifact = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.BANK_OPERATIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            output_format=ReportOutputFormat.ZIP,
        )
    )

    zip_bytes = base64.b64decode(artifact.content.encode("ascii"))
    assert artifact.content_type == "application/zip"
    assert artifact.content_encoding == "base64"
    assert artifact.report_run.content_sha256 == hashlib.sha256(zip_bytes).hexdigest()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "bank_operations_2026-01-01_2026-01-31.csv" in names
        assert "bank_operations_2026-01-01_2026-01-31.pdf" in names
        assert {info.date_time for info in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}
        manifest = archive.read("manifest.json").decode("utf-8")
    assert '"report_type": "bank_operations"' in manifest
    assert artifact.manifest["included_files"]


@pytest.mark.django_db
def test_zip_evidence_package_checksum_is_reproducible_with_same_generation_metadata(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)
    pinned_as_of = datetime(2026, 1, 31, 12, 0, tzinfo=business_timezone())

    first = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.BANK_OPERATIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            output_format=ReportOutputFormat.ZIP,
            as_of=pinned_as_of,
        )
    )
    second = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.BANK_OPERATIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            output_format=ReportOutputFormat.ZIP,
            as_of=pinned_as_of,
        )
    )

    assert first.content == second.content
    assert first.report_run.content_sha256 == second.report_run.content_sha256


@pytest.mark.django_db
def test_bank_operations_report_redacts_counterparty_and_bank_fields(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)

    artifact = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.BANK_OPERATIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            redaction_mode=ReportRedactionMode.REDACTED,
        )
    )

    rows = _csv_rows(artifact.content)
    assert rows[0]["payer_name"] == "REDACTED"
    assert rows[0]["payer_account_identifier"] == "REDACTED"
    assert rows[0]["bank_reference"] == "REDACTED"
    assert "Reporting Investor" not in artifact.content


@pytest.mark.django_db
def test_bexio_export_uses_configurable_account_mapping_and_marks_unmapped(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)

    artifact = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.BEXIO_ACCOUNTING_EXPORT,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            redaction_mode=ReportRedactionMode.FULL,
            filters={
                "bexio_mapping": {
                    "account_types": {
                        "collection_cash": {
                            "account_code": "1020",
                            "tax_code": "NA",
                            "label": "Collection cash",
                        }
                    }
                }
            },
        )
    )

    rows = _csv_rows(artifact.content)
    by_account_type = {row["ledger_account_type"]: row for row in rows}
    assert by_account_type["collection_cash"]["bexio_account_code"] == "1020"
    assert by_account_type["collection_cash"]["bexio_tax_code"] == "NA"
    assert by_account_type["collection_cash"]["mapping_status"] == "configured"
    assert by_account_type["investor_balance_liability"]["mapping_status"] == "unmapped"
    assert artifact.manifest["notes"]


@pytest.mark.django_db
def test_participant_statement_and_annual_garanta_tax_info_are_ledger_derived(
    admin_user: Model,
    superadmin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)
    _post_platform_fee_revenue(admin_user, amount_minor=25_00)

    statement = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.PARTICIPANT_ACCOUNT_STATEMENT,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            redaction_mode=ReportRedactionMode.FULL,
            filters={"participant_type": "lender", "participant_id": str(investor.pk)},
        )
    )
    statement_rows = _csv_rows(statement.content)
    assert statement_rows
    assert {row["participant_id"] for row in statement_rows} == {str(investor.pk)}
    assert "principal_or_settlement_movement" in {
        row["statement_section"] for row in statement_rows
    }

    tax_info = generate_report(
        GenerateReportCommand(
            actor=superadmin_user,
            report_type=ReportType.ANNUAL_TAX_INFORMATION,
            period_preset=ReportPeriodPreset.CALENDAR_YEAR,
            period_anchor_date=date(2026, 6, 1),
            filters={"participant_type": "garanta"},
        )
    )
    tax_rows = _csv_rows(tax_info.content)
    assert {
        row["category"] for row in tax_rows
    } >= {
        "platform_revenue:platform_fee_revenue:secondary_market_purchase_settled",
        "informational_only_not_tax_advice",
    }
    revenue_row = next(
        row
        for row in tax_rows
        if row["category"]
        == "platform_revenue:platform_fee_revenue:secondary_market_purchase_settled"
    )
    assert revenue_row["amount_minor"] == "2500"


@pytest.mark.django_db
def test_failed_outbox_report_redacts_payload_and_error_by_default(admin_user: Model) -> None:
    OutboxMessage.objects.create(
        idempotency_key="failed-email-reporting-test",
        topic="email.transactional.installment",
        payload={"recipient": "investor@example.test", "body": "private"},
        status="dead_letter",
        attempts=8,
        last_error="smtp rejected investor@example.test",
    )

    artifact = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.FAILED_OUTBOX,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            redaction_mode=ReportRedactionMode.REDACTED,
        )
    )

    rows = _csv_rows(artifact.content)
    assert rows == [
        {
            "outbox_message_id": rows[0]["outbox_message_id"],
            "idempotency_key": "failed-email-reporting-test",
            "topic": "email.transactional.installment",
            "status": "dead_letter",
            "attempts": "8",
            "next_attempt_at": "",
            "processed_at": "",
            "last_error": "REDACTED",
            "payload_json": "{}",
            "created_at": rows[0]["created_at"],
            "updated_at": rows[0]["updated_at"],
        }
    ]
    assert "investor@example.test" not in artifact.content


@pytest.mark.django_db
def test_report_run_and_event_have_app_and_db_append_only_guards(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)
    artifact = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.OPERATIONAL_SUBLEDGER,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
    )
    event = ReportEvent.objects.get(report_run=artifact.report_run)
    guarded_records = [
        (artifact.report_run, ReportRun, "reporting_reportrun"),
        (event, ReportEvent, "reporting_reportevent"),
    ]

    for record, model, table in guarded_records:
        record_id = record.pk
        db_record_id = record_id.hex
        with pytest.raises(AppendOnlyViolation):
            record.save()
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).update(id=record_id)
        with pytest.raises(AppendOnlyViolation):
            model.objects.filter(pk=record_id).delete()

        with pytest.raises(DatabaseError) as update_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {table} SET id = %s WHERE id = %s",
                    [db_record_id, db_record_id],
                )
        assert "append-only" in str(update_error.value)

        with pytest.raises(DatabaseError) as delete_error, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE id = %s", [db_record_id])
        assert "append-only" in str(delete_error.value)


@pytest.mark.django_db
def test_same_source_report_is_reproducible_by_content_checksum(
    admin_user: Model,
    investor: Model,
) -> None:
    _declare_deposit(admin_user, investor)

    first = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.TRIAL_BALANCE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            output_format=ReportOutputFormat.CSV,
            redaction_mode=ReportRedactionMode.REDACTED,
        )
    )
    second = generate_report(
        GenerateReportCommand(
            actor=admin_user,
            report_type=ReportType.TRIAL_BALANCE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            output_format=ReportOutputFormat.CSV,
            redaction_mode=ReportRedactionMode.REDACTED,
        )
    )

    assert first.content == second.content
    assert first.report_run.content_sha256 == second.report_run.content_sha256
    assert ReportRun.objects.count() == 2
