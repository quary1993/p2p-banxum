from __future__ import annotations

from django.db import migrations


TABLE = "secondary_market_secondarymarketlistingevent"


def install_listing_event_append_only_guard(apps, schema_editor):
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


def uninstall_listing_event_append_only_guard(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(f"DROP TRIGGER IF EXISTS {TABLE}_append_only_guard ON {TABLE};")
        elif vendor == "sqlite":
            cursor.execute(f"DROP TRIGGER IF EXISTS {TABLE}_append_only_update_guard;")
            cursor.execute(f"DROP TRIGGER IF EXISTS {TABLE}_append_only_delete_guard;")


class Migration(migrations.Migration):
    dependencies = [
        ("platform_core", "0002_append_only_guards"),
        ("secondary_market", "0006_secondarymarketlistingevent_idempotency_key_and_more"),
    ]

    operations = [
        migrations.RunPython(
            install_listing_event_append_only_guard,
            uninstall_listing_event_append_only_guard,
        ),
    ]
