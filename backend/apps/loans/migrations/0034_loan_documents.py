# IP of Webby-Soft SRL. Re-audit: documents uploaded to a loan as proof for its securities.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0033_security_verification_append_only"),
        ("platform_core", "0013_calendar_revision"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoanDocument",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("document_type", models.CharField(max_length=64)),
                ("display_name", models.CharField(max_length=200)),
                ("document_date", models.DateField(blank=True, null=True)),
                ("created_by_admin_id", models.UUIDField()),
                ("scan_confirmed_by_admin_id", models.UUIDField(blank=True, null=True)),
                ("scan_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("scan_note", models.CharField(blank=True, max_length=500)),
                (
                    "loan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="documents",
                        to="loans.loan",
                    ),
                ),
                (
                    "stored_file",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="loan_documents",
                        to="platform_core.storedfile",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
    ]
