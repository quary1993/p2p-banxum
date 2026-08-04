from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


PURCHASE_TABLE = "originator_claims_originatorclaimpurchase"


def require_existing_acceptance(apps, schema_editor) -> None:
    purchase_model = apps.get_model("originator_claims", "OriginatorClaimPurchase")
    if purchase_model.objects.filter(document_acceptance_id__isnull=True).exists():
        raise RuntimeError(
            "Originator claim purchases without immutable document acceptance evidence "
            "must be remediated before this migration can run."
        )


def reinstall_purchase_append_only_guard(apps, schema_editor) -> None:
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"""
                DROP TRIGGER IF EXISTS {PURCHASE_TABLE}_append_only_guard ON {PURCHASE_TABLE};
                CREATE TRIGGER {PURCHASE_TABLE}_append_only_guard
                BEFORE UPDATE OR DELETE ON {PURCHASE_TABLE}
                FOR EACH ROW
                EXECUTE FUNCTION platform_core_prevent_append_only_mutation();
                """
            )
        elif vendor == "sqlite":
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {PURCHASE_TABLE}_append_only_update_guard;"
            )
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {PURCHASE_TABLE}_append_only_delete_guard;"
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {PURCHASE_TABLE}_append_only_update_guard
                BEFORE UPDATE ON {PURCHASE_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be updated');
                END;
                """
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {PURCHASE_TABLE}_append_only_delete_guard
                BEFORE DELETE ON {PURCHASE_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be deleted');
                END;
                """
            )


class Migration(migrations.Migration):
    dependencies = [
        ("originator_claims", "0005_originatorloanprofile_held_at_and_more"),
    ]

    operations = [
        migrations.RunPython(require_existing_acceptance, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="originatorclaimpurchase",
            name="document_acceptance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="documents.documentacceptanceevidence",
            ),
        ),
        migrations.RunPython(
            reinstall_purchase_append_only_guard,
            reinstall_purchase_append_only_guard,
        ),
    ]
