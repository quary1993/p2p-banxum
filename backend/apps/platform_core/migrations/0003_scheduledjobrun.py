from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0002_append_only_guards"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledJobRun",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("job_name", models.CharField(max_length=128)),
                ("run_key", models.CharField(max_length=200, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        default="running",
                        max_length=32,
                    ),
                ),
                ("scheduled_for", models.DateTimeField()),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("attempt_count", models.PositiveIntegerField(default=1)),
                ("actor_user_id", models.UUIDField(blank=True, null=True)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["-started_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="scheduledjobrun",
            index=models.Index(
                fields=["job_name", "scheduled_for"],
                name="platform_co_job_nam_cfd649_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="scheduledjobrun",
            index=models.Index(fields=["status", "started_at"], name="platform_co_status_56517f_idx"),
        ),
    ]
