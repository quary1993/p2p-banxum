# IP of Webby-Soft SRL.
"""Proof that each security exists before publication (18.10, Q13, U33-DEC-38).

A security verifier (role ``security_verifier`` or its deputy) links one document of the
security per required category and records the verification with name and date. The
verification stays current while the essential fields keep their values; an essential change
needs a new verification. Publication is refused until every security that is not released has a
current, complete verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from django.conf import settings
from django.db import transaction
from django.db.models import Model

from backend.apps.loans.models import (
    Loan,
    LoanSecurity,
    LoanSecurityStatus,
    LoanSecurityVerification,
)
from backend.apps.platform_core.domain import declarations as roles
from backend.apps.platform_core.domain import security_proofs as rules
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.time import now_utc
from backend.apps.platform_core.selectors.settings import get_platform_setting_value
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event


class SecurityProofError(ValueError):
    pass


class SecurityProofPermissionError(PermissionError):
    pass


def _configured() -> dict[str, Any]:
    value = get_platform_setting_value(rules.REQUIRED_PROOFS_SETTING, None)
    return value if isinstance(value, dict) else {}


def _security_values(security: LoanSecurity) -> dict[str, Any]:
    return {name: getattr(security, name) for name in rules.ESSENTIAL_FIELDS}


def current_verification(security: LoanSecurity) -> LoanSecurityVerification | None:
    latest = cast(
        LoanSecurityVerification | None,
        LoanSecurityVerification.objects.filter(security=security).order_by("-verified_at").first(),
    )
    if latest is None:
        return None
    fingerprint = rules.essential_fingerprint(_security_values(security))
    return latest if latest.essential_fingerprint == fingerprint else None


def security_proof_status(security: LoanSecurity) -> dict[str, Any]:
    required = rules.required_proofs(str(security.security_type), _configured())
    current = current_verification(security)
    latest = (
        LoanSecurityVerification.objects.filter(security=security).order_by("-verified_at").first()
    )
    released = str(security.status) == LoanSecurityStatus.RELEASED
    return {
        "security_id": str(security.id),
        "security_type": str(security.security_type),
        "released": released,
        "required_proofs": [
            {"key": key, "label": rules.PROOF_LABELS.get(key, key)} for key in required
        ],
        "document_ids": [str(item) for item in security.document_ids or []],
        "verified": current is not None,
        "verified_by": current.verifier_name if current else "",
        "verified_at": current.verified_at.isoformat() if current else None,
        "proofs": dict(current.proofs) if current else {},
        "needs_new_verification": latest is not None and current is None,
        "history": [
            {
                "verifier_name": item.verifier_name,
                "verified_at": item.verified_at.isoformat(),
                "note": item.note,
            }
            for item in LoanSecurityVerification.objects.filter(security=security).order_by(
                "-verified_at"
            )
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
        if current_verification(security) is None:
            problems.append(f"{label}: no current verification of its documents.")
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
        security = LoanSecurity.objects.select_for_update().filter(id=command.security_id).first()
        if security is None:
            raise SecurityProofError("Security does not exist.")
        if str(security.status) == LoanSecurityStatus.RELEASED:
            raise SecurityProofError("A released security is not verified.")
        required = rules.required_proofs(str(security.security_type), _configured())
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
