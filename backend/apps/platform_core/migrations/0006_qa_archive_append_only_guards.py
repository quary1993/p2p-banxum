from django.db import migrations

TABLES = ("platform_core_qadatasetreset", "platform_core_archivedinvestoractivity")


def install(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            if schema_editor.connection.vendor == "postgresql":
                cursor.execute(
                    f"CREATE TRIGGER {table}_append_only_guard BEFORE UPDATE OR DELETE ON {table} "
                    "FOR EACH ROW EXECUTE FUNCTION platform_core_prevent_append_only_mutation()"
                )
            elif schema_editor.connection.vendor == "sqlite":
                for action in ("UPDATE", "DELETE"):
                    cursor.execute(
                        f"CREATE TRIGGER {table}_append_only_{action.lower()}_guard "
                        f"BEFORE {action} ON {table} BEGIN "
                        "SELECT RAISE(ABORT, 'append-only table cannot be changed'); END"
                    )


def uninstall(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            if schema_editor.connection.vendor == "postgresql":
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_guard ON {table}")
            elif schema_editor.connection.vendor == "sqlite":
                for action in ("update", "delete"):
                    cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_{action}_guard")


class Migration(migrations.Migration):
    dependencies = [("platform_core", "0005_qa_dataset_reset_archive")]
    operations = [migrations.RunPython(install, uninstall)]
