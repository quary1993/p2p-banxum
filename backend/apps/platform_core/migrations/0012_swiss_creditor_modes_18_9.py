# IP of Webby-Soft SRL. 18.9: Swiss creditor modes (UID, mode, external debts, SNB rates).

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_core", "0011_return_rule_56_days"),
    ]

    operations = [
        migrations.CreateModel(
            name="SnbReferenceRate",
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
                ("currency", models.CharField(max_length=3)),
                ("rate_date", models.DateField()),
                ("chf_per_unit", models.DecimalField(decimal_places=6, max_digits=12)),
                ("source", models.CharField(max_length=255)),
                ("entered_by_admin_id", models.UUIDField()),
            ],
            options={
                "ordering": ["-rate_date", "currency"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("currency", "rate_date"),
                        name="platform_core_snb_rate_unique_day",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("chf_per_unit__gt", 0)),
                        name="platform_core_snb_rate_positive",
                    ),
                ],
            },
        ),
    ]
