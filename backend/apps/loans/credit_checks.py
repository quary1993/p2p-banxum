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
    status: str = ""


CHECK_STATUSES = ("", "received", "reviewed")
REPORTING_PLAN_STATUSES = ("proposed", "agreed")
MAX_REPORTING_MILESTONES = 8


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
        "status": row.status,
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
        "repayment_source": loan.repayment_source,
        "reporting_plan_status": loan.reporting_plan_status,
        "reporting_milestones": list(loan.reporting_milestones or []),
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
    if command.status not in CHECK_STATUSES:
        raise CreditCheckValidationError("A check is received or reviewed.")
    row.source = command.source.strip()
    row.checked_on = command.checked_on
    row.status = command.status
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


@transaction.atomic
def set_repayment_source(*, actor: Model, loan_id: str, text: str) -> dict[str, Any]:
    """18.3: the credit file's "Source of repayment" text investors read."""
    _require_admin(actor)
    loan = Loan.objects.select_for_update().filter(id=loan_id).first()
    if loan is None:
        raise CreditCheckValidationError("Loan does not exist.")
    cleaned = text.strip()
    if len(cleaned) > 2000:
        raise CreditCheckValidationError(
            "The source of repayment can have at most 2000 characters."
        )
    loan.repayment_source = cleaned
    loan.updated_by_admin_id = actor.pk
    loan.save(update_fields=["repayment_source", "updated_by_admin_id", "updated_at"])
    _audit(actor, "loan.repayment_source_set", loan, {})
    return list_credit_checks(actor=actor, loan_id=loan_id)


def credit_file_updated_at(loan: Any, borrower: Any | None = None) -> Any:
    """18.3: when the credit file last changed: the loan, its checks or the borrower record."""
    moments = [loan.updated_at]
    if borrower is not None and getattr(borrower, "updated_at", None):
        moments.append(borrower.updated_at)
    latest_check = (
        loan.credit_checks.order_by("-updated_at").values_list("updated_at", flat=True).first()
    )
    if latest_check:
        moments.append(latest_check)
    return max(moments)


def reporting_plan_payload(loan: Any) -> dict[str, Any] | None:
    milestones = loan.reporting_milestones if isinstance(loan.reporting_milestones, list) else []
    if not milestones or loan.reporting_plan_status not in REPORTING_PLAN_STATUSES:
        return None
    return {"status": loan.reporting_plan_status, "milestones": list(milestones)}


def investor_checks(loan: Any) -> dict[str, Any]:
    """For investors: the recorded checks, how the loan is followed and the reporting plan."""
    return {
        "credit_checks": [check_payload(row) for row in loan.credit_checks.all()],
        "monitoring": {
            "frequency": loan.monitoring_frequency,
            "focus": loan.monitoring_focus,
        },
        "reporting_plan": reporting_plan_payload(loan),
        "repayment_source": str(loan.repayment_source),
    }


def _clean_milestone(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        raise CreditCheckValidationError("Each reporting milestone needs when, a title and a text.")
    cleaned = {key: str(item.get(key) or "").strip() for key in ("when", "title", "body")}
    if not cleaned["when"] or not cleaned["title"]:
        raise CreditCheckValidationError("Each reporting milestone needs when and a title.")
    for key, limit in (("when", 80), ("title", 120), ("body", 500)):
        if len(cleaned[key]) > limit:
            raise CreditCheckValidationError(
                f"A reporting milestone's {key} can be at most {limit} characters."
            )
    return cleaned


@transaction.atomic
def set_reporting_plan(
    *, actor: Model, loan_id: str, status: str, milestones: list[Any]
) -> dict[str, Any]:
    """Record what the borrower reports over the loan term, as a proposed or agreed plan.
    An empty list removes the plan."""
    _require_admin(actor)
    loan = Loan.objects.select_for_update().filter(id=loan_id).first()
    if loan is None:
        raise CreditCheckValidationError("Loan does not exist.")
    if len(milestones) > MAX_REPORTING_MILESTONES:
        raise CreditCheckValidationError(
            f"A reporting plan has at most {MAX_REPORTING_MILESTONES} milestones."
        )
    cleaned = [_clean_milestone(item) for item in milestones]
    if cleaned and status not in REPORTING_PLAN_STATUSES:
        raise CreditCheckValidationError("Say whether the plan is proposed or agreed.")
    loan.reporting_plan_status = status if cleaned else ""
    loan.reporting_milestones = cleaned
    loan.save(update_fields=["reporting_plan_status", "reporting_milestones", "updated_at"])
    _audit(
        actor,
        "loan.reporting_plan_set",
        loan,
        {"status": loan.reporting_plan_status, "milestones": len(cleaned)},
    )
    return list_credit_checks(actor=actor, loan_id=loan_id)
