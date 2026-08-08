from django.db import migrations, models


APPEND_ONLY_TABLE = "marketplace_primary_primaryinvestmentorderbatch"


def install_batch_append_only_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"""
                DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_guard
                ON {APPEND_ONLY_TABLE};
                CREATE TRIGGER {APPEND_ONLY_TABLE}_append_only_guard
                BEFORE UPDATE OR DELETE ON {APPEND_ONLY_TABLE}
                FOR EACH ROW
                EXECUTE FUNCTION platform_core_prevent_append_only_mutation();
                """
            )
        elif vendor == "sqlite":
            cursor.execute(f"DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_update_guard;")
            cursor.execute(f"DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_delete_guard;")
            cursor.execute(
                f"""
                CREATE TRIGGER {APPEND_ONLY_TABLE}_append_only_update_guard
                BEFORE UPDATE ON {APPEND_ONLY_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be updated');
                END;
                """
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {APPEND_ONLY_TABLE}_append_only_delete_guard
                BEFORE DELETE ON {APPEND_ONLY_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be deleted');
                END;
                """
            )


def uninstall_batch_append_only_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"""
                DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_guard
                ON {APPEND_ONLY_TABLE};
                """
            )
        elif vendor == "sqlite":
            cursor.execute(f"DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_update_guard;")
            cursor.execute(f"DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_delete_guard;")


class Migration(migrations.Migration):
    dependencies = [
        (
            "marketplace_primary",
            "0007_remove_primaryinvestmentorderbatch_primary_order_batch_total_positive_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            uninstall_batch_append_only_guards,
            install_batch_append_only_guards,
        ),
        migrations.RemoveConstraint(
            model_name="primaryinvestmentorderbatch",
            name="primary_order_batch_count_positive",
        ),
        migrations.AlterField(
            model_name="primaryinvestmentorderbatch",
            name="order_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="primaryinvestmentorderbatch",
            name="originator_purchase_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="primaryinvestmentorderbatch",
            name="originator_purchase_ids",
            field=models.JSONField(default=list),
        ),
        migrations.AddConstraint(
            model_name="primaryinvestmentorderbatch",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("order_count__gt", 0))
                    | models.Q(("originator_purchase_count__gt", 0))
                ),
                name="primary_order_batch_has_investments",
            ),
        ),
        migrations.RunPython(
            install_batch_append_only_guards,
            uninstall_batch_append_only_guards,
        ),
    ]
