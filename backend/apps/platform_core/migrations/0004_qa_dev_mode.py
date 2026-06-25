from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0003_scheduledjobrun"),
    ]

    operations = [
        migrations.CreateModel(
            name="QaDevModeState",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "singleton_id",
                    models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False),
                ),
                ("is_enabled", models.BooleanField(default=False)),
                ("entered_at", models.DateTimeField(blank=True, null=True)),
                ("entered_by_user_id", models.UUIDField(blank=True, null=True)),
                ("current_time", models.DateTimeField(blank=True, null=True)),
                ("snapshot_path", models.TextField(blank=True)),
                ("snapshot_created_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.TextField(blank=True)),
                ("last_advanced_at", models.DateTimeField(blank=True, null=True)),
                ("last_advance_summary", models.JSONField(blank=True, default=dict)),
            ],
        ),
        migrations.AddConstraint(
            model_name="qadevmodestate",
            constraint=models.CheckConstraint(
                condition=models.Q(("singleton_id", 1)),
                name="qa_dev_mode_singleton_id_one",
            ),
        ),
    ]
