from __future__ import annotations

from django.db import migrations, models


LISTING_EVENT_TABLE = "secondary_market_secondarymarketlistingevent"


def install_listing_event_append_only_guard(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"""
                DROP TRIGGER IF EXISTS {LISTING_EVENT_TABLE}_append_only_guard
                ON {LISTING_EVENT_TABLE};
                CREATE TRIGGER {LISTING_EVENT_TABLE}_append_only_guard
                BEFORE UPDATE OR DELETE ON {LISTING_EVENT_TABLE}
                FOR EACH ROW
                EXECUTE FUNCTION platform_core_prevent_append_only_mutation();
                """
            )
        elif vendor == "sqlite":
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {LISTING_EVENT_TABLE}_append_only_update_guard;"
            )
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {LISTING_EVENT_TABLE}_append_only_delete_guard;"
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {LISTING_EVENT_TABLE}_append_only_update_guard
                BEFORE UPDATE ON {LISTING_EVENT_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be updated');
                END;
                """
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {LISTING_EVENT_TABLE}_append_only_delete_guard
                BEFORE DELETE ON {LISTING_EVENT_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be deleted');
                END;
                """
            )


def align_open_listing_snapshots_with_active_loans(apps, schema_editor):
    listing_model = apps.get_model("secondary_market", "SecondaryMarketListing")
    listing_model.objects.filter(
        status__in=["active", "approval_requested"],
        loan__status="active",
        loan_status_at_listing="funded",
    ).update(loan_status_at_listing="active")


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0011_active_servicing_status"),
        ("secondary_market", "0007_reinstall_listing_event_append_only_guard"),
    ]

    operations = [
        migrations.AlterField(
            model_name="secondarymarketlistingevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("edited", "Edited"),
                    ("repriced", "Repriced after loan change"),
                    ("auto_cancelled", "Automatically cancelled"),
                    ("auto_published", "Auto published"),
                    ("approval_requested", "Approval requested"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("removed", "Removed"),
                    ("cancelled", "Cancelled"),
                    ("sold", "Sold"),
                ],
                max_length=64,
            ),
        ),
        migrations.RunPython(
            install_listing_event_append_only_guard,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            align_open_listing_snapshots_with_active_loans,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
