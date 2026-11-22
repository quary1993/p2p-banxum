"""IP of Webby-Soft SRL. Audit S4-4 (Q05, D4): the identity check of an assisted account recovery.

A lost second factor without recovery codes is recovered only after a NEW identity check at the
provider (Didit). This module starts that check, reads its result and compares it with the
identity that the investor's approved KYC case holds. The result is evidence for one recovery
case; it never changes the KYC case (see ``services._record_recovery_check_event``).

The comparison (the defined rule):

- the provider's decision is terminal and approved (document and liveness passed);
- the date of birth on the new document equals the stored verified date of birth;
- the name on the new document matches the stored verified name: after lowering the case and
  removing accents and punctuation (and reading "ue", "ae", "oe" like "ü", "ä", "ö"), the two
  names have the same words, or the words of one are all in the other and at least two words
  are shared (a document can leave out a middle name).

Any other outcome cannot confirm the identity. An admin's note is supplementary only.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from backend.apps.kyc_compliance import services
from backend.apps.kyc_compliance.models import (
    KycProviderEvent,
    KycProviderSession,
    KycSessionPurpose,
    KycStatus,
    KycVerificationCase,
)
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event

OUTCOME_PENDING = "pending"
OUTCOME_NOT_APPROVED = "not_approved"
OUTCOME_MISMATCH = "mismatch"
OUTCOME_MATCH = "match"
RECOVERY_CHECK_TTL = timedelta(days=7)


class RecoveryCheckError(services.KycComplianceError):
    pass


@dataclass(frozen=True, slots=True)
class RecoveryCheckResult:
    outcome: str
    provider_session_id: str
    provider_status: str = ""
    normalized_status: str = ""
    provider_event_id: str = ""
    decision_digest: str = ""
    decided_at: str = ""
    mismatches: tuple[str, ...] = ()
    compared: dict[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        """What the recovery case keeps: no name and no date, only the comparison's result."""
        return {
            "outcome": self.outcome,
            "provider": "didit",
            "provider_session_id": self.provider_session_id,
            "provider_status": self.provider_status,
            "normalized_status": self.normalized_status,
            "provider_event_id": self.provider_event_id,
            "decision_digest": self.decision_digest,
            "decided_at": self.decided_at,
            "mismatches": list(self.mismatches),
            "compared": dict(self.compared),
        }


def name_words(value: str) -> frozenset[str]:
    """The words of a name without case, accents and punctuation.

    A document's machine-readable zone writes "MUELLER" where the printed name says "Müller",
    and some systems write "Muller": the three spellings give the same word here.
    """
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold().replace("ß", "ss"))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = "".join(ch if ch.isalnum() else " " for ch in plain)
    words = (
        word.replace("ae", "a").replace("oe", "o").replace("ue", "u") for word in cleaned.split()
    )
    return frozenset(words)


def names_match(stored: str, new: str) -> bool:
    first, second = name_words(stored), name_words(new)
    if not first or not second:
        return False
    if first == second:
        return True
    shared = first & second
    return len(shared) >= 2 and (first <= second or second <= first)


def stored_identity(user: Model) -> KycVerificationCase | None:
    """The approved KYC case with the verified name and date of birth, or None."""
    return (
        KycVerificationCase.objects.filter(user_id=user.pk, status=KycStatus.APPROVED)
        .exclude(verified_full_name="")
        .exclude(verified_birth_date__isnull=True)
        .first()
    )


@transaction.atomic
def start_recovery_identity_check(*, user: Model, reference: str) -> KycProviderSession:
    """Create a new provider session for the recovery case ``reference``."""
    case = stored_identity(user)
    if case is None:
        raise RecoveryCheckError(
            "This account has no verified name and date of birth from an approved identity "
            "check, so a new identity check cannot be compared with it."
        )
    workflow_id = services._workflow_id(None)
    vendor_data = services.vendor_data_for_user(user)
    hosted = services._create_provider_session(
        user=user, workflow_id=workflow_id, vendor_data=vendor_data
    )
    session: KycProviderSession = KycProviderSession.objects.create(
        case=case,
        provider_environment=services._provider_environment(),
        workflow_id=workflow_id,
        provider_session_id=hosted.provider_session_id,
        verification_url=hosted.verification_url,
        vendor_data=vendor_data,
        expires_at=timezone.now() + RECOVERY_CHECK_TTL,
        provider_payload=hosted.provider_payload,
        purpose=KycSessionPurpose.ACCOUNT_RECOVERY,
        recovery_reference=str(reference),
    )
    record_audit_event(
        AuditCommand(
            actor=ActorRef.system(),
            action="kyc.recovery_check_started",
            target_type="KycVerificationCase",
            target_id=str(case.id),
            metadata={
                "provider_session_id": session.provider_session_id,
                "recovery_reference": str(reference),
            },
        )
    )
    return session


