from __future__ import annotations

from datetime import timedelta

from django.db import migrations, models
from django.db.models import F


def backfill_refinancing_flags(apps, schema_editor):
    loan_model = apps.get_model("loans", "Loan")
    # Loans imported as "ongoing" under the previous model carried an original
    # principal above the financeable principal. Mark them as refinancing loans
    # and seed original terms from the loan's own terms as a best-effort default.
    refinancing = loan_model.objects.exclude(original_principal_minor=F("principal_minor"))
    for loan in refinancing.iterator():
        loan.is_refinancing = True
        loan.original_interest_rate_bps = loan.interest_rate_bps
        loan.original_term_months = loan.term_months
        loan.original_repayment_type = loan.repayment_type
        loan.original_interest_only_months = loan.interest_only_months
        loan.original_loan_start_date = loan.loan_start_date - timedelta(days=30)
        loan.save(
            update_fields=[
                "is_refinancing",
                "original_interest_rate_bps",
                "original_term_months",
                "original_repayment_type",
                "original_interest_only_months",
                "original_loan_start_date",
            ]
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("loans", "0009_loan_start_original_principal_prepub_paid"),
    ]

    operations = [
        migrations.AddField(
            model_name="loan",
            name="is_refinancing",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="loan",
            name="original_interest_rate_bps",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="loan",
            name="original_term_months",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="loan",
            name="original_loan_start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="loan",
            name="original_repayment_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("equal_installments", "Equal installments"),
                    ("bullet_periodic_interest", "Bullet principal with periodic interest"),
                    ("amortizing_principal_interest", "Amortizing principal and interest"),
                    ("interest_only_then_bullet", "Interest-only then bullet"),
                    ("interest_only_then_amortizing", "Interest-only then amortizing"),
                ],
                default="",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="loan",
            name="original_interest_only_months",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_refinancing_flags, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="loan",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(is_refinancing=False)
                    | (
                        models.Q(original_interest_rate_bps__isnull=False)
                        & models.Q(original_term_months__isnull=False)
                        & ~models.Q(original_repayment_type="")
                        & models.Q(original_interest_only_months__isnull=False)
                        & models.Q(original_loan_start_date__isnull=False)
                    )
                ),
                name="loan_refinancing_requires_original_terms",
            ),
        ),
    ]
