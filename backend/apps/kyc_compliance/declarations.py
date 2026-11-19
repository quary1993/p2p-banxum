# IP of Webby-Soft SRL.
"""Investor declarations, compliance reviews and re-verification dates (18.10, Q12, U33-DEC-27).

- An investor submits a declaration in registration or in Settings; each submission is a new
  version (append-only). Q12 answers open a necessary review.
- ``investment_block`` is the one check every investment path calls (primary order and allocation,
  Loan Originator claim purchase, resale purchase): no declaration yet, a necessary open review, or
  a re-verification date that has passed. Withdrawals, documents and existing investments are
  never blocked.
- Compliance (role ``compliance`` or ``compliance_deputy``) closes reviews, asks for more
  information, opens a review by hand and sets re-verification dates. A daily job sends the
  notices 30 and 7 days before the date.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max, Model

from backend.apps.kyc_compliance.models import (
    ComplianceReview,
    ComplianceReviewStatus,
    InvestorDeclaration,
    InvestorReverification,
)
from backend.apps.platform_core.domain import declarations as rules
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    has_lender_role,
    is_admin_actor,
    is_superadmin_actor,
)
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.investor_notices import (
    InvestorNotice,
    enqueue_investor_notice,
)

BLOCK_NO_DECLARATION = "declaration_missing"
BLOCK_REVIEW_OPEN = "compliance_review_open"
BLOCK_REVERIFICATION_DUE = "reverification_due"

BLOCK_MESSAGES = {
    BLOCK_NO_DECLARATION: (
        "Complete your declarations (Settings > Declarations) before your next investment."
    ),
    BLOCK_REVIEW_OPEN: (
        "Our compliance team is reviewing your declarations. You can invest again when the "
        "review is closed. Your account, documents and investments stay available."
    ),
    BLOCK_REVERIFICATION_DUE: (
        "Your re-verification date has passed. Update your details to invest again; you can "
        "still withdraw your money."
    ),
}


class DeclarationsError(ValueError):
    """A declaration or compliance action that cannot be done, with a message to show."""


class DeclarationsPermissionError(PermissionError):
    pass


class InvestmentComplianceBlock(ValueError):
    """Raised by investment paths when ``investment_block`` returns a reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(BLOCK_MESSAGES[reason])
        self.reason = reason


def _is_compliance(actor: Model) -> bool:
    return is_admin_actor(actor) and rules.has_staff_role(actor, rules.COMPLIANCE_ROLES)


def _require_compliance(actor: Model) -> None:
    if not _is_compliance(actor):
        raise DeclarationsPermissionError(
            "Only the compliance role or its deputy can do this (granted by a superadmin)."
        )


def _audit(actor: Model, action: str, target: Any, metadata: dict[str, Any]) -> None:
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action=action,
            target_type=type(target).__name__,
            target_id=str(target.pk),
            metadata=metadata,
        )
    )


# Investor side ------------------------------------------------------------------------------


def latest_declaration(user_id: Any) -> InvestorDeclaration | None:
    return InvestorDeclaration.objects.filter(user_id=user_id).order_by("-version").first()


def open_necessary_review(user_id: Any) -> ComplianceReview | None:
    return (
        ComplianceReview.objects.filter(user_id=user_id, necessary=True)
        .exclude(status=ComplianceReviewStatus.CLOSED)
        .order_by("created_at")
        .first()
    )


def current_reverification(user_id: Any) -> InvestorReverification | None:
    return (
        InvestorReverification.objects.filter(
            user_id=user_id, completed_at__isnull=True, replaced_at__isnull=True
        )
        .order_by("-created_at")
        .first()
    )


def investment_block(user: Any, *, on: date | None = None) -> str | None:
    """Why this investor cannot make a new investment now, or None (18.10)."""
    if not getattr(settings, "COMPLIANCE_DECLARATIONS_REQUIRED", True):
        return None
    user_id = getattr(user, "pk", None)
    if user_id is None:
        return None
    if latest_declaration(user_id) is None:
        return BLOCK_NO_DECLARATION
    if open_necessary_review(user_id) is not None:
        return BLOCK_REVIEW_OPEN
    reverification = current_reverification(user_id)
    today = on or business_date(now_utc())
    if reverification is not None and reverification.due_date < today:
        return BLOCK_REVERIFICATION_DUE
    return None


def assert_can_invest(user: Any) -> None:
    reason = investment_block(user)
    if reason is not None:
        raise InvestmentComplianceBlock(reason)


@dataclass(frozen=True)
class SubmitDeclarationCommand:
    actor: Model
    data: dict[str, Any] = field(default_factory=dict)


