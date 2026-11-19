# IP of Webby-Soft SRL. 18.9: Swiss creditor modes (UID, mode, external debts, SNB rates).

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("entities", "0006_credit_file_structure"),
    ]

    operations = [
        migrations.CreateModel(
            name="SwissCreditorRegime",
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
                ("uid", models.CharField(max_length=16, unique=True)),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            (
                                "sandbox",
                                "Sandbox (total below CHF 500,000, no creditor limit)",
                            ),
                            (
                                "ten_twenty",
                                "10/20 (10 creditors per financing, 20 per borrower)",
                            ),
                        ],
                        default="sandbox",
                        max_length=16,
                    ),
                ),
                ("confirmed_by_admin_id", models.UUIDField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("confirmation_note", models.TextField(blank=True, default="")),
            ],
            options={
                "ordering": ["uid"],
            },
        ),
        migrations.AddField(
            model_name="borrowerentity",
            name="uid",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AlterField(
            model_name="borrowerentityevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("updated", "Updated"),
                    ("kyb_status_changed", "KYB status changed"),
                    ("document_added", "Document added"),
                    ("creditor_mode_changed", "Creditor mode changed"),
                    ("external_debt_recorded", "External debt recorded"),
                    ("external_debt_ended", "External debt ended"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="BorrowerExternalDebt",
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
                ("uid", models.CharField(db_index=True, max_length=16)),
                ("creditor_name", models.CharField(max_length=255)),
                ("creditor_identification", models.CharField(max_length=128)),
                ("creditor_is_bank", models.BooleanField(default=False)),
                ("financing_id", models.CharField(max_length=128)),
                (
                    "identical_terms_group",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                ("principal_minor", models.BigIntegerField()),
                ("currency", models.CharField(max_length=3)),
                ("start_date", models.DateField()),
                ("ended_on", models.DateField(blank=True, null=True)),
                ("declaration_document_id", models.UUIDField(blank=True, null=True)),
                (
                    "declaration_reference",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("checked_by_admin_id", models.UUIDField()),
                ("checked_at", models.DateTimeField()),
                ("notes", models.TextField(blank=True, default="")),
            ],
            options={
                "ordering": ["uid", "start_date", "id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("principal_minor__gt", 0)),
                        name="entities_external_debt_positive_principal",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("ended_on__isnull", True)),
                        fields=("uid", "creditor_identification", "financing_id"),
                        name="entities_external_debt_open_unique",
                    ),
                ],
            },
        ),
    ]
