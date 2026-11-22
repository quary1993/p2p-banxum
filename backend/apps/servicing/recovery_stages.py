"""IP of Webby-Soft SRL. U33-DEC-22: the real stages of a late or defaulted loan's follow-up.

The admin records what was done (title, real date, a note for investors) and, only when it is
known, what really comes next (title, date when known, note). Titles follow the real process:
there is no fixed list, no automatic progress and no universal calendar. Investors of the loan
see the stages on their investment; Banxum follows up and the investor is never asked to act.
A wrong entry is removed with a reason (kept for the audit), never deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from django.apps import apps
from django.db import transaction
from django.db.models import Model

from backend.apps.platform_core.domain.access import actor_ref_for_user
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.servicing.models import (
    LoanRecoveryResult,
    LoanRecoveryStage,
    LoanRecoveryStageStatus,
)
from backend.apps.servicing.services import (
    ServicingValidationError,
    _clean_required,
    _locked_loan,
    _require_admin_actor,
)

# Stages are recorded while a loan is late, in default or written off. A late loan that becomes
# current again keeps its history.
RECOVERY_STAGE_LOAN_STATUSES = frozenset({"late", "defaulted", "written_off"})
TITLE_MAX_LENGTH = 120
# Q16 (2026-11-13): the standard English stage names the admin can pick; an own title is allowed.
STANDARD_RECOVERY_STAGES = {
    "reminder_sent": "Reminder sent",
    "formal_notice": "Formal notice",
    "enforcement_of_security": "Enforcement of the security",
    "debt_collection": "Debt collection proceedings",
    "claim_in_insolvency": "Claim filed in insolvency",
    "sale_of_security": "Sale of the security",
    "recovery_closed": "Recovery closed",
    "agreement_terminated": "Loan agreement terminated",
}
RECOVERY_CLOSED_KEY = "recovery_closed"


@dataclass(frozen=True, slots=True)
class RecordRecoveryStageCommand:
    actor: Model
    loan_id: str
    status: str
    title: str
    occurred_on: date | None = None
    investor_note: str = ""
    # Q16: a standard stage (its English name becomes the title) and the result of "Recovery
    # closed" (full, partial or none).
    standard_key: str = ""
    recovery_result: str = ""


def _admin_emails(stages: list[LoanRecoveryStage]) -> dict[str, str]:
    """Admin id -> email for the people who recorded or removed the stages."""
    ids = {stage.created_by_admin_id for stage in stages} | {
        stage.removed_by_admin_id for stage in stages if stage.removed_by_admin_id
    }
    if not ids:
        return {}
    user_model = apps.get_model("accounts_auth", "User")
    return {
        str(user_id): str(email)
        for user_id, email in user_model.objects.filter(pk__in=ids).values_list("pk", "email")
    }


def _stage_payload(
    stage: LoanRecoveryStage, emails: dict[str, str] | None = None
) -> dict[str, Any]:
    names = emails if emails is not None else _admin_emails([stage])
    return {
        "id": str(stage.id),
        "status": stage.status,
        "title": stage.title,
        "standard_key": stage.standard_key,
        "recovery_result": stage.recovery_result,
        "occurred_on": stage.occurred_on,
        "investor_note": stage.investor_note,
        "created_at": stage.created_at,
        "recorded_by_email": names.get(str(stage.created_by_admin_id), ""),
        "removed_at": stage.removed_at,
        "removed_reason": stage.removed_reason,
        "removed_by_email": names.get(str(stage.removed_by_admin_id), "")
        if stage.removed_by_admin_id
        else "",
    }


def list_recovery_stages(*, actor: Model, loan_id: str) -> list[dict[str, Any]]:
    """Admin: every stage of the loan, removed ones included, with who recorded or removed it."""
    _require_admin_actor(actor)
    stages = list(
        LoanRecoveryStage.objects.filter(loan_id=loan_id).order_by(
            "status", "occurred_on", "created_at", "id"
        )
    )
    emails = _admin_emails(stages)
    return [_stage_payload(stage, emails) for stage in stages]


@transaction.atomic
def record_recovery_stage(command: RecordRecoveryStageCommand) -> dict[str, Any]:
    """Record a stage that happened, or set the step that really comes next.

    A new next step replaces the current one (removed with the reason "Replaced").
    """
    _require_admin_actor(command.actor)
    loan = _locked_loan(command.loan_id)
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) not in RECOVERY_STAGE_LOAN_STATUSES:
        raise ServicingValidationError(
            "Recovery stages can be recorded only for a loan that is late, in default or "
            "written off."
        )
    if command.status not in LoanRecoveryStageStatus.values:
        raise ServicingValidationError("The stage must be done or next.")
    standard_key = command.standard_key.strip()
    if standard_key and standard_key not in STANDARD_RECOVERY_STAGES:
        raise ServicingValidationError("Unknown standard stage.")
    title = (
        STANDARD_RECOVERY_STAGES[standard_key]
        if standard_key
        else _clean_required(command.title, "Title")
    )
    recovery_result = command.recovery_result.strip()
    closing = standard_key == RECOVERY_CLOSED_KEY
    if recovery_result and recovery_result not in LoanRecoveryResult.values:
        raise ServicingValidationError("The result must be full, partial or no recovery.")
    if closing and command.status == LoanRecoveryStageStatus.DONE and not recovery_result:
        raise ServicingValidationError(
            "Recovery closed states the result: full, partial or no recovery."
        )
    if recovery_result and not closing:
        raise ServicingValidationError("A result is recorded only with Recovery closed.")
    if len(title) > TITLE_MAX_LENGTH:
        raise ServicingValidationError(f"The title can have at most {TITLE_MAX_LENGTH} characters.")
    today = business_date(now_utc())
    if command.status == LoanRecoveryStageStatus.DONE:
        if command.occurred_on is None:
            raise ServicingValidationError("The date of a stage that happened is required.")
        if command.occurred_on > today:
            raise ServicingValidationError("A stage that happened cannot have a future date.")
        if command.occurred_on < loan_ref.loan_start_date:
            raise ServicingValidationError("The date cannot be before the start of the loan.")
    elif command.occurred_on is not None and command.occurred_on < today:
        raise ServicingValidationError("The date of the next step cannot be in the past.")
    now = now_utc()
    replaced: list[str] = []
    if command.status == LoanRecoveryStageStatus.NEXT:
        current = LoanRecoveryStage.objects.filter(
            loan_id=loan_ref.id, status=LoanRecoveryStageStatus.NEXT, removed_at__isnull=True
        )
        replaced = [str(stage_id) for stage_id in current.values_list("id", flat=True)]
        current.update(
            removed_at=now, removed_by_admin_id=command.actor.pk, removed_reason="Replaced"
        )
    stage = LoanRecoveryStage.objects.create(
        loan_id=loan_ref.id,
        status=command.status,
        title=title,
        standard_key=standard_key,
        recovery_result=recovery_result,
        occurred_on=command.occurred_on,
        investor_note=command.investor_note.strip(),
        created_by_admin_id=command.actor.pk,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="servicing.recovery_stage_recorded",
            target_type="Loan",
            target_id=str(loan_ref.id),
            metadata={
                "decision": "U33-DEC-22",
                "stage_id": str(stage.id),
                "status": command.status,
                "title": title,
                "standard_key": standard_key,
                "recovery_result": recovery_result,
                "occurred_on": command.occurred_on.isoformat() if command.occurred_on else None,
                "replaced_stage_ids": replaced,
            },
        )
    )
    return _stage_payload(stage)


@transaction.atomic
def remove_recovery_stage(
    *, actor: Model, loan_id: str, stage_id: str, reason: str
) -> dict[str, Any]:
    """Remove a wrong entry; it stays recorded for the audit and is hidden from investors."""
    _require_admin_actor(actor)
    cleaned = _clean_required(reason, "Reason")
    stage = (
        LoanRecoveryStage.objects.select_for_update().filter(id=stage_id, loan_id=loan_id).first()
    )
    if stage is None:
        raise ServicingValidationError("This stage does not exist for the loan.")
    if stage.removed_at is not None:
        raise ServicingValidationError("This stage is already removed.")
    stage.removed_at = now_utc()
    stage.removed_by_admin_id = actor.pk
    stage.removed_reason = cleaned
    stage.save(update_fields=["removed_at", "removed_by_admin_id", "removed_reason", "updated_at"])
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="servicing.recovery_stage_removed",
            target_type="Loan",
            target_id=str(loan_id),
            metadata={"decision": "U33-DEC-22", "stage_id": str(stage.id), "reason": cleaned},
        )
    )
    return _stage_payload(stage)


def investor_recovery_stages(loan_ids: list[str]) -> dict[str, dict[str, Any]]:
    """For investors: per loan, the stages that happened (oldest first) and the next step."""
    result: dict[str, dict[str, Any]] = {
        str(loan_id): {"stages": [], "next_step": None} for loan_id in loan_ids
    }
    if not loan_ids:
        return result
    stages = LoanRecoveryStage.objects.filter(
        loan_id__in=loan_ids, removed_at__isnull=True
    ).order_by("occurred_on", "created_at", "id")
    for stage in stages:
        entry = {
            "title": stage.title,
            "recovery_result": stage.recovery_result,
            "occurred_on": stage.occurred_on,
            "investor_note": stage.investor_note,
        }
        target = result[str(stage.loan_id)]
        if stage.status == LoanRecoveryStageStatus.NEXT:
            target["next_step"] = entry
        else:
            target["stages"].append(entry)
    return result
