from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0007_alter_loanevent_event_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="loanevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("updated", "Updated"),
                    ("published", "Published"),
                    ("funding_closed", "Funding closed"),
                    ("funding_cancelled", "Funding cancelled"),
                    ("schedule_generated", "Schedule generated"),
                    ("servicing_status_changed", "Servicing status changed"),
                    ("recovery_recorded", "Recovery recorded"),
                    ("write_off_recorded", "Write-off recorded"),
                ],
                max_length=32,
            ),
        ),
    ]
