# IP of Webby-Soft SRL. Audit S6-9: the originator's identifier of the underlying financing.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0032_new_loans_use_the_engine"),
        ("originator_claims", "0018_swiss_creditor_modes_18_9"),
    ]

    operations = [
        migrations.AddField(
            model_name="originatorloanprofile",
            name="underlying_financing_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddConstraint(
            model_name="originatorloanprofile",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    models.Q(("underlying_financing_id", ""), _negated=True),
                    models.Q(("opportunity_status", "cancelled"), _negated=True),
                ),
                fields=("originator", "underlying_financing_id"),
                name="originator_one_live_offer_per_underlying_financing",
            ),
        ),
    ]
