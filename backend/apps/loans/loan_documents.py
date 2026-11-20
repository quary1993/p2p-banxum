"""IP of Webby-Soft SRL. Documents uploaded to a loan as proof for its securities.

Re-audit (owner's choice of 2026-11-20): a Loan Originator claim has no borrower record, so the
proofs of its securities are uploaded to the loan; a Direct loan can use these documents and
the borrower's documents. The files are internal (never shown to investors).

Security review G-1 (no malware scanner yet): an upload is stored as "waiting for check"; it
opens and counts as proof only after an admin confirmed, with a note, that the file was checked
(audited). Only PDF, PNG and JPEG files up to 20 MB are accepted, recognised by their content.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Model

from backend.apps.loans.models import Loan, LoanDocument
from backend.apps.platform_core.domain import security_proofs as rules
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.time import now_utc
from backend.apps.platform_core.models.files import FileAccessScope, FileScanStatus
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.files import (
    RegisterStoredFileCommand,
    mark_file_scan_clean,
    register_stored_file,
)

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
OTHER_DOCUMENT_TYPE = "other"
_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
)


class LoanDocumentError(ValueError):
    pass


class LoanDocumentPermissionError(PermissionError):
    pass


def document_type_label(value: str) -> str:
    return rules.PROOF_LABELS.get(value, "Other document")


def document_type_choices() -> list[tuple[str, str]]:
    return [*rules.PROOF_LABELS.items(), (OTHER_DOCUMENT_TYPE, "Other document")]


def _require_admin(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise LoanDocumentPermissionError("Only an admin can manage loan documents.")


def _file_kind(content: bytes) -> tuple[str, str]:
    for signature, content_type, extension in _SIGNATURES:
        if content.startswith(signature):
            return content_type, extension
    raise LoanDocumentError("Upload a PDF, PNG or JPEG file.")


@dataclass(frozen=True, slots=True)
class UploadLoanDocumentCommand:
    actor: Model
    loan_id: str
    filename: str
    content: bytes
    display_name: str
    document_type: str = OTHER_DOCUMENT_TYPE
    document_date: date | None = None


@transaction.atomic
def upload_loan_document(command: UploadLoanDocumentCommand) -> LoanDocument:
    _require_admin(command.actor)
    loan = Loan.objects.select_for_update().filter(id=command.loan_id).first()
    if loan is None:
        raise LoanDocumentError("Loan does not exist.")
    if not command.content:
        raise LoanDocumentError("The file is empty.")
    if len(command.content) > MAX_DOCUMENT_BYTES:
        raise LoanDocumentError("A document can have at most 20 MB.")
    content_type, extension = _file_kind(command.content)
    display_name = command.display_name.strip()[:200]
    if not display_name:
        raise LoanDocumentError("Give the document a name.")
    document_type = command.document_type.strip() or OTHER_DOCUMENT_TYPE
    if document_type not in dict(document_type_choices()):
        raise LoanDocumentError("Unknown document type.")
    original = re.sub(r"[^A-Za-z0-9._-]+", "-", command.filename).strip("-")[:120]
    key = default_storage.save(
        f"loans/{loan.pk}/documents/{uuid.uuid4().hex}{extension}", ContentFile(command.content)
    )
    actor_ref = actor_ref_for_user(command.actor)
    stored = register_stored_file(
        RegisterStoredFileCommand(
            storage_key=key,
            original_filename=original or f"document{extension}",
            content_type=content_type,
            size_bytes=len(command.content),
            checksum_sha256=hashlib.sha256(command.content).hexdigest(),
            created_by=actor_ref,
            owner=ActorRef(actor_type="loan", actor_id=str(loan.pk)),
            access_scope=FileAccessScope.INTERNAL,
        )
    )
    document = LoanDocument.objects.create(
        loan=loan,
        stored_file=stored,
        document_type=document_type,
        display_name=display_name,
        document_date=command.document_date,
        created_by_admin_id=command.actor.pk,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.document_uploaded",
            target_type="LoanDocument",
            target_id=str(document.id),
            metadata={
                "loan_id": str(loan.pk),
                "document_type": document_type,
                "content_sha256": stored.checksum_sha256,
                "size_bytes": stored.size_bytes,
            },
        )
    )
    return document


@transaction.atomic
def confirm_loan_document_check(
    *, actor: Model, document_id: str, note: str, checksum_sha256: str
) -> LoanDocument:
    """G-1: the admin confirms that the file was checked (scanned) before it can be used.

    The platform does not serve a file before its check, so the admin scans the original file
    outside the platform and gives its SHA-256. The check counts only when that value matches
    the stored copy (re-audit 2: proof that the stored copy is the scanned file)."""
    _require_admin(actor)
    document = (
        LoanDocument.objects.select_for_update()
        .select_related("stored_file")
        .filter(id=document_id)
        .first()
    )
    if document is None:
        raise LoanDocumentError("Document not found.")
    note = note.strip()[:500]
    if len(note) < 5:
        raise LoanDocumentError("Say how the file was checked (at least 5 characters).")
    if document.stored_file.scan_status == FileScanStatus.CLEAN:
        return document
    given = "".join(str(checksum_sha256 or "").split()).lower()
    if not given or given != str(document.stored_file.checksum_sha256).lower():
        raise LoanDocumentError(
            "The SHA-256 does not match the uploaded file. Scan the file that you uploaded and "
            "enter its SHA-256."
        )
    mark_file_scan_clean(document.stored_file)
    document.scan_confirmed_by_admin_id = actor.pk
    document.scan_confirmed_at = now_utc()
    document.scan_note = note
    document.save(
        update_fields=["scan_confirmed_by_admin_id", "scan_confirmed_at", "scan_note", "updated_at"]
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="loan.document_check_confirmed",
            target_type="LoanDocument",
            target_id=str(document.id),
            metadata={
                "loan_id": str(document.loan_id),
                "note": note,
                "content_sha256": str(document.stored_file.checksum_sha256),
            },
        )
    )
    return document


def is_checked(document: LoanDocument) -> bool:
    return str(document.stored_file.scan_status) == FileScanStatus.CLEAN


def document_payload(document: LoanDocument) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "display_name": document.display_name,
        "document_type": document.document_type,
        "document_type_label": document_type_label(document.document_type),
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "uploaded_at": document.created_at.isoformat(),
        "checked": is_checked(document),
        "checked_at": document.scan_confirmed_at.isoformat()
        if document.scan_confirmed_at
        else None,
        "check_note": document.scan_note,
        "size_bytes": int(document.stored_file.size_bytes),
        "checksum_sha256": str(document.stored_file.checksum_sha256),
    }


def list_loan_documents(*, actor: Model, loan_id: str) -> list[dict[str, Any]]:
    _require_admin(actor)
    return [
        document_payload(document)
        for document in LoanDocument.objects.select_related("stored_file").filter(loan_id=loan_id)
    ]


def read_loan_document(document: LoanDocument) -> tuple[bytes, str, str, str]:
    """(content, filename, content type, checksum) of a checked document."""
    if not is_checked(document):
        raise LoanDocumentError("This document waits for its check.")
    stored = document.stored_file
    with default_storage.open(stored.storage_key, "rb") as handle:
        content = cast(bytes, handle.read())
    checksum = hashlib.sha256(content).hexdigest()
    if stored.checksum_sha256 and checksum != stored.checksum_sha256:
        raise LoanDocumentError("This document is not available at the moment.")
    return content, str(stored.original_filename), str(stored.content_type), checksum
