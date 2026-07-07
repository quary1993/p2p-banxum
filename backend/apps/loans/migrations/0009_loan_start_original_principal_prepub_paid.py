from __future__ import annotations

from django.db import migrations, models
from django.db.models import F


def backfill_loan_schedule_fields(apps, schema_editor):
    loan_model = apps.get_model("loans", "Loan")
    loan_model.objects.filter(original_principal_minor__isnull=True).update(
        original_principal_minor=F("principal_minor")
    )
    loan_model.objects.filter(loan_start_date__isnull=True).update(
        loan_start_date=F("funding_deadline")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0008_alter_loanevent_event_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="loan",
            name="original_principal_minor",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="loan",
            name="loan_start_date",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="loan",
            name="pre_publication_paid_installments",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(backfill_loan_schedule_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="loan",
            name="original_principal_minor",
            field=models.BigIntegerField(),
        ),
        migrations.AlterField(
            model_name="loan",
            name="loan_start_date",
            field=models.DateField(),
        ),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=models.Q(original_principal_minor__gte=F("principal_minor")),
                name="loan_original_principal_not_below_financeable",
            ),
        ),
    ]
