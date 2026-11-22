# IP of Webby-Soft SRL. 18.9: Swiss creditor modes (UID, mode, external debts, SNB rates).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("originator_claims", "0017_accrued_interest_pricing_18_7"),
    ]

    operations = [
        migrations.AddField(
            model_name="originatorloanprofile",
            name="borrower_uid",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
