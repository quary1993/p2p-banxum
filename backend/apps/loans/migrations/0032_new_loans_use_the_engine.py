# IP of Webby-Soft SRL. Audit S5-7: a new loan uses the 18.6 engine by default.
# No data change: the loans of migration 0029 keep legacy_monthly.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0031_security_asset_reference"),
    ]

    operations = [
        migrations.AlterField(
            model_name="loan",
            name="interest_convention",
            field=models.CharField(
                choices=[
                    ("act_365_fixed", "Actual/365 Fixed (18.6 engine)"),
                    ("legacy_monthly", "Earlier schedule (before 18.6)"),
                ],
                default="act_365_fixed",
                max_length=32,
            ),
        ),
    ]
