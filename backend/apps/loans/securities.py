"""IP of Webby-Soft SRL. U33-DEC-21: several securities per loan, managed separately.

Each security has only the fields that apply: the type of asset or right, the holder (owner or
guarantor), rank, status, value with its date, source and appraiser, prior-ranking debt,
insurance and the documents; a guarantee has its scope and limit instead of an asset value. The
guarantor's wealth is never added to an asset value, and the same asset is not counted twice.

The first security (position 0) gives the loan's summary fields (collateral type, value and
description) that the loan form, the loan-to-value figure and older filters read; editing those
fields on the loan edits the first security, and the other way round.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, cast

from django.apps import apps
from django.db import transaction
from django.db.models import Model

from backend.apps.loans.models import (
    GUARANTEE_SECURITY_TYPES,
    LEGACY_ONLY_SECURITY_TYPES,
    CollateralType,
    Loan,
    LoanSecurity,
    LoanSecurityStatus,
    LoanStatus,
)
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event


class LoanSecurityError(RuntimeError):
    pass


class LoanSecurityAuthorizationError(LoanSecurityError):
    pass


class LoanSecurityValidationError(LoanSecurityError):
    pass


@dataclass(frozen=True, slots=True)
class SaveLoanSecurityCommand:
    actor: Model
    loan_id: str
    security_type: str
    security_id: str | None = None
    description: str = ""
    holder_name: str = ""
    rank: int | None = None
    status: str = ""
    value_minor: int | None = None
    valuation_date: date | None = None
    valuation_source: str = ""
    appraiser: str = ""
    prior_ranking_debt_minor: int | None = None
    insurance: str = ""
    undertaking_scope: str = ""
    undertaking_limit_minor: int | None = None
    document_ids: tuple[str, ...] = field(default_factory=tuple)


def _require_admin(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise LoanSecurityAuthorizationError("Only an active admin can manage loan securities.")


def _loan(loan_id: str) -> Loan:
    loan = Loan.objects.select_for_update().filter(id=loan_id).first()
    if loan is None:
        raise LoanSecurityValidationError("Loan does not exist.")
    return loan


def is_guarantee(security_type: str) -> bool:
    return security_type in GUARANTEE_SECURITY_TYPES


def security_payload(
    security: LoanSecurity, documents: dict[str, str] | None = None
) -> dict[str, Any]:
    names = documents or {}
    return {
        "id": str(security.id),
        "position": security.position,
        "security_type": security.security_type,
        "is_guarantee": is_guarantee(security.security_type),
        "description": security.description,
        "holder_name": security.holder_name,
        "rank": security.rank,
        "status": security.status,
        "value_minor": security.value_minor,
        "valuation_date": security.valuation_date,
        "valuation_source": security.valuation_source,
        "appraiser": security.appraiser,
        "prior_ranking_debt_minor": security.prior_ranking_debt_minor,
        "insurance": security.insurance,
        "undertaking_scope": security.undertaking_scope,
        "undertaking_limit_minor": security.undertaking_limit_minor,
        "documents": [
            {"id": str(document_id), "display_name": names.get(str(document_id), "")}
            for document_id in security.document_ids or []
            if str(document_id) in names
        ],
    }


def _borrower_documents(loan: Loan) -> dict[str, str]:
    if loan.borrower_id is None:
        return {}
    document_model = apps.get_model("entities", "BorrowerDocument")
    return {
        str(document.id): str(getattr(document, "display_name", "") or "")
        for document in document_model.objects.filter(borrower_id=loan.borrower_id)
    }


def borrower_documents_for_securities(*, actor: Model, loan_id: str) -> list[dict[str, str]]:
    """The borrower's documents an admin can attach to a security (id and name)."""
    _require_admin(actor)
    return [
        {"id": document_id, "display_name": name}
        for document_id, name in _borrower_documents(_loan(loan_id)).items()
    ]


