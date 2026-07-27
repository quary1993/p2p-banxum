from __future__ import annotations

from django.db import migrations, models


LOAN_EVENT_TABLE = "loans_loanevent"


def install_loan_event_append_only_guard(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"""
                DROP TRIGGER IF EXISTS {LOAN_EVENT_TABLE}_append_only_guard
                ON {LOAN_EVENT_TABLE};
                CREATE TRIGGER {LOAN_EVENT_TABLE}_append_only_guard
                BEFORE UPDATE OR DELETE ON {LOAN_EVENT_TABLE}
                FOR EACH ROW
                EXECUTE FUNCTION platform_core_prevent_append_only_mutation();
                """
            )
        elif vendor == "sqlite":
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {LOAN_EVENT_TABLE}_append_only_update_guard;"
            )
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {LOAN_EVENT_TABLE}_append_only_delete_guard;"
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {LOAN_EVENT_TABLE}_append_only_update_guard
                BEFORE UPDATE ON {LOAN_EVENT_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be updated');
                END;
                """
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {LOAN_EVENT_TABLE}_append_only_delete_guard
                BEFORE DELETE ON {LOAN_EVENT_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'append-only table cannot be deleted');
                END;
                """
            )


def activate_previously_disbursed_loans(apps, schema_editor):
    loan_model = apps.get_model("loans", "Loan")
    bank_operation_model = apps.get_model("ledger", "BankOperation")
    disbursed_loan_ids = list(
        bank_operation_model.objects.filter(
            operation_type="borrower_loan_disbursement",
            linked_object_type="loan",
            status="reconciled",
        ).values_list("linked_object_id", flat=True)
    )
    if disbursed_loan_ids:
        loan_model.objects.filter(
            id__in=disbursed_loan_ids,
            status="funded",
        ).update(status="active")


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0009_additive_payout_instructions"),
        ("loans", "0010_loan_refinancing_original_terms"),
    ]

    operations = [
        migrations.AlterField(
            model_name="loan",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("published", "Published"),
                    ("funded", "Funded"),
                    ("active", "Active"),
                    ("late", "Late"),
                    ("defaulted", "Defaulted"),
                    ("repaid", "Repaid"),
                    ("written_off", "Written off"),
                    ("cancelled", "Cancelled"),
                ],
                default="draft",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="loanevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("updated", "Updated"),
                    ("published", "Published"),
                    ("funding_closed", "Funding closed"),
                    ("disbursed", "Disbursed"),
                    ("funding_cancelled", "Funding cancelled"),
                    ("schedule_generated", "Schedule generated"),
                    ("servicing_status_changed", "Servicing status changed"),
                    ("recovery_recorded", "Recovery recorded"),
                    ("write_off_recorded", "Write-off recorded"),
                ],
                max_length=32,
            ),
        ),
        migrations.RunPython(
            install_loan_event_append_only_guard,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            activate_previously_disbursed_loans,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
