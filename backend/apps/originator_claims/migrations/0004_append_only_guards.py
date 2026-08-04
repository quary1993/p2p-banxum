from __future__ import annotations

from django.db import migrations


APPEND_ONLY_TABLES = (
    "originator_claims_originatorloanimport",
    "originator_claims_originatorloanpaymentrow",
    "originator_claims_originatorloanschedulerow",
    "originator_claims_originatorclaimquote",
    "originator_claims_originatorclaimpurchase",
    "originator_claims_originatorclaimentitlement",
    "originator_claims_originatorsettlement",
    "originator_claims_originatorsettlementpurchase",
    "originator_claims_originatorborrowerrepayment",
    "originator_claims_investororiginatorrepaymentdistributionline",
    "originator_claims_originatorsettlementrepayment",
    "originator_claims_originatorclaimevent",
)


def install_append_only_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
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
        elif vendor == "sqlite":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_update_guard;")
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_delete_guard;")


class Migration(migrations.Migration):
    dependencies = [
        ("originator_claims", "0003_investororiginatorrepaymentdistributionline_and_more"),
        ("platform_core", "0002_append_only_guards"),
    ]

    operations = [
        migrations.RunPython(install_append_only_guards, uninstall_append_only_guards),
    ]
