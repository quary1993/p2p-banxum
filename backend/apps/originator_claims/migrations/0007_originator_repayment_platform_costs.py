from __future__ import annotations

from django.db import migrations, models
from django.db.models import F, Q


TABLE = "originator_claims_originatorborrowerrepayment"


def reinstall_append_only_guard(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"""
                DROP TRIGGER IF EXISTS {TABLE}_append_only_guard ON {TABLE};
                CREATE TRIGGER {TABLE}_append_only_guard
                BEFORE UPDATE OR DELETE ON {TABLE}
                FOR EACH ROW
                EXECUTE FUNCTION platform_core_prevent_append_only_mutation();
                """
            )
        elif vendor == "sqlite":
            cursor.execute(f"DROP TRIGGER IF EXISTS {TABLE}_append_only_update_guard;")
            cursor.execute(f"DROP TRIGGER IF EXISTS {TABLE}_append_only_delete_guard;")
            cursor.execute(
                f"""
                CREATE TRIGGER {TABLE}_append_only_update_guard
                BEFORE UPDATE ON {TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be updated');
                END;
                """
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {TABLE}_append_only_delete_guard
                BEFORE DELETE ON {TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be deleted');
                END;
                """
            )


class Migration(migrations.Migration):
    dependencies = [("originator_claims", "0006_require_purchase_document_acceptance")]

    operations = [
        migrations.RemoveConstraint(
            model_name="originatorborrowerrepayment",
            name="originator_repayment_distribution_conserved",
        ),
        migrations.RemoveConstraint(
            model_name="originatorborrowerrepayment",
            name="originator_repayment_amounts_nonnegative",
        ),
        migrations.AddField(
            model_name="originatorborrowerrepayment",
            name="platform_costs_minor",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="originatorborrowerrepayment",
            constraint=models.CheckConstraint(
                condition=(
                    Q(principal_minor__gte=0)
                    & Q(interest_minor__gte=0)
                    & Q(penalty_minor__gte=0)
                    & Q(fee_minor__gte=0)
                    & Q(amount_minor__gt=0)
                    & Q(investor_distributed_minor__gte=0)
                    & Q(originator_payable_minor__gte=0)
                    & Q(platform_costs_minor__gte=0)
                    & Q(principal_before_minor__gt=0)
                    & Q(principal_after_minor__gte=0)
                    & Q(originator_principal_before_minor__gte=0)
                    & Q(originator_principal_after_minor__gte=0)
                ),
                name="originator_repayment_amounts_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="originatorborrowerrepayment",
            constraint=models.CheckConstraint(
                condition=Q(
                    amount_minor=(
                        F("investor_distributed_minor")
                        + F("originator_payable_minor")
                        + F("platform_costs_minor")
                    )
                ),
                name="originator_repayment_distribution_conserved",
            ),
        ),
        migrations.RunPython(reinstall_append_only_guard, reinstall_append_only_guard),
    ]