def submit_declaration(command: SubmitDeclarationCommand) -> InvestorDeclaration:
    actor = cast(Any, command.actor)
    if not has_lender_role(actor):
        raise DeclarationsPermissionError("Only an investor account submits declarations.")
    try:
        answers = rules.validate_declaration(command.data)
    except rules.DeclarationError as exc:
        raise DeclarationsError(str(exc)) from exc
    triggers = rules.review_triggers(answers)
    with transaction.atomic():
        # Serialize the versions of one investor.
        get_user_model().objects.select_for_update().filter(pk=actor.pk).first()
        last = InvestorDeclaration.objects.filter(user_id=actor.pk).aggregate(v=Max("version"))
        declaration = InvestorDeclaration.objects.create(
            user_id=actor.pk,
            version=int(last["v"] or 0) + 1,
            subject_type=answers.subject_type,
            beneficial_owner_is_self=answers.beneficial_owner_is_self,
            beneficial_owner_name=answers.beneficial_owner_name,
            sources_of_funds=list(answers.sources_of_funds),
            savings_origin=answers.savings_origin,
            source_other_text=answers.source_other_text,
            pep_status=answers.pep_status,
            pep_person=answers.pep_person,
            pep_relation=answers.pep_relation,
            pep_function=answers.pep_function,
            pep_country=answers.pep_country,
            yearly_volume_band=answers.yearly_volume_band,
            company_details=dict(answers.company_details),
            review_triggers=list(triggers),
            submitted_at=now_utc(),
        )
        if triggers:
            review = open_necessary_review(actor.pk)
            if review is None:
                review = ComplianceReview.objects.create(
                    user_id=actor.pk,
                    declaration=declaration,
                    triggers=list(triggers),
                    necessary=True,
                    opened_reason="Declaration answers that need a review (Q12).",
                )
            else:
                review.declaration = declaration
                review.triggers = sorted(set(review.triggers) | set(triggers))
                review.save(update_fields=["declaration", "triggers", "updated_at"])
        _audit(
            actor,
            "compliance.declaration_submitted",
            declaration,
            {"version": declaration.version, "triggers": list(triggers)},
        )
    return cast(InvestorDeclaration, declaration)


def declaration_payload(declaration: InvestorDeclaration) -> dict[str, Any]:
    return {
        "id": str(declaration.id),
        "version": declaration.version,
        "subject_type": declaration.subject_type,
        "beneficial_owner_is_self": declaration.beneficial_owner_is_self,
        "beneficial_owner_name": declaration.beneficial_owner_name,
        "sources_of_funds": list(declaration.sources_of_funds),
        "savings_origin": declaration.savings_origin,
        "source_other_text": declaration.source_other_text,
        "pep_status": declaration.pep_status,
        "pep_person": declaration.pep_person,
        "pep_relation": declaration.pep_relation,
        "pep_function": declaration.pep_function,
        "pep_country": declaration.pep_country,
        "yearly_volume_band": declaration.yearly_volume_band,
        "company_details": dict(declaration.company_details or {}),
        "review_triggers": list(declaration.review_triggers or []),
        "submitted_at": declaration.submitted_at.isoformat(),
    }


def investor_compliance_status(user: Any) -> dict[str, Any]:
    """What the investor sees in Settings > Declarations and before investing."""
    user_id = user.pk
    declaration = latest_declaration(user_id)
    review = open_necessary_review(user_id)
    reverification = current_reverification(user_id)
    block = investment_block(user)
    return {
        "declaration": declaration_payload(declaration) if declaration is not None else None,
        "review_open": review is not None,
        "review_status": str(review.status) if review is not None else None,
        "review_message": review.investor_message if review is not None else "",
        "reverification_due_date": (
            reverification.due_date.isoformat() if reverification is not None else None
        ),
        "investment_block": block,
        "investment_block_message": BLOCK_MESSAGES[block] if block else "",
    }


# Compliance side ----------------------------------------------------------------------------


def review_payload(review: ComplianceReview) -> dict[str, Any]:
    user = cast(Any, review.user)
    return {
        "id": str(review.id),
        "investor_id": str(review.user_id),
        "investor_name": str(user.full_name),
        "investor_email": str(user.email),
        "declaration_version": review.declaration.version if review.declaration else None,
        "triggers": list(review.triggers or []),
        "trigger_labels": [rules.TRIGGER_LABELS.get(t, t) for t in review.triggers or []],
        "necessary": review.necessary,
        "status": str(review.status),
        "opened_reason": review.opened_reason,
        "investor_message": review.investor_message,
        "outcome_note": review.outcome_note,
        "created_at": review.created_at.isoformat(),
        "closed_at": review.closed_at.isoformat() if review.closed_at else None,
    }


