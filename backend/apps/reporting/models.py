from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class ReportType(models.TextChoices):
    OPERATIONAL_SUBLEDGER = "operational_subledger", "Operational subledger"
    TRIAL_BALANCE = "trial_balance", "Trial balance"
    GARANTA_ACCRUED_REVENUE = "garanta_accrued_revenue", "Garanta accrued revenue"


class ReportOutputFormat(models.TextChoices):
    CSV = "csv", "CSV"


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
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["report_run", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
        ]
