from __future__ import annotations

import django.db.models.deletion
import uuid
from django.db import migrations, models


APPEND_ONLY_TABLE = "marketplace_primary_primaryloancancellation"


def install_primary_cancellation_append_only_guards(apps, schema_editor):
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


def uninstall_primary_cancellation_append_only_guards(apps, schema_editor):
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
        ("loans", "0008_alter_loanevent_event_type"),
        ("marketplace_primary", "0004_primary_loan_close_append_only_guard"),
        ("platform_core", "0002_append_only_guards"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrimaryLoanCancellation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("released_order_count", models.PositiveIntegerField(default=0)),
                (
                    "closed_not_invested_order_count",
                    models.PositiveIntegerField(default=0),
                ),
                ("released_principal_minor", models.BigIntegerField(default=0)),
                ("created_by_admin_id", models.UUIDField()),
                ("cancelled_at", models.DateTimeField()),
                ("reason", models.TextField()),
                ("investor_message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                (
                    "currency",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="primary_market_cancellations",
                        to="platform_core.currency",
                    ),
                ),
                (
                    "loan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="primary_market_cancellations",
                        to="loans.loan",
                    ),
                ),
            ],
            options={
                "ordering": ["-cancelled_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["loan", "cancelled_at"],
                        name="marketplace_loan_id_0ddc6a_idx",
                    ),
                    models.Index(
                        fields=["currency", "cancelled_at"],
                        name="marketplace_currenc_07e574_idx",
                    ),
                    models.Index(
                        fields=["created_by_admin_id", "cancelled_at"],
                        name="marketplace_created_291382_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("released_principal_minor__gte", 0)),
                        name="primary_cancel_released_principal_nonnegative",
                    ),
                    models.UniqueConstraint(
                        fields=("loan",),
                        name="unique_primary_cancellation_per_loan",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            install_primary_cancellation_append_only_guards,
            uninstall_primary_cancellation_append_only_guards,
        ),
    ]