def list_reviews(*, actor: Model, status: str | None = None) -> list[dict[str, Any]]:
    _require_compliance(actor)
    queryset = ComplianceReview.objects.select_related("user", "declaration")
    if status == "open":
        queryset = queryset.exclude(status=ComplianceReviewStatus.CLOSED)
    elif status:
        queryset = queryset.filter(status=status)
    return [review_payload(review) for review in queryset.order_by("-created_at")[:200]]


def investor_compliance_file(*, actor: Model, investor_id: str) -> dict[str, Any]:
    _require_compliance(actor)
    declarations = InvestorDeclaration.objects.filter(user_id=investor_id).order_by("-version")
    reviews = ComplianceReview.objects.filter(user_id=investor_id).select_related(
        "user", "declaration"
    )
    reverifications = InvestorReverification.objects.filter(user_id=investor_id)
    return {
        "investor_id": investor_id,
        "declarations": [declaration_payload(item) for item in declarations],
        "reviews": [review_payload(item) for item in reviews.order_by("-created_at")],
        "reverifications": [
            {
                "id": str(item.id),
                "due_date": item.due_date.isoformat(),
                "reason": item.reason,
                "notices_sent": list(item.notices_sent or []),
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "replaced_at": item.replaced_at.isoformat() if item.replaced_at else None,
            }
            for item in reverifications.order_by("-created_at")
        ],
    }


@dataclass(frozen=True)
class OpenReviewCommand:
    actor: Model
    investor_id: str
    reason: str
    necessary: bool = True


def open_review(command: OpenReviewCommand) -> ComplianceReview:
    """Compliance opens a review by hand (cases other than the Q12 triggers)."""
    _require_compliance(command.actor)
    reason = command.reason.strip()
    if len(reason) < 5:
        raise DeclarationsError("Give the reason for the review.")
    with transaction.atomic():
        review = ComplianceReview.objects.create(
            user_id=command.investor_id,
            declaration=latest_declaration(command.investor_id),
            triggers=["manual"],
            necessary=command.necessary,
            opened_reason=reason,
            opened_by_user_id=cast(Any, command.actor).pk,
            assigned_to_user_id=cast(Any, command.actor).pk,
        )
        _audit(command.actor, "compliance.review_opened", review, {"reason": reason})
    return review


@dataclass(frozen=True)
class DecideReviewCommand:
    actor: Model
    review_id: str
    decision: str  # "close" | "more_information"
    note: str = ""
    investor_message: str = ""


def decide_review(command: DecideReviewCommand) -> ComplianceReview:
    _require_compliance(command.actor)
    with transaction.atomic():
        review = ComplianceReview.objects.select_for_update().get(pk=command.review_id)
        if review.status == ComplianceReviewStatus.CLOSED:
            raise DeclarationsError("This review is already closed.")
        actor_id = cast(Any, command.actor).pk
        if command.decision == "close":
            if len(command.note.strip()) < 5:
                raise DeclarationsError("Record the outcome of the review.")
            review.status = ComplianceReviewStatus.CLOSED
            review.outcome_note = command.note.strip()
            review.closed_by_user_id = actor_id
            review.closed_at = now_utc()
        elif command.decision == "more_information":
            message = command.investor_message.strip()
            if len(message) < 5:
                raise DeclarationsError("Say what the investor must send or update.")
            review.status = ComplianceReviewStatus.MORE_INFORMATION
            review.investor_message = message
        else:
            raise DeclarationsError("Unknown decision.")
        review.assigned_to_user_id = actor_id
        review.save()
        _audit(
            command.actor,
            f"compliance.review_{command.decision}",
            review,
            {"note": review.outcome_note, "investor_message": review.investor_message},
        )
    if command.decision == "more_information":
        brand = settings.PLATFORM_BRAND_NAME
        enqueue_investor_notice(
            InvestorNotice(
                investor_user_id=str(review.user_id),
                topic="email.compliance_more_information",
                idempotency_key=f"email:compliance-more-info:{review.id}:{review.updated_at}",
                subject=f"{brand}: please update your declarations",
                body_text=review.investor_message,
                template_key="compliance.more_information.v1",
                headline="Please update your declarations",
                status_label="Action needed",
                status_tone="warning",
                metadata={"review_id": str(review.id)},
            )
        )
    return review


@dataclass(frozen=True)
class SetReverificationCommand:
    actor: Model
    investor_id: str
    due_date: date
    reason: str = ""


