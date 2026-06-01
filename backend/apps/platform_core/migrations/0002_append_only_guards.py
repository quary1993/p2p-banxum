from __future__ import annotations

from django.db import migrations


APPEND_ONLY_TABLES = (
    "platform_core_auditevent",
    "platform_core_domainevent",
    "platform_core_platformsettingversion",
)


def install_append_only_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                """
                CREATE OR REPLACE FUNCTION platform_core_prevent_append_only_mutation()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'append-only table % cannot be updated or deleted', TG_TABLE_NAME;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
            for table in APPEND_ONLY_TABLES:
                cursor.execute(
                    f"""
                    DROP TRIGGER IF EXISTS {table}_append_only_guard ON {table};
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


def uninstall_append_only_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_guard ON {table};")
            cursor.execute("DROP FUNCTION IF EXISTS platform_core_prevent_append_only_mutation();")
        elif vendor == "sqlite":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_update_guard;")
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_delete_guard;")


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(install_append_only_guards, uninstall_append_only_guards),
    ]
