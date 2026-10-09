"""Loan notes for Loan Originator loans have no BANXUM borrower (audit A-29).

SQLite rebuilds the table to drop NOT NULL, which removes its append-only
triggers, so the guard is installed again afterwards (idempotent on PostgreSQL).
"""

from __future__ import annotations

from django.db import migrations, models

APPEND_ONLY_TABLES = ("servicing_loanrisknote",)


def install_risk_note_append_only_guard(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(
                    f"""
                    DROP TRIGGER IF EXISTS {table}_append_only_guard
                    ON {table};
                    CREATE TRIGGER {table}_append_only_guard
                    BEFORE UPDATE OR DELETE ON {table}
                    FOR EACH ROW
                    EXECUTE FUNCTION platform_core_prevent_append_only_mutation();
                    """
                )
        elif vendor == "sqlite":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_update_guard;")
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_delete_guard;")
                cursor.execute(
                    f"""
                    CREATE TRIGGER {table}_append_only_update_guard
                    BEFORE UPDATE ON {table}
                    BEGIN
                        SELECT RAISE(ABORT, 'append-only table cannot be updated');
                    END;
                    """
                )
                cursor.execute(
                    f"""
                    CREATE TRIGGER {table}_append_only_delete_guard
                    BEFORE DELETE ON {table}
                    BEGIN
                        SELECT RAISE(ABORT, 'append-only table cannot be deleted');
                    END;
                    """
                )


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0002_append_only_guards"),
        ("servicing", "0012_reinstall_writeoff_append_only_guard"),
    ]

    operations = [
        migrations.AlterField(
            model_name="loanrisknote",
            name="borrower_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.RunPython(
            install_risk_note_append_only_guard,
            migrations.RunPython.noop,
        ),
    ]
