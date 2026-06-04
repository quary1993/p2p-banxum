from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ReportRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "report_type",
                    models.CharField(
                        choices=[
                            ("operational_subledger", "Operational subledger"),
                            ("trial_balance", "Trial balance"),
                            ("garanta_accrued_revenue", "Garanta accrued revenue"),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    "output_format",
                    models.CharField(choices=[("csv", "CSV")], max_length=16),
                ),
                (
                    "redaction_mode",
                    models.CharField(
                        choices=[("redacted", "Redacted"), ("full", "Full")],
                        max_length=16,
                    ),
                ),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("generated_by_admin_id", models.UUIDField()),
                ("generated_at", models.DateTimeField()),
                ("definition_version", models.CharField(max_length=64)),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("content_sha256", models.CharField(max_length=64)),
                ("manifest", models.JSONField(blank=True, default=dict)),
                ("destination_note", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["-generated_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["report_type", "start_date", "end_date"],
                        name="reporting_r_report__c1acd2_idx",
                    ),
                    models.Index(
                        fields=["generated_by_admin_id", "generated_at"],
                        name="reporting_r_generat_59330a_idx",
                    ),
                    models.Index(
                        fields=["redaction_mode", "generated_at"],
                        name="reporting_r_redacti_d96547_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("end_date__gte", models.F("start_date"))),
                        name="reporting_report_run_valid_date_range",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ReportEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "event_type",
                    models.CharField(choices=[("generated", "Generated")], max_length=64),
                ),
                ("actor_user_id", models.UUIDField()),
                ("actor_account_type", models.CharField(max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="reporting.reportrun",
                    ),
                ),
            ],
            options={
                "ordering": ["occurred_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["report_run", "occurred_at"],
                        name="reporting_r_report__f1d973_idx",
                    ),
                    models.Index(
                        fields=["actor_user_id", "occurred_at"],
                        name="reporting_r_actor_u_6d7265_idx",
                    ),
                    models.Index(
                        fields=["event_type", "occurred_at"],
                        name="reporting_r_event_t_b8a200_idx",
                    ),
                ],
            },
        ),
    ]