def list_loan_securities(*, actor: Model, loan_id: str) -> list[dict[str, Any]]:
    _require_admin(actor)
    loan = Loan.objects.filter(id=loan_id).first()
    if loan is None:
        raise LoanSecurityValidationError("Loan does not exist.")
    documents = _borrower_documents(loan)
    return [security_payload(item, documents) for item in loan.securities.all()]


def _clean(value: str) -> str:
    return value.strip()


def _validated(
    command: SaveLoanSecurityCommand, loan: Loan, current: LoanSecurity | None
) -> dict[str, Any]:
    security_type = command.security_type
    if security_type not in CollateralType.values:
        raise LoanSecurityValidationError("Unknown security type.")
    if security_type == CollateralType.UNSECURED_EXCEPTION:
        raise LoanSecurityValidationError("An unsecured exception is not a security.")
    if security_type in LEGACY_ONLY_SECURITY_TYPES and (
        current is None or current.security_type != security_type
    ):
        raise LoanSecurityValidationError(
            "Record each security of a mixed or asset-backed package on its own, with its type."
        )
    description = _clean(command.description)
    if security_type == CollateralType.OTHER and not description:
        raise LoanSecurityValidationError("Describe a security of the type Other.")
    if command.status and command.status not in LoanSecurityStatus.values:
        raise LoanSecurityValidationError("Unknown security status.")
    if command.rank is not None and command.rank < 1:
        raise LoanSecurityValidationError("The rank starts at 1 (first rank).")
    for label, amount in (
        ("value", command.value_minor),
        ("prior-ranking debt", command.prior_ranking_debt_minor),
        ("limit of the undertaking", command.undertaking_limit_minor),
    ):
        if amount is not None and amount < 0:
            raise LoanSecurityValidationError(f"The {label} cannot be negative.")
    guarantee = is_guarantee(security_type)
    if guarantee and (
        command.value_minor is not None
        or command.prior_ranking_debt_minor is not None
        or command.valuation_date is not None
        or _clean(command.valuation_source)
        or _clean(command.appraiser)
    ):
        raise LoanSecurityValidationError(
            "A guarantee has a scope and a limit, not an asset value or a valuation."
        )
    if not guarantee and (
        _clean(command.undertaking_scope) or command.undertaking_limit_minor is not None
    ):
        raise LoanSecurityValidationError(
            "Scope and limit apply to a personal or corporate guarantee only."
        )
    if command.prior_ranking_debt_minor is not None and not command.value_minor:
        raise LoanSecurityValidationError("Prior-ranking debt needs the value of the asset.")
    documents = _borrower_documents(loan)
    unknown = [item for item in command.document_ids if str(item) not in documents]
    if unknown:
        raise LoanSecurityValidationError("A document is not a document of this borrower.")
    return {
        "security_type": security_type,
        "description": description,
        "holder_name": _clean(command.holder_name),
        "rank": command.rank,
        "status": command.status,
        "value_minor": command.value_minor,
        "valuation_date": command.valuation_date,
        "valuation_source": _clean(command.valuation_source),
        "appraiser": _clean(command.appraiser),
        "prior_ranking_debt_minor": command.prior_ranking_debt_minor,
        "insurance": _clean(command.insurance),
        "undertaking_scope": _clean(command.undertaking_scope),
        "undertaking_limit_minor": command.undertaking_limit_minor,
        "document_ids": [str(item) for item in dict.fromkeys(command.document_ids)],
    }


def _sync_loan_summary(loan: Loan) -> None:
    """The first security gives the loan's summary fields (a guarantee has no asset value)."""
    first = loan.securities.order_by("position", "created_at").first()
    if first is None:
        return
    value = 0 if is_guarantee(first.security_type) else int(first.value_minor or 0)
    changed = []
    for name, new in (
        ("collateral_type", first.security_type),
        ("collateral_description", first.description),
        ("collateral_value_minor", value),
    ):
        if getattr(loan, name) != new:
            setattr(loan, name, new)
            changed.append(name)
    if changed:
        loan.save(update_fields=[*changed, "updated_at"])


