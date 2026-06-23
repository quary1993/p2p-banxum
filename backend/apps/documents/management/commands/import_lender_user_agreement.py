from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser

from backend.apps.documents.legal_import import (
    LegalTemplateImportError,
    extract_lender_user_agreement_template,
)
from backend.apps.documents.models import DocumentCategory
from backend.apps.documents.services import (
    CreateDocumentTemplateVersionCommand,
    DocumentValidationError,
    create_document_template_version,
)


class Command(BaseCommand):
    help = (
        "Import the Garanta/BANXUM lender user agreement DOCX as the current "
        "registration document template."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("docx_path")
        parser.add_argument("--effective-date", required=True)
        parser.add_argument("--superadmin-email", required=True)
        parser.add_argument("--template-key", default="default")
        parser.add_argument("--language", default="en")
        parser.add_argument("--legal-review-reference", default="")
        parser.add_argument("--publish", action="store_true")
        parser.add_argument(
            "--allow-unresolved-placeholders",
            action="store_true",
            help=(
                "Allow unresolved [to confirm]/[to complete] placeholders. "
                "Do not use for production publication."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user_model = get_user_model()
        superadmin = user_model.objects.filter(
            email=str(options["superadmin_email"]).strip().lower()
        ).first()
        if superadmin is None:
            raise CommandError("Superadmin email does not match an existing account.")

        try:
            imported = extract_lender_user_agreement_template(
                docx_path=str(options["docx_path"]),
                effective_date=str(options["effective_date"]),
            )
        except LegalTemplateImportError as exc:
            raise CommandError(str(exc)) from exc

        if imported.unresolved_placeholders and not options["allow_unresolved_placeholders"]:
            unresolved = ", ".join(imported.unresolved_placeholders)
            raise CommandError(
                "Agreement still contains unresolved legal/commercial placeholders: "
                f"{unresolved}. Complete the DOCX or rerun with "
                "--allow-unresolved-placeholders for non-production testing only."
            )

        try:
            version = create_document_template_version(
                CreateDocumentTemplateVersionCommand(
                    actor=superadmin,
                    category=DocumentCategory.REGISTRATION,
                    template_key=str(options["template_key"]),
                    language=str(options["language"]),
                    name="Garanta Lender User Agreement",
                    description=(
                        "Registration-time lender user agreement imported from the "
                        "Garanta aligned final draft DOCX."
                    ),
                    title=imported.title,
                    body=imported.body,
                    checkbox_labels=[imported.checkbox_label],
                    publish_now=bool(options["publish"]),
                    legal_review_reference=str(options["legal_review_reference"]),
                    metadata={
                        "source": "docx_import",
                        "source_docx_sha256": imported.source_docx_sha256,
                        "body_sha256": imported.body_sha256,
                        "source_version_label": imported.version_label,
                        "effective_date": imported.effective_date,
                        "skipped_instruction_text": imported.skipped_instruction_text,
                        "unresolved_placeholders": list(imported.unresolved_placeholders),
                    },
                    note="Imported lender user agreement DOCX.",
                )
            )
        except DocumentValidationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Imported lender user agreement "
                f"template_version_id={version.id} status={version.status} "
                f"content_hash={version.content_hash}"
            )
        )
