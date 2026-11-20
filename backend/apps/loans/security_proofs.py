# IP of Webby-Soft SRL.
"""Proof that each security exists before publication (18.10, Q13, U33-DEC-38).

A security verifier (role ``security_verifier`` or its deputy) links one document of the
security per required category and records the verification with name and date. The
verification stays current while the essential fields keep their values; an essential change
needs a new verification. Publication is refused until every security that is not released has a
current, complete verification.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Model

from backend.apps.loans import loan_documents
from backend.apps.loans.models import (
    Loan,
    LoanDocument,
    LoanSecurity,
    LoanSecurityStatus,
    LoanSecurityVerification,
)
from backend.apps.platform_core.domain import declarations as roles
from backend.apps.platform_core.domain import security_proofs as rules
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.time import now_utc
from backend.apps.platform_core.models.files import FileScanStatus
from backend.apps.platform_core.selectors.settings import get_platform_setting_value
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event


class SecurityProofError(ValueError):
    pass


class SecurityProofPermissionError(PermissionError):
    pass


def _configured() -> dict[str, tuple[str, ...]]:
    """The validated proof setting. Audit S7-3: a wrong setting stops verification and
    publication (fail closed) instead of silently using another list."""
    value = get_platform_setting_value(rules.REQUIRED_PROOFS_SETTING, None)
    try:
        return rules.validate_required_proofs_setting(value)
    except rules.ProofConfigurationError as exc:
        raise SecurityProofError(
            f"The required-proof setting is not valid: {exc} Correct it before you continue."
        ) from exc


def _security_values(security: LoanSecurity) -> dict[str, Any]:
    return {name: getattr(security, name) for name in rules.ESSENTIAL_FIELDS}


def _required(security: LoanSecurity) -> tuple[str, ...]:
    return rules.required_proofs(str(security.security_type), _configured())


def _documents(loan_id: Any, document_ids: list[str]) -> dict[str, Any]:
    """The documents with these ids that still exist for the loan: the borrower's documents and
    the documents uploaded to the loan (re-audit: Loan Originator claims have no borrower)."""
    if not document_ids:
        return {}
    loan = Loan.objects.filter(id=loan_id).only("borrower_id").first()
    found: dict[str, Any] = {}
    if loan is not None and loan.borrower_id is not None:
        document_model = apps.get_model("entities", "BorrowerDocument")
        found.update(
            (str(document.id), document)
            for document in document_model.objects.select_related("stored_file").filter(
                id__in=document_ids, borrower_id=loan.borrower_id
            )
        )
    found.update(
        (str(document.id), document)
        for document in LoanDocument.objects.select_related("stored_file").filter(
            id__in=document_ids, loan_id=loan_id
        )
    )
    return found


def _checked(document: Any) -> bool:
    """G-1: a proof counts only when its file passed the check (scan or audited manual check)."""
    return str(document.stored_file.scan_status) == FileScanStatus.CLEAN


def _latest(security: LoanSecurity) -> LoanSecurityVerification | None:
    return cast(
        LoanSecurityVerification | None,
        LoanSecurityVerification.objects.filter(security=security).order_by("-verified_at").first(),
    )


def verification_problem(security: LoanSecurity) -> str:
    """Why the security has no current verification ("" when it has one). Audit S7-3: the
    verification must match the essential fields and the current required-proof list, and
    each proof document must still be linked and exist."""
    latest = _latest(security)
    if latest is None:
        return "no verification of its documents."
    try:
        required = _required(security)
    except SecurityProofError as exc:
        return str(exc)
    if latest.essential_fingerprint != rules.essential_fingerprint(_security_values(security)):
        return "an essential detail changed after the verification; verify it again."
    if not rules.same_required_proofs(latest.required_proofs, required):
        return "the list of required proofs changed after the verification; verify it again."
    proof_ids = [str(latest.proofs.get(key) or "") for key in required]
    linked = {str(item) for item in security.document_ids or []}
    existing = _documents(security.loan_id, proof_ids)
    if any(not item or item not in linked or item not in existing for item in proof_ids):
        return "a proof document is no longer available; verify it again."
    return ""


def current_verification(security: LoanSecurity) -> LoanSecurityVerification | None:
    return None if verification_problem(security) else _latest(security)


def _document_payload(document_id: str, document: Any | None) -> dict[str, Any]:
    """Audit S7-8: safe metadata of a proof document (no file content, no storage path)."""
    if document is None:
        return {
            "id": document_id,
            "title": "",
            "document_type": "",
            "document_date": None,
            "uploaded_at": None,
            "available": False,
            "checked": False,
            "source": "",
        }
    on_loan = isinstance(document, LoanDocument)
    return {
        "id": document_id,
        "title": str(document.display_name or ""),
        "document_type": (
            loan_documents.document_type_label(document.document_type)
            if on_loan
            else str(document.get_document_type_display())
        ),
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "uploaded_at": document.created_at.isoformat() if document.created_at else None,
        "available": True,
        "checked": _checked(document),
        "source": "loan" if on_loan else "borrower",
    }


def security_proof_status(security: LoanSecurity) -> dict[str, Any]:
    configuration_error = ""
    try:
        required = _required(security)
    except SecurityProofError as exc:
        required, configuration_error = (), str(exc)
    problem = verification_problem(security)
    latest = _latest(security)
    current = None if problem else latest
    released = str(security.status) == LoanSecurityStatus.RELEASED
    history = list(
        LoanSecurityVerification.objects.filter(security=security).order_by("-verified_at")
    )
    linked_ids = [str(item) for item in security.document_ids or []]
    proof_ids = {str(value) for item in history for value in (item.proofs or {}).values()}
    documents = _documents(security.loan_id, sorted(set(linked_ids) | proof_ids))
    return {
        "security_id": str(security.id),
        "security_type": str(security.security_type),
        "released": released,
        "required_proofs": [
            {"key": key, "label": rules.PROOF_LABELS.get(key, key)} for key in required
        ],
        "configuration_error": configuration_error,
        "document_ids": linked_ids,
        "documents": [_document_payload(item, documents.get(item)) for item in linked_ids],
        "verified": current is not None,
        "verified_by": current.verifier_name if current else "",
        "verified_at": current.verified_at.isoformat() if current else None,
        "proofs": dict(current.proofs) if current else {},
        "needs_new_verification": latest is not None and current is None,
        "problem": problem if latest is not None else "",
        "history": [
            {
                "verifier_name": item.verifier_name,
                "verified_at": item.verified_at.isoformat(),
                "note": item.note,
                "required_proofs": [str(key) for key in item.required_proofs or []],
                "proofs": [
                    {
                        "key": str(key),
                        "label": rules.PROOF_LABELS.get(str(key), str(key)),
                        "document": _document_payload(str(value), documents.get(str(value))),
                    }
                    for key, value in (item.proofs or {}).items()
                ],
            }
            for item in history
        ],
    }


def loan_security_proofs(loan: Loan) -> list[dict[str, Any]]:
    return [
        security_proof_status(security)
        for security in LoanSecurity.objects.filter(loan=loan).order_by("position", "created_at")
    ]


def publication_problems(loan: Loan) -> list[str]:
    """What still stops publication (empty when every kept security is verified)."""
    problems: list[str] = []
    for security in LoanSecurity.objects.filter(loan=loan).order_by("position", "created_at"):
        if str(security.status) == LoanSecurityStatus.RELEASED:
            continue
        label = security.public_name or security.get_security_type_display()
        problem = verification_problem(security)
        if problem:
            problems.append(f"{label}: {problem}")
    return problems


def assert_securities_verified(loan: Loan) -> None:
    if not getattr(settings, "SECURITY_PROOFS_REQUIRED", True):
        return
    problems = publication_problems(loan)
    if problems:
        raise SecurityProofError(
            "Each security needs all its documents and a named verification before "
            "publication (Q13). " + " ".join(problems)
        )


def proofs_apply_to(loan: Loan) -> bool:
    """Audit S7-4: a loan whose securities were verified (publication with the proof rule, or a
    later verification) keeps needing current verifications for new investments. Loans
    published before 18.10, with no verification at all, keep their earlier rules."""
    if not getattr(settings, "SECURITY_PROOFS_REQUIRED", True):
        return False
    return LoanSecurityVerification.objects.filter(security__loan=loan).exists()


def investment_problem(loan: Loan) -> str:
    """Why new investments in the loan wait for a new security verification ("" when none)."""
    if not proofs_apply_to(loan):
        return ""
    problems = publication_problems(loan)
    if not problems:
        return ""
    return (
        "New investments in this opportunity wait until the securities are verified again "
        "(Q13). " + " ".join(problems)
    )


def assert_investment_allowed(loan: Loan) -> None:
    """Audit S7-4: orders, allocations, quotes and purchases stop while a security of a
    verified loan has no current verification. Call it with the loan row locked."""
    problem = investment_problem(loan)
    if problem:
        raise SecurityProofError(problem)


@dataclass(frozen=True)
class RecordSecurityVerificationCommand:
    actor: Model
    security_id: str
    proofs: dict[str, str] = field(default_factory=dict)
    note: str = ""


def record_security_verification(
    command: RecordSecurityVerificationCommand,
) -> LoanSecurityVerification:
    actor = cast(Any, command.actor)
    if not (is_admin_actor(actor) and roles.has_staff_role(actor, roles.SECURITY_VERIFIER_ROLES)):
        raise SecurityProofPermissionError(
            "Only the security verifier role or its deputy can record a verification."
        )
    with transaction.atomic():
        # Audit S7-4: the loan row first (the order of publication and security edits).
        loan_id = (
            LoanSecurity.objects.filter(id=command.security_id)
            .values_list("loan_id", flat=True)
            .first()
        )
        if loan_id is None:
            raise SecurityProofError("Security does not exist.")
        Loan.objects.select_for_update().filter(id=loan_id).first()
        security = LoanSecurity.objects.select_for_update().filter(id=command.security_id).first()
        if security is None:
            raise SecurityProofError("Security does not exist.")
        if str(security.status) == LoanSecurityStatus.RELEASED:
            raise SecurityProofError("A released security is not verified.")
        required = _required(security)
        proofs = {str(key): str(value).strip() for key, value in command.proofs.items() if value}
        missing = rules.missing_proofs(required, proofs)
        if missing:
            labels = ", ".join(rules.PROOF_LABELS.get(key, key) for key in missing)
            raise SecurityProofError(f"Link a document for each required proof: {labels}.")
        linked = {str(item) for item in security.document_ids or []}
        foreign = [key for key in required if proofs[key] not in linked]
        if foreign:
            raise SecurityProofError(
                "Use documents linked to this security (add them to the security first)."
            )
        existing = _documents(security.loan_id, [proofs[key] for key in required])
        if any(proofs[key] not in existing for key in required):
            raise SecurityProofError("A linked proof document no longer exists.")
        if not all(_checked(existing[proofs[key]]) for key in required):
            raise SecurityProofError(
                "A proof document waits for its check. Confirm the check of each file first."
            )
        verification = LoanSecurityVerification.objects.create(
            security=security,
            verifier_user_id=actor.pk,
            verifier_name=str(actor.full_name),
            verified_at=now_utc(),
            proofs={key: proofs[key] for key in required},
            required_proofs=list(required),
            essential_fingerprint=rules.essential_fingerprint(_security_values(security)),
            note=command.note.strip(),
        )
        record_audit_event(
            AuditCommand(
                actor=actor_ref_for_user(actor),
                action="loan.security_verified",
                target_type="LoanSecurity",
                target_id=str(security.id),
                metadata={"loan_id": str(security.loan_id), "proofs": verification.proofs},
            )
        )
    return cast(LoanSecurityVerification, verification)


@dataclass(frozen=True)
class _OpenedFile:
    document_id: str
    display_name: str
    filename: str
    content_type: str
    content: bytes
    checksum_sha256: str


def open_proof_document(*, actor: Model, security_id: str, document_id: str) -> dict[str, Any]:
    """Audit S7-8: an admin opens a document linked to the security (or used in one of its
    verifications) to check it before the verification. Each opening is audited."""
    if not is_admin_actor(actor):
        raise SecurityProofPermissionError("Only an admin can open security documents.")
    security = LoanSecurity.objects.select_related("loan").filter(id=security_id).first()
    if security is None:
        raise SecurityProofError("Security does not exist.")
    allowed = {str(item) for item in security.document_ids or []}
    for proofs in LoanSecurityVerification.objects.filter(security=security).values_list(
        "proofs", flat=True
    ):
        allowed.update(str(value) for value in (proofs or {}).values())
    if str(document_id) not in allowed:
        raise SecurityProofError("Document not found.")
    loan_document = (
        LoanDocument.objects.select_related("stored_file")
        .filter(id=document_id, loan_id=security.loan_id)
        .first()
    )
    if loan_document is not None:
        try:
            content, filename, content_type, checksum = loan_documents.read_loan_document(
                loan_document
            )
        except (loan_documents.LoanDocumentError, OSError) as exc:
            raise SecurityProofError(str(exc)) from exc
        document_file: Any = _OpenedFile(
            document_id=str(loan_document.id),
            display_name=loan_document.display_name,
            filename=filename,
            content_type=content_type,
            content=content,
            checksum_sha256=checksum,
        )
    else:
        entities: Any = import_module("backend.apps.entities.services")
        borrower_id = security.loan.borrower_id
        try:
            document_file = entities.read_borrower_document_for_staff(
                borrower_id=str(borrower_id) if borrower_id else None,
                document_id=str(document_id),
            )
        except entities.BorrowerValidationError as exc:
            raise SecurityProofError(str(exc)) from exc
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="loan.security_document_opened",
            target_type="BorrowerDocument",
            target_id=document_file.document_id,
            metadata={
                "loan_id": str(security.loan_id),
                "security_id": str(security.id),
                "content_sha256": document_file.checksum_sha256,
            },
        )
    )
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", document_file.filename).strip("-") or "document"
    return {
        "document_id": document_file.document_id,
        "display_name": document_file.display_name,
        "filename": filename[:120],
        "content_type": document_file.content_type,
        "content_encoding": "base64",
        "content": base64.b64encode(document_file.content).decode("ascii"),
        "content_sha256": document_file.checksum_sha256,
    }


SEED_VERIFIER_NAME = "Synthetic seed data (no real check)"


@transaction.atomic
def seed_verified_securities(*, actor: Model, loan_id: str) -> int:
    """QA and demo seeds only (re-audit P-2): give each security of a seeded loan that is not
    released one placeholder document per required proof (uploaded to the loan, marked as
    checked) and a verification named "Synthetic seed data (no real check)", so the always-on
    proof rule lets the seeded catalogue publish. Never call it for a real loan.
    Returns the number of securities verified now (0 when all were already current)."""
    if not is_admin_actor(actor):
        raise SecurityProofPermissionError("Only an admin can seed verifications.")
    Loan.objects.select_for_update().filter(id=loan_id).first()
    verified = 0
    for security in LoanSecurity.objects.select_for_update().filter(loan_id=loan_id):
        if str(security.status) == LoanSecurityStatus.RELEASED or current_verification(security):
            continue
        required = _required(security)
        proofs: dict[str, str] = {}
        for key in required:
            document = loan_documents.upload_loan_document(
                loan_documents.UploadLoanDocumentCommand(
                    actor=actor,
                    loan_id=str(loan_id),
                    filename=f"seed-{key}.pdf",
                    content=f"%PDF-1.4 Synthetic seed placeholder: {key}".encode(),
                    display_name=f"Seed placeholder: {rules.PROOF_LABELS.get(key, key)}",
                    document_type=key,
                )
            )
            loan_documents.confirm_loan_document_check(
                actor=actor,
                document_id=str(document.id),
                note="Synthetic seed data; generated placeholder, no real document.",
            )
            proofs[key] = str(document.id)
        security.document_ids = [
            *[str(item) for item in security.document_ids or []],
            *proofs.values(),
        ]
        security.save(update_fields=["document_ids", "updated_at"])
        security.refresh_from_db()
        LoanSecurityVerification.objects.create(
            security=security,
            verifier_user_id=actor.pk,
            verifier_name=SEED_VERIFIER_NAME,
            verified_at=now_utc(),
            proofs=proofs,
            required_proofs=list(required),
            essential_fingerprint=rules.essential_fingerprint(_security_values(security)),
            note="QA or demo seed: placeholder documents, no real verification.",
        )
        verified += 1
    return verified