@transaction.atomic
def save_loan_security(command: SaveLoanSecurityCommand) -> dict[str, Any]:
    """Add a security to a loan, or change one."""
    _require_admin(command.actor)
    loan = _loan(command.loan_id)
    current = None
    if command.security_id:
        current = (
            LoanSecurity.objects.select_for_update()
            .filter(id=command.security_id, loan=loan)
            .first()
        )
        if current is None:
            raise LoanSecurityValidationError("This security does not exist for the loan.")
    values = _validated(command, loan, current)
    if current is None:
        last = loan.securities.order_by("-position").first()
        current = LoanSecurity.objects.create(
            loan=loan,
            position=0 if last is None else last.position + 1,
            created_by_admin_id=command.actor.pk,
            updated_by_admin_id=command.actor.pk,
            **values,
        )
        action = "loan.security_added"
    else:
        for name, value in values.items():
            setattr(current, name, value)
        current.updated_by_admin_id = command.actor.pk
        current.save()
        action = "loan.security_changed"
    _sync_loan_summary(loan)
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action=action,
            target_type="Loan",
            target_id=str(loan.id),
            metadata={
                "decision": "U33-DEC-21",
                "security_id": str(current.id),
                "security_type": current.security_type,
                "status": current.status,
            },
        )
    )
    return security_payload(current, _borrower_documents(loan))


@transaction.atomic
def remove_loan_security(*, actor: Model, loan_id: str, security_id: str) -> None:
    """Remove a security entered by mistake from a draft. After publication a security that ends
    is marked as released instead, so the history stays factual."""
    _require_admin(actor)
    loan = _loan(loan_id)
    if loan.status != LoanStatus.DRAFT:
        raise LoanSecurityValidationError(
            "After publication a security is not removed: set its status to released."
        )
    security = LoanSecurity.objects.filter(id=security_id, loan=loan).first()
    if security is None:
        raise LoanSecurityValidationError("This security does not exist for the loan.")
    if loan.securities.count() == 1:
        raise LoanSecurityValidationError("A loan keeps at least one security.")
    security.delete()
    for position, item in enumerate(loan.securities.order_by("position", "created_at")):
        if item.position != position:
            LoanSecurity.objects.filter(pk=item.pk).update(position=position)
    _sync_loan_summary(loan)
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="loan.security_removed",
            target_type="Loan",
            target_id=str(loan.id),
            metadata={"decision": "U33-DEC-21", "security_id": str(security_id)},
        )
    )


# A free position for the swap: (loan, position) is unique.
_SWAP_POSITION = 32767


@transaction.atomic
def move_loan_security(
    *, actor: Model, loan_id: str, security_id: str, direction: str
) -> list[dict[str, Any]]:
    """Move a security one place up or down in a draft. The first one gives the loan's summary
    (collateral type, value and loan-to-value); after publication the order stays fixed."""
    _require_admin(actor)
    if direction not in {"up", "down"}:
        raise LoanSecurityValidationError("Move a security up or down.")
    loan = _loan(loan_id)
    if loan.status != LoanStatus.DRAFT:
        raise LoanSecurityValidationError("After publication the order of the securities is fixed.")
    items = list(loan.securities.select_for_update().order_by("position", "created_at"))
    index = next((i for i, item in enumerate(items) if str(item.id) == str(security_id)), None)
    if index is None:
        raise LoanSecurityValidationError("This security does not exist for the loan.")
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(items):
        raise LoanSecurityValidationError(
            "This security is already first."
            if direction == "up"
            else "This security is already last."
        )
    moved, other = items[index], items[target]
    from_position, to_position = moved.position, other.position
    LoanSecurity.objects.filter(pk=moved.pk).update(position=_SWAP_POSITION)
    LoanSecurity.objects.filter(pk=other.pk).update(position=from_position)
    LoanSecurity.objects.filter(pk=moved.pk).update(position=to_position)
    _sync_loan_summary(loan)
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="loan.security_moved",
            target_type="Loan",
            target_id=str(loan.id),
            metadata={
                "decision": "U33-DEC-21",
                "security_id": str(moved.id),
                "security_type": moved.security_type,
                "from_position": from_position,
                "to_position": to_position,
            },
        )
    )
    documents = _borrower_documents(loan)
    return [security_payload(item, documents) for item in loan.securities.all()]


