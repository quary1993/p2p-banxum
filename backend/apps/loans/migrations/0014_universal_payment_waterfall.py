from django.db import migrations, models


WATERFALL_VERSION = "garanta_costs_penalty_interest_principal_v2"


def apply_universal_waterfall(apps, schema_editor):
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.exclude(recovery_waterfall_version=WATERFALL_VERSION).update(
        recovery_waterfall_version=WATERFALL_VERSION
    )


class Migration(migrations.Migration):
    dependencies = [("loans", "0013_loan_skin_in_the_game_bps_and_more")]

    operations = [
        migrations.AlterField(
            model_name="loan",
            name="recovery_waterfall_version",
            field=models.CharField(default=WATERFALL_VERSION, max_length=64),
        ),
        migrations.RunPython(apply_universal_waterfall, migrations.RunPython.noop),
    ]
