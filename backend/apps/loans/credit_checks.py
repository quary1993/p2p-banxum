"""IP of Webby-Soft SRL. U33-DEC-20: the credit file's "Checks & updates" kept on the loan.

Each check states what was checked, the result, the source and the date, as recorded by the team;
no rating or opinion on the business. The monitoring text says how often and on what the loan is
followed. Updates themselves are the published loan notes and the recorded recovery stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db import transaction
from django.db.models import Model

from backend.apps.loans.models import Loan, LoanCreditCheck
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event


class CreditCheckError(RuntimeError):
    pass


class CreditCheckAuthorizationError(CreditCheckError):
    pass


class CreditCheckValidationError(CreditCheckError):
    pass


@dataclass(frozen=True, slots=True)
class SaveCreditCheckCommand:
    actor: Model
    loan_id: str
    name: str
    result: str
    source: str = ""
    checked_on: date | None = None
    check_id: str | None = None


def _require_admin(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise CreditCheckAuthorizationError("Only an active admin can edit the credit file.")


def _loan(loan_id: str) -> Loan:
    loan = Loan.objects.filter(id=loan_id).first()
    if loan is None:
        raise CreditCheckValidationError("Loan does not exist.")
    return loan


def check_payload(row: LoanCreditCheck) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "position": row.position,
        "name": row.name,
        "result": row.result,
        "source": row.source,
        "checked_on": row.checked_on,
    }


def _audit(actor: Model, action: str, loan: Loan, metadata: dict[str, Any]) -> None:
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action=action,
            target_type="Loan",
            target_id=str(loan.id),
            metadata={"decision": "U33-DEC-20", **metadata},
        )
    )


def list_credit_checks(*, actor: Model, loan_id: str) -> dict[str, Any]:
    _require_admin(actor)
    loan = _loan(loan_id)
    return {
        "checks": [check_payload(row) for row in loan.credit_checks.all()],
        "monitoring_frequency": loan.monitoring_frequency,
        "monitoring_focus": loan.monitoring_focus,
    }


@transaction.atomic
def save_credit_check(command: SaveCreditCheckCommand) -> dict[str, Any]:
    _require_admin(command.actor)
    loan = _loan(command.loan_id)
    name = command.name.strip()
    result = command.result.strip()
    if not name or not result:
        raise CreditCheckValidationError("A check needs what was checked and its result.")
    if command.checked_on is not None and command.checked_on > business_date(now_utc()):
        raise CreditCheckValidationError("The date of a check cannot be in the future.")
    if command.check_id:
        row = (
            LoanCreditCheck.objects.select_for_update()
            .filter(id=command.check_id, loan=loan)
            .first()
        )
        if row is None:
            raise CreditCheckValidationError("This check does not exist for the loan.")
    else:
        last = loan.credit_checks.order_by("-position").first()
        row = LoanCreditCheck(loan=loan, position=0 if last is None else last.position + 1)
    row.name = name
    row.result = result
    row.source = command.source.strip()
    row.checked_on = command.checked_on
    row.updated_by_admin_id = command.actor.pk
    row.save()
    _audit(command.actor, "loan.credit_check_saved", loan, {"check_id": str(row.id)})
    return check_payload(row)


@transaction.atomic
def remove_credit_check(*, actor: Model, loan_id: str, check_id: str) -> None:
    _require_admin(actor)
    loan = _loan(loan_id)
    deleted, _ = LoanCreditCheck.objects.filter(id=check_id, loan=loan).delete()
    if not deleted:
        raise CreditCheckValidationError("This check does not exist for the loan.")
    _audit(actor, "loan.credit_check_removed", loan, {"check_id": str(check_id)})


@transaction.atomic
def move_credit_check(
    *, actor: Model, loan_id: str, check_id: str, direction: str
) -> dict[str, Any]:
    """Move a check one place up or down in the list investors see."""
    _require_admin(actor)
    if direction not in {"up", "down"}:
        raise CreditCheckValidationError("Move a check up or down.")
    loan = _loan(loan_id)
    rows = list(loan.credit_checks.select_for_update().order_by("position", "created_at", "id"))
    index = next((i for i, row in enumerate(rows) if str(row.id) == str(check_id)), None)
    if index is None:
        raise CreditCheckValidationError("This check does not exist for the loan.")
    target = index - 1 if direction == "up" else index + 1
    if not 0 <= target < len(rows):
        raise CreditCheckValidationError(
            "This check is already first." if direction == "up" else "This check is already last."
        )
    rows[index], rows[target] = rows[target], rows[index]
    for position, row in enumerate(rows):
        if row.position != position:
            LoanCreditCheck.objects.filter(pk=row.pk).update(position=position)
    _audit(actor, "loan.credit_check_moved", loan, {"check_id": str(check_id)})
    return list_credit_checks(actor=actor, loan_id=loan_id)


@transaction.atomic
def set_monitoring(*, actor: Model, loan_id: str, frequency: str, focus: str) -> dict[str, Any]:
    _require_admin(actor)
    loan = Loan.objects.select_for_update().filter(id=loan_id).first()
    if loan is None:
        raise CreditCheckValidationError("Loan does not exist.")
    loan.monitoring_frequency = frequency.strip()
    loan.monitoring_focus = focus.strip()
    loan.updated_by_admin_id = actor.pk
    loan.save(
        update_fields=[
            "monitoring_frequency",
            "monitoring_focus",
            "updated_by_admin_id",
            "updated_at",
        ]
    )
    _audit(actor, "loan.monitoring_set", loan, {})
    return list_credit_checks(actor=actor, loan_id=loan_id)


def investor_checks(loan: Any) -> dict[str, Any]:
    """For investors: the recorded checks and how the loan is followed."""
    return {
        "credit_checks": [check_payload(row) for row in loan.credit_checks.all()],
        "monitoring": {
            "frequency": loan.monitoring_frequency,
            "focus": loan.monitoring_focus,
        },
    }
