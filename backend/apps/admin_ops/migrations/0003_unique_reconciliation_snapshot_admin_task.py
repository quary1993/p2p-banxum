from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("admin_ops", "0002_admin_task_event_append_only_guard"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="admintask",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("related_object_type", "ReconciliationSnapshot"),
                    ("task_type", "payment_reconciliation"),
                ),
                fields=("task_type", "related_object_type", "related_object_id"),
                name="unique_reconciliation_snapshot_admin_task",
            ),
        ),
    ]
