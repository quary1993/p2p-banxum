from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ledger", "0008_alter_investorbalancelot_source_type")]

    operations = [
        migrations.RemoveConstraint(
            model_name="investorpayoutinstruction",
            name="ledger_one_active_payout_instruction_per_currency",
        ),
        migrations.AddConstraint(
            model_name="investorpayoutinstruction",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="active"),
                fields=("investor_user_id", "currency", "destination_iban"),
                name="ledger_unique_active_payout_iban_per_currency",
            ),
        ),
    ]
