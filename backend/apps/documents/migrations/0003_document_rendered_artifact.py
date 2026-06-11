from __future__ import annotations

import django.db.models.deletion
import uuid
from django.db import migrations, models


APPEND_ONLY_TABLES = (
    "documents_documenttemplateversion",
    "documents_documentacceptanceevidence",
    "documents_documentevent",
    "documents_documentrenderedartifact",
)


def install_document_append_only_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(
                    f"""
                    DROP TRIGGER IF EXISTS {table}_append_only_guard
                    ON {table};
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


def uninstall_document_append_only_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(
                    f"""
                    DROP TRIGGER IF EXISTS {table}_append_only_guard
                    ON {table};
                    """
                )
        elif vendor == "sqlite":
            for table in APPEND_ONLY_TABLES:
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_update_guard;")
                cursor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only_delete_guard;")


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0002_document_append_only_guards"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentRenderedArtifact",
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
                ("user_id", models.UUIDField()),
                ("actor_user_id", models.UUIDField()),
                ("actor_account_type", models.CharField(max_length=64)),
                (
                    "output_format",
                    models.CharField(
                        choices=[("pdf", "PDF"), ("csv", "CSV")],
                        max_length=16,
                    ),
                ),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("investor_download", "Investor download"),
                            ("admin_download", "Admin download"),
                            ("email_delivery", "Email delivery"),
                            ("evidence_export", "Evidence export"),
                        ],
                        default="investor_download",
                        max_length=64,
                    ),
                ),
                ("content_type", models.CharField(max_length=128)),
                ("content_encoding", models.CharField(max_length=32)),
                ("filename", models.CharField(max_length=255)),
                ("content_sha256", models.CharField(max_length=64)),
                ("manifest", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("rendered_at", models.DateTimeField(auto_now_add=True)),
                (
                    "acceptance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rendered_artifacts",
                        to="documents.documentacceptanceevidence",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rendered_artifacts",
                        to="documents.documenttemplate",
                    ),
                ),
                (
                    "template_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rendered_artifacts",
                        to="documents.documenttemplateversion",
                    ),
                ),
            ],
            options={
                "ordering": ["-rendered_at", "-id"],
            },
        ),
        migrations.AlterField(
            model_name="documentevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("template_created", "Template created"),
                    ("version_created", "Version created"),
                    ("version_published", "Version published"),
                    ("accepted", "Accepted"),
                    ("artifact_rendered", "Artifact rendered"),
                ],
                max_length=64,
            ),
        ),
        migrations.AddIndex(
            model_name="documentrenderedartifact",
            index=models.Index(
                fields=["acceptance", "rendered_at"],
                name="documents_d_accept_2469d9_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="documentrenderedartifact",
            index=models.Index(
                fields=["user_id", "rendered_at"],
                name="documents_d_user_id_4467dd_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="documentrenderedartifact",
            index=models.Index(
                fields=["content_sha256"],
                name="documents_d_content_413215_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="documentrenderedartifact",
            index=models.Index(
                fields=["purpose", "rendered_at"],
                name="documents_d_purpose_82a1f2_idx",
            ),
        ),
        migrations.RunPython(
            install_document_append_only_guards,
            uninstall_document_append_only_guards,
        ),
    ]