def set_reverification(command: SetReverificationCommand) -> InvestorReverification:
    """Compliance sets (or replaces) the investor's re-verification date (internal risk)."""
    _require_compliance(command.actor)
    if command.due_date <= business_date(now_utc()):
        raise DeclarationsError("The re-verification date must be in the future.")
    with transaction.atomic():
        current = current_reverification(command.investor_id)
        if current is not None:
            current.replaced_at = now_utc()
            current.save(update_fields=["replaced_at", "updated_at"])
        item = InvestorReverification.objects.create(
            user_id=command.investor_id,
            due_date=command.due_date,
            reason=command.reason.strip(),
            set_by_user_id=cast(Any, command.actor).pk,
        )
        _audit(
            command.actor,
            "compliance.reverification_set",
            item,
            {"due_date": command.due_date.isoformat()},
        )
    return item


def complete_reverification(*, actor: Model, investor_id: str) -> InvestorReverification:
    _require_compliance(actor)
    with transaction.atomic():
        current = current_reverification(investor_id)
        if current is None:
            raise DeclarationsError("This investor has no open re-verification date.")
        current.completed_at = now_utc()
        current.completed_by_user_id = cast(Any, actor).pk
        current.save(update_fields=["completed_at", "completed_by_user_id", "updated_at"])
        _audit(actor, "compliance.reverification_completed", current, {})
    return current


def send_reverification_notices(*, as_of: date | None = None) -> dict[str, Any]:
    """Daily job: notices 30 and 7 days before each open re-verification date (one per date and
    milestone; after a missed run only the closest milestone)."""
    today = as_of or business_date(now_utc())
    sent: list[str] = []
    brand = settings.PLATFORM_BRAND_NAME
    horizon = today + timedelta(days=max(rules.REVERIFICATION_NOTICE_DAYS))
    open_items = InvestorReverification.objects.filter(
        completed_at__isnull=True, replaced_at__isnull=True, due_date__gte=today
    ).filter(due_date__lte=horizon)
    for item in open_items:
        days_left = (item.due_date - today).days
        due = [m for m in rules.REVERIFICATION_NOTICE_DAYS if days_left <= m]
        if not due:
            continue
        milestone = min(due)
        already = {int(m) for m in item.notices_sent or []}
        if milestone in already or any(m <= milestone for m in already):
            continue
        enqueue_investor_notice(
            InvestorNotice(
                investor_user_id=str(item.user_id),
                topic="email.compliance_reverification_due",
                idempotency_key=f"email:reverification:{item.id}:{milestone}",
                subject=f"{brand}: re-verification due on {item.due_date.isoformat()}",
                body_text=(
                    f"Please update your details and declarations before "
                    f"{item.due_date.isoformat()}. After this date you cannot make new "
                    "investments until the re-verification is done; you can still withdraw."
                ),
                template_key="compliance.reverification_due.v1",
                headline="Re-verification due",
                status_label=f"{days_left} days left",
                status_tone="warning",
                data_rows=(("Due date", item.due_date.isoformat()),),
                metadata={"reverification_id": str(item.id), "milestone": milestone},
            )
        )
        item.notices_sent = sorted(already | {milestone}, reverse=True)
        item.save(update_fields=["notices_sent", "updated_at"])
        sent.append(f"{item.user_id}:{milestone}")
    return {"as_of_date": today.isoformat(), "sent": sent}


# Staff roles --------------------------------------------------------------------------------


@dataclass(frozen=True)
class SetStaffRolesCommand:
    actor: Model
    user_id: str
    roles: tuple[str, ...]


def set_staff_roles(command: SetStaffRolesCommand) -> Model:
    """A superadmin grants or removes the staff roles of an admin account (audited)."""
    if not is_superadmin_actor(command.actor):
        raise DeclarationsPermissionError("Only a superadmin can change staff roles.")
    unknown = [role for role in command.roles if role not in rules.STAFF_ROLES]
    if unknown:
        raise DeclarationsError(f"Unknown role: {', '.join(unknown)}.")
    user_model: Any = get_user_model()
    with transaction.atomic():
        user = user_model.objects.select_for_update().get(pk=command.user_id)
        if not is_admin_actor(user):
            raise DeclarationsError("Staff roles are for active admin accounts only.")
        before = list(user.staff_roles or [])
        user.staff_roles = sorted(set(command.roles))
        user.save(update_fields=["staff_roles"])
        _audit(
            command.actor,
            "account.staff_roles_changed",
            user,
            {"before": before, "after": list(user.staff_roles)},
        )
    return cast(Model, user)