def _terminal_event(session: KycProviderSession) -> KycProviderEvent | None:
    return (
        KycProviderEvent.objects.filter(
            session=session, normalized_status__in=services.TERMINAL_DECISION_STATUSES
        )
        .order_by("-processed_at", "-id")
        .first()
    )


def _poll_provider(session: KycProviderSession) -> None:
    """Ask the provider for the decision when no webhook brought it (live provider only)."""
    payload = session.provider_payload if isinstance(session.provider_payload, dict) else {}
    live = str(payload.get("mode", "")).strip().lower() == "api" or (
        services._didit_session_provider() in {"api", "didit", "live"}
    )
    if not live:
        return
    decision = services._decision_poll_payload(
        session=session, payload=services._retrieve_didit_session_decision(session)
    )
    command = services.provider_event_command_from_payload(
        decision,
        provider_event_id_fallback=f"didit-poll:{services._safe_json_hash(decision)[:48]}",
    )
    services.process_didit_event(command)


def recovery_check_result(
    *, provider_session_id: str, reference: str, refresh: bool = True
) -> RecoveryCheckResult:
    """The outcome of the identity check that belongs to the recovery case ``reference``."""
    session = (
        KycProviderSession.objects.select_related("case")
        .filter(
            provider_session_id=provider_session_id,
            purpose=KycSessionPurpose.ACCOUNT_RECOVERY,
            recovery_reference=str(reference),
        )
        .first()
    )
    if session is None:
        # A session of another recovery, or a normal KYC session, proves nothing here.
        raise RecoveryCheckError("This identity check does not belong to this recovery.")
    event = _terminal_event(session)
    if event is None and refresh:
        try:
            _poll_provider(session)
        except (services.DiditApiError, services.KycWebhookMatchError):
            pass
        event = _terminal_event(session)
    if event is None:
        return RecoveryCheckResult(
            outcome=OUTCOME_PENDING, provider_session_id=session.provider_session_id
        )
    payload = event.raw_payload if isinstance(event.raw_payload, dict) else {}
    base: dict[str, Any] = {
        "provider_session_id": session.provider_session_id,
        "provider_status": str(event.provider_status),
        "normalized_status": str(event.normalized_status),
        "provider_event_id": str(event.provider_event_id),
        "decision_digest": services._safe_json_hash(payload),
        "decided_at": event.processed_at.isoformat(),
    }
    if event.normalized_status != KycStatus.APPROVED:
        return RecoveryCheckResult(outcome=OUTCOME_NOT_APPROVED, **base)
    case = session.case
    new = services._verified_identity(payload)
    new_name = str(new.get("verified_full_name") or "")
    new_birth: date | None = new.get("verified_birth_date")
    mismatches: list[str] = []
    if not case.verified_full_name or case.verified_birth_date is None:
        mismatches.append("stored_identity_incomplete")
    if not new_name:
        mismatches.append("name_missing")
    elif not names_match(str(case.verified_full_name), new_name):
        mismatches.append("name")
    if new_birth is None:
        mismatches.append("birth_date_missing")
    elif case.verified_birth_date is not None and new_birth != case.verified_birth_date:
        mismatches.append("birth_date")
    compared = {
        "name": "name" not in mismatches and "name_missing" not in mismatches,
        "birth_date": "birth_date" not in mismatches and "birth_date_missing" not in mismatches,
        "kyc_case_id": str(case.id),
    }
    return RecoveryCheckResult(
        outcome=OUTCOME_MISMATCH if mismatches else OUTCOME_MATCH,
        mismatches=tuple(mismatches),
        compared=compared,
        **base,
    )
