from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import (
    AppendOnlyModel,
    PlatformDateTimeField,
    TimestampedModel,
)


class ReportType(models.TextChoices):
    OPERATIONAL_SUBLEDGER = "operational_subledger", "Operational subledger"
    TRIAL_BALANCE = "trial_balance", "Trial balance"
    GARANTA_ACCRUED_REVENUE = "garanta_accrued_revenue", "Garanta accrued revenue"
    BEXIO_ACCOUNTING_EXPORT = "bexio_accounting_export", "Bexio accounting export"
    BANK_OPERATIONS = "bank_operations", "Bank operations"
    RECONCILIATION = "reconciliation", "Reconciliation"
    INVESTOR_BALANCES = "investor_balances", "Investor balances"
    BALANCE_AGEING = "balance_ageing", "Balance ageing"
    WITHDRAWALS = "withdrawals", "Withdrawals"
    LOAN_FUNDING = "loan_funding", "Loan funding"
    REPAYMENT_STATUS = "repayment_status", "Repayment status"
    DEFAULT_EXPOSURE = "default_exposure", "Default exposure"
    RECOVERY_WRITE_OFF = "recovery_write_off", "Recovery/write-off"
    FX_ACTIVITY = "fx_activity", "FX activity"
    KYC_STATUS = "kyc_status", "KYC status"
    AUDIT_LOG = "audit_log", "Audit log"
    FAILED_OUTBOX = "failed_outbox", "Failed outbox"
    PARTICIPANT_ACCOUNT_STATEMENT = (
        "participant_account_statement",
        "Participant account statement",
    )
    ANNUAL_TAX_INFORMATION = "annual_tax_information", "Annual tax information"
    # 18.3: the design's investor reports (reporting/investor_reports.py).
    INVESTOR_PORTFOLIO = "investor_portfolio", "Portfolio report"
    INVESTOR_INTEREST_REPAYMENTS = "investor_interest_repayments", "Interest and repayments"
    INVESTOR_TAX_REPORT = "investor_tax_report", "Tax report"


class ReportOutputFormat(models.TextChoices):
    CSV = "csv", "CSV"
    PDF = "pdf", "PDF"
    ZIP = "zip", "ZIP evidence package"


class ReportPeriodPreset(models.TextChoices):
    CUSTOM = "custom", "Custom"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    YEARLY = "yearly", "Yearly"
    CALENDAR_YEAR = "calendar_year", "Calendar year"


class ReportRedactionMode(models.TextChoices):
    REDACTED = "redacted", "Redacted"
    FULL = "full", "Full"


class ReportEventType(models.TextChoices):
    GENERATED = "generated", "Generated"


class ReportRun(AppendOnlyModel, TimestampedModel):
    report_type = models.CharField(max_length=64, choices=ReportType.choices)
    output_format = models.CharField(max_length=16, choices=ReportOutputFormat.choices)
    redaction_mode = models.CharField(max_length=16, choices=ReportRedactionMode.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    generated_by_admin_id = models.UUIDField()
    generated_at = models.DateTimeField()
    definition_version = models.CharField(max_length=64)
    filters = models.JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    content_sha256 = models.CharField(max_length=64)
    manifest = models.JSONField(default=dict, blank=True)
    destination_note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-generated_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="reporting_report_run_valid_date_range",
            ),
        ]
        indexes = [
            models.Index(fields=["report_type", "start_date", "end_date"]),
            models.Index(fields=["generated_by_admin_id", "generated_at"]),
            models.Index(fields=["redaction_mode", "generated_at"]),
        ]


class ReportEvent(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_run = models.ForeignKey(
        ReportRun,
        on_delete=models.PROTECT,
        related_name="events",
    )
    event_type = models.CharField(max_length=64, choices=ReportEventType.choices)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = PlatformDateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["report_run", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
        ]


class InvestorReportKind(models.TextChoices):
    """18.3: the reports an investor creates (design #/reports) and the monthly statements."""

    ACCOUNT_STATEMENT = "account_statement", "Account statement"
    PORTFOLIO = "portfolio", "Portfolio report"
    INTEREST_REPAYMENTS = "interest_repayments", "Interest and repayments"
    TAX = "tax", "Tax report"
    MONTHLY_STATEMENT = "monthly_statement", "Monthly statement"


class InvestorReportDocument(AppendOnlyModel):
    """18.3: a report generated for one investor, kept so it opens again as it was issued.

    The file is stored as generated (base64 for PDF, text for CSV) with its checksum; the report
    run records how it was made. A monthly statement is created by the platform (automatic).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investor_user_id = models.UUIDField()
    kind = models.CharField(max_length=32, choices=InvestorReportKind.choices)
    # Empty: every currency of the investor (EUR and CHF are reported separately).
    currency = models.CharField(max_length=3, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    output_format = models.CharField(max_length=16, choices=ReportOutputFormat.choices)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    content_encoding = models.CharField(max_length=16)
    content = models.TextField()
    content_sha256 = models.CharField(max_length=64)
    issued_at = models.DateTimeField()
    automatic = models.BooleanField(default=False)
    report_run = models.ForeignKey(
        ReportRun, on_delete=models.PROTECT, related_name="investor_documents"
    )
    created_by_user_id = models.UUIDField()

    class Meta:
        ordering = ["-issued_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="reporting_investor_report_valid_date_range",
            ),
            # One automatic monthly statement per investor and month.
            models.UniqueConstraint(
                fields=["investor_user_id", "kind", "start_date"],
                condition=models.Q(automatic=True),
                name="reporting_one_automatic_statement_per_month",
            ),
        ]
        indexes = [models.Index(fields=["investor_user_id", "issued_at"])]
