# IP of Webby-Soft SRL.
"""18.4 (Q01, transition): each balance lot stores its return days.

Lots that exist before this migration keep the 58-day rule of 2026-10-16 and its dates (the column
is added with 58 for them); new lots get the setting `balance.auto_return_after_days` (56).
"""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0014_release_penalty_mode_lots"),
        ("platform_core", "0011_return_rule_56_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="investorbalancelot",
            name="return_after_days",
            field=models.PositiveSmallIntegerField(default=58),
        ),
        migrations.AlterField(
            model_name="investorbalancelot",
            name="return_after_days",
            field=models.PositiveSmallIntegerField(default=56),
        ),
    ]