def sync_first_security_from_loan(loan: Loan, *, actor: Model | None = None) -> None:
    """The loan form's collateral fields create or change the first security."""
    if loan.collateral_type == CollateralType.UNSECURED_EXCEPTION:
        return
    guarantee = is_guarantee(loan.collateral_type)
    value = (
        None if guarantee or not loan.collateral_value_minor else int(loan.collateral_value_minor)
    )
    first = loan.securities.order_by("position", "created_at").first()
    actor_id = getattr(actor, "pk", None)
    if first is None:
        LoanSecurity.objects.create(
            loan=loan,
            position=0,
            security_type=loan.collateral_type,
            description=loan.collateral_description or "",
            value_minor=value,
            created_by_admin_id=actor_id,
            updated_by_admin_id=actor_id,
        )
        return
    changed = False
    for name, new in (
        ("security_type", loan.collateral_type),
        ("description", loan.collateral_description or ""),
        ("value_minor", value),
    ):
        if getattr(first, name) != new:
            setattr(first, name, new)
            changed = True
    if changed:
        if guarantee:
            first.prior_ranking_debt_minor = None
            first.valuation_date = None
        first.updated_by_admin_id = actor_id
        first.save()


def all_securities_released(loan: Loan) -> bool:
    """U33-DEC-38: a loan whose recorded securities are all released is not secured any more.

    A loan without security records (created before U33-DEC-21 and not migrated) is judged by
    its collateral type, as before.
    """
    securities = loan.securities.all()
    return (
        securities.exists() and not securities.exclude(status=LoanSecurityStatus.RELEASED).exists()
    )


def investor_securities(loan_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """For investors: every security of each loan, in order, released ones with their status."""
    result: dict[str, list[dict[str, Any]]] = {str(loan_id): [] for loan_id in loan_ids}
    if not loan_ids:
        return result
    securities = list(
        LoanSecurity.objects.filter(loan_id__in=loan_ids)
        .select_related("loan")
        .order_by("loan_id", "position", "created_at")
    )
    borrower_ids = {cast(Any, item.loan).borrower_id for item in securities if item.document_ids}
    names: dict[str, str] = {}
    if borrower_ids:
        document_model = apps.get_model("entities", "BorrowerDocument")
        names = {
            str(document.id): str(getattr(document, "display_name", "") or "")
            for document in document_model.objects.filter(
                borrower_id__in=borrower_ids, investor_visible=True
            )
        }
    for item in securities:
        result[str(item.loan_id)].append(security_payload(item, names))
    return result


def security_types_by_loan(loan_ids: list[str]) -> dict[str, list[str]]:
    """The types of the securities in force (not released), for filters and Smart Invest."""
    result: dict[str, list[str]] = {str(loan_id): [] for loan_id in loan_ids}
    rows = (
        LoanSecurity.objects.filter(loan_id__in=loan_ids)
        .exclude(status=LoanSecurityStatus.RELEASED)
        .order_by("loan_id", "position")
        .values_list("loan_id", "security_type")
    )
    for loan_id, security_type in rows:
        types = result[str(loan_id)]
        if security_type not in types:
            types.append(security_type)
    return result


def loan_security_types(loan: Any) -> list[str]:
    """The types of one loan's securities in force; its collateral type when none is recorded."""
    loan_id = str(loan.id)
    types = security_types_by_loan([loan_id])[loan_id]
    if types:
        return types
    collateral = str(loan.collateral_type)
    return [] if collateral == CollateralType.UNSECURED_EXCEPTION else [collateral]
