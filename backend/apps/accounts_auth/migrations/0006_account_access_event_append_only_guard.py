from __future__ import annotations

from django.db import migrations


APPEND_ONLY_TABLE = "accounts_auth_accountaccessevent"


def install_account_access_append_only_guard(apps, schema_editor):
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
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_update_guard;"
            )
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_delete_guard;"
            )
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


def uninstall_account_access_append_only_guard(apps, schema_editor):
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
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_update_guard;"
            )
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {APPEND_ONLY_TABLE}_append_only_delete_guard;"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0002_append_only_guards"),
        ("accounts_auth", "0005_accountaccessevent"),
    ]

    operations = [
        migrations.RunPython(
            install_account_access_append_only_guard,
            uninstall_account_access_append_only_guard,
        ),
    ]
