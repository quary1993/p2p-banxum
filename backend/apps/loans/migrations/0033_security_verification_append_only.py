# IP of Webby-Soft SRL. Audit S7-9: security verifications are append-only in the database too.

from django.db import migrations

VERIFICATION_TABLE = "loans_loansecurityverification"


def install_verification_append_only_guard(apps, schema_editor):
    """The proof history cannot be changed or removed by direct SQL (same guard as declarations)."""
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"""
                DROP TRIGGER IF EXISTS {VERIFICATION_TABLE}_append_only_guard
                ON {VERIFICATION_TABLE};
                CREATE TRIGGER {VERIFICATION_TABLE}_append_only_guard
                BEFORE UPDATE OR DELETE ON {VERIFICATION_TABLE}
                FOR EACH ROW
                EXECUTE FUNCTION platform_core_prevent_append_only_mutation();
                """
            )
        elif vendor == "sqlite":
            for kind in ("UPDATE", "DELETE"):
                name = f"{VERIFICATION_TABLE}_append_only_{kind.lower()}_guard"
                cursor.execute(f"DROP TRIGGER IF EXISTS {name};")
                cursor.execute(
                    f"""
                    CREATE TRIGGER {name}
                    BEFORE {kind} ON {VERIFICATION_TABLE}
                    BEGIN
                        SELECT RAISE(ABORT, 'append-only table cannot be changed');
                    END;
                    """
                )


def uninstall_verification_append_only_guard(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {VERIFICATION_TABLE}_append_only_guard "
                f"ON {VERIFICATION_TABLE};"
            )
        elif vendor == "sqlite":
            for kind in ("update", "delete"):
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS {VERIFICATION_TABLE}_append_only_{kind}_guard;"
                )


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0032_new_loans_use_the_engine"),
        ("platform_core", "0002_append_only_guards"),
    ]

    operations = [
        migrations.RunPython(
            install_verification_append_only_guard,
            uninstall_verification_append_only_guard,
        ),
    ]
