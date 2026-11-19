# IP of Webby-Soft SRL.
from __future__ import annotations

from django.db import migrations


# 18.6: the distribution line table was rebuilt on SQLite (new column), and expenses are
# append-only.
APPEND_ONLY_TABLES = (
    "servicing_investorrepaymentdistributionline",
    "servicing_loanexpense",
)


def install_engine_append_only_guards(apps, schema_editor):
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


def uninstall_engine_append_only_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(
                    f"""
                    DROP TRIGGER IF EXISTS {table}_append_only_guard
                    ON {table};
                    """
                )
        elif vendor == "sqlite":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_update_guard;")
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_delete_guard;")


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0002_append_only_guards"),
        ("servicing", "0016_engine_servicing_18_6"),
    ]

    operations = [
        migrations.RunPython(
            install_engine_append_only_guards,
            uninstall_engine_append_only_guards,
        ),
    ]
