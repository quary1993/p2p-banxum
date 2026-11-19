# IP of Webby-Soft SRL.
"""C06 / F16 (2026-11-13, 2026-11-16) and Q15: the main security and the loan-to-value assets.

- Each loan's first security (lowest position) becomes its main security (the summary).
- A security counts in the loan-to-value when it is an asset type with a documented valuation
  (real estate, equipment, inventory, vehicles, pledged securities, cash), has a value and is not
  released. Records of the old "mixed" and "asset backed" types with a value keep counting, so
  their loan-to-value does not change. Receivables, guarantees and other types do not count until
  an admin says so.
- The loan's collateral value becomes the sum of the counted values. A loan whose value changes
  gets an append-only "updated" loan event from the system actor.
- Q15: the "Vehicle" type is added.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import migrations, models

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
COUNTED_TYPES = (
    "real_estate",
    "equipment",
    "inventory",
    "vehicle",
    "securities_pledge",
    "cash_collateral",
    "mixed_collateral",
    "asset_backed",
)


def main_security_and_ltv_assets(apps: Any, schema_editor: Any) -> None:
    loan_model = apps.get_model("loans", "Loan")
    security_model = apps.get_model("loans", "LoanSecurity")
    event_model = apps.get_model("loans", "LoanEvent")
    loan_ids = security_model.objects.values_list("loan_id", flat=True).distinct()
    for loan in loan_model.objects.filter(pk__in=list(loan_ids)).iterator():
        securities = list(security_model.objects.filter(loan_id=loan.pk).order_by("position", "created_at"))
        security_model.objects.filter(pk=securities[0].pk).update(is_main=True)
        total = 0
        for security in securities:
            counts = (
                security.security_type in COUNTED_TYPES
                and int(security.value_minor or 0) > 0
                and security.status != "released"
            )
            if counts:
                security_model.objects.filter(pk=security.pk).update(counts_in_ltv=True)
                total += int(security.value_minor)
        previous = int(loan.collateral_value_minor)
        if total != previous:
            # queryset.update() keeps updated_at: no admin edited the loan.
            loan_model.objects.filter(pk=loan.pk).update(collateral_value_minor=total)
            event_model.objects.create(
                loan_id=loan.pk,
                event_type="updated",
                actor_user_id=SYSTEM_ACTOR_ID,
                actor_account_type="system",
                previous_status=str(loan.status),
                new_status=str(loan.status),
                note="C06: the loan-to-value uses the sum of the distinct valued assets.",
                metadata={
                    "decision": "C06/F16",
                    "source": "migration",
                    "changes": {
                        "collateral_value_minor": {"old": str(previous), "new": str(total)}
                    },
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0025_keep_existing_contract_status_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="loansecurity",
            name="counts_in_ltv",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="loansecurity",
            name="is_main",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="loansecurity",
            name="valuation_amount_minor",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="loansecurity",
            name="valuation_currency",
            field=models.CharField(blank=True, default="", max_length=3),
        ),
        migrations.AddField(
            model_name="loansecurity",
            name="valuation_fx_rate",
            field=models.DecimalField(
                blank=True, decimal_places=8, max_digits=18, null=True
            ),
        ),
        migrations.AddField(
            model_name="loansecurity",
            name="valuation_fx_rate_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="loan",
            name="collateral_type",
            field=models.CharField(
                choices=[
                    ("real_estate", "Real estate"),
                    ("corporate_guarantee", "Corporate guarantee"),
                    ("personal_guarantee", "Personal guarantee"),
                    ("receivables", "Receivables"),
                    ("invoices", "Invoices"),
                    ("equipment", "Equipment"),
                    ("inventory", "Inventory"),
                    ("vehicle", "Vehicle"),
                    ("securities_pledge", "Securities pledge"),
                    ("cash_collateral", "Cash collateral"),
                    ("share_pledge", "Share pledge"),
                    ("asset_backed", "Asset backed"),
                    ("mixed_collateral", "Mixed collateral"),
                    ("unsecured_exception", "Unsecured exception"),
                    ("other", "Other"),
                ],
                default="real_estate",
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="loansecurity",
            name="security_type",
            field=models.CharField(
                choices=[
                    ("real_estate", "Real estate"),
                    ("corporate_guarantee", "Corporate guarantee"),
                    ("personal_guarantee", "Personal guarantee"),
                    ("receivables", "Receivables"),
                    ("invoices", "Invoices"),
                    ("equipment", "Equipment"),
                    ("inventory", "Inventory"),
                    ("vehicle", "Vehicle"),
                    ("securities_pledge", "Securities pledge"),
                    ("cash_collateral", "Cash collateral"),
                    ("share_pledge", "Share pledge"),
                    ("asset_backed", "Asset backed"),
                    ("mixed_collateral", "Mixed collateral"),
                    ("unsecured_exception", "Unsecured exception"),
                    ("other", "Other"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddConstraint(
            model_name="loansecurity",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_main", True)),
                fields=("loan",),
                name="unique_main_loan_security",
            ),
        ),
        migrations.RunPython(main_security_and_ltv_assets, migrations.RunPython.noop),
    ]
