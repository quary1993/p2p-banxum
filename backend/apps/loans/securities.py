"""IP of Webby-Soft SRL. U33-DEC-21: several securities per loan, managed separately.

Each security has only the fields that apply: the type of asset or right, the holder (owner or
guarantor), rank, status, value with its date, source and appraiser, prior-ranking debt,
insurance and the documents; a guarantee has its scope and limit instead of an asset value. The
guarantor's wealth is never added to an asset value, and the same asset is not counted twice.

C06 / F16 (2026-11-13, 2026-11-16): the admin chooses the main security, which gives the loan's
summary fields (collateral type and description). The loan's collateral value, which the
loan-to-value, the filters and Smart Invest read, is the sum of the values of the securities that
count in the loan-to-value and are not released: ``LTV = loan amount / sum x 100``. The same asset
is never counted twice and a guarantee never counts. Values are in the loan currency; a valuation
in another currency keeps its amount, the rate and the rate date. The loan form's collateral
fields edit the main security.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from django.apps import apps
from django.db import transaction
from django.db.models import Model

from backend.apps.loans.models import (
    CLOSED_FOR_NEW_SECURITY_TYPES,
    GUARANTEE_SECURITY_TYPES,
    LTV_ASSET_SECURITY_TYPES,
    CollateralType,
    Loan,
    LoanDocument,
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
    public_name: str = ""
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
    # F16: None keeps the current choice (a new security takes the default of its type).
    counts_in_ltv: bool | None = None
    # F16: a valuation in another currency than the loan's (amount, rate to the loan currency,
    # rate date); the value in the loan currency is then calculated.
    valuation_currency: str = ""
    valuation_amount_minor: int | None = None
    valuation_fx_rate: Decimal | None = None
    valuation_fx_rate_date: date | None = None
    # Audit S1-3: the asset's stable identifier (needed when several assets count in the LTV).
    asset_reference: str = ""


DISTINCT_ASSETS_MESSAGE = (
    "Several assets count in the loan-to-value: enter the asset reference of each one (for "
    "example the land register number or the serial number), so that one asset is never "
    "counted twice."
)


def normalized_asset_reference(value: str) -> str:
    return " ".join(value.split()).upper()[:160]


def counted_asset_problems(loan: Loan) -> list[str]:
    """Audit S1-3 (C06): two counted assets need distinct asset references."""
    counted = list(
        loan.securities.filter(counts_in_ltv=True)
        .exclude(status=LoanSecurityStatus.RELEASED)
        .values_list("asset_reference", flat=True)
    )
    if len(counted) < 2:
        return []
    if any(not reference for reference in counted):
        return [DISTINCT_ASSETS_MESSAGE]
    if len(set(counted)) != len(counted):
        return ["The same asset reference counts twice in the loan-to-value."]
    return []


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
        "public_name": security.public_name,
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
        "is_main": security.is_main,
        "counts_in_ltv": security.counts_in_ltv,
        "asset_reference": security.asset_reference,
        "valuation_currency": security.valuation_currency,
        "valuation_amount_minor": security.valuation_amount_minor,
        "valuation_fx_rate": (
            None if security.valuation_fx_rate is None else str(security.valuation_fx_rate)
        ),
        "valuation_fx_rate_date": security.valuation_fx_rate_date,
        "documents": [
            {"id": str(document_id), "display_name": names.get(str(document_id), "")}
            for document_id in security.document_ids or []
            if str(document_id) in names
        ],
    }


def _borrower_documents(loan: Loan) -> dict[str, str]:
    """The documents a security of this loan can link: the borrower's documents and the
    documents uploaded to the loan (re-audit: a Loan Originator claim has no borrower)."""
    documents: dict[str, str] = {}
    if loan.borrower_id is not None:
        document_model = apps.get_model("entities", "BorrowerDocument")
        documents.update(
            (str(document.id), str(getattr(document, "display_name", "") or ""))
            for document in document_model.objects.filter(borrower_id=loan.borrower_id)
        )
    documents.update(
        (str(document.id), str(document.display_name))
        for document in LoanDocument.objects.filter(loan_id=loan.pk)
    )
    return documents


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
    if security_type in CLOSED_FOR_NEW_SECURITY_TYPES and (
        current is None or current.security_type != security_type
    ):
        if security_type == CollateralType.INVOICES:
            raise LoanSecurityValidationError(
                "Invoices are closed for new securities: record the pledged claim as Receivables "
                "and attach the invoice as a document."
            )
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
    value_minor = command.value_minor
    valuation = _foreign_valuation(command, loan, guarantee=guarantee)
    if valuation["valuation_currency"]:
        # Audit step 1 D4: a value in the loan currency that differs from the converted one is
        # ambiguous; leave it empty or send the converted value.
        if command.value_minor is not None and command.value_minor != valuation["converted_minor"]:
            raise LoanSecurityValidationError(
                "The value in the loan currency is calculated from the amount and the rate; "
                "leave it empty."
            )
        value_minor = valuation["converted_minor"]
    if command.prior_ranking_debt_minor is not None and not value_minor:
        raise LoanSecurityValidationError("Prior-ranking debt needs the value of the asset.")
    status = command.status
    counts_in_ltv = command.counts_in_ltv
    if counts_in_ltv is None:
        counts_in_ltv = (
            current.counts_in_ltv
            if current is not None
            else security_type in LTV_ASSET_SECURITY_TYPES and bool(value_minor)
        )
    if counts_in_ltv and guarantee:
        raise LoanSecurityValidationError("A guarantee never counts in the loan-to-value.")
    if counts_in_ltv and not value_minor:
        raise LoanSecurityValidationError(
            "Only a security with a documented value counts in the loan-to-value."
        )
    asset_reference = normalized_asset_reference(command.asset_reference)
    if guarantee and asset_reference:
        raise LoanSecurityValidationError("A guarantee has no asset reference.")
    if counts_in_ltv and status != LoanSecurityStatus.RELEASED:
        others = loan.securities.filter(counts_in_ltv=True).exclude(
            status=LoanSecurityStatus.RELEASED
        )
        if current is not None:
            others = others.exclude(pk=current.pk)
        other_references = list(others.values_list("asset_reference", flat=True))
        if other_references:
            if not asset_reference or any(not item for item in other_references):
                raise LoanSecurityValidationError(DISTINCT_ASSETS_MESSAGE)
            if asset_reference in other_references:
                raise LoanSecurityValidationError(
                    "This asset already counts in the loan-to-value (same asset reference)."
                )
    documents = _borrower_documents(loan)
    unknown = [item for item in command.document_ids if str(item) not in documents]
    if unknown:
        raise LoanSecurityValidationError("A document is not a document of this borrower.")
    return {
        "security_type": security_type,
        "description": description,
        "public_name": _clean(command.public_name)[:120],
        "holder_name": _clean(command.holder_name),
        "rank": command.rank,
        "status": status,
        "value_minor": value_minor,
        "counts_in_ltv": counts_in_ltv,
        "asset_reference": asset_reference,
        "valuation_currency": valuation["valuation_currency"],
        "valuation_amount_minor": valuation["valuation_amount_minor"],
        "valuation_fx_rate": valuation["valuation_fx_rate"],
        "valuation_fx_rate_date": valuation["valuation_fx_rate_date"],
        "valuation_date": command.valuation_date,
        "valuation_source": _clean(command.valuation_source),
        "appraiser": _clean(command.appraiser),
        "prior_ranking_debt_minor": command.prior_ranking_debt_minor,
        "insurance": _clean(command.insurance),
        "undertaking_scope": _clean(command.undertaking_scope),
        "undertaking_limit_minor": command.undertaking_limit_minor,
        "document_ids": [str(item) for item in dict.fromkeys(command.document_ids)],
    }


def _foreign_valuation(
    command: SaveLoanSecurityCommand, loan: Loan, *, guarantee: bool
) -> dict[str, Any]:
    """F16: a valuation in another currency is converted to the loan currency (no FX for investors).

    The amount, the rate (one unit of the valuation currency in the loan currency) and the rate
    date are kept; the value in the loan currency is calculated once, rounded half up.
    """
    currency = command.valuation_currency.strip().upper()
    loan_currency = str(loan.currency_id).upper()
    empty: dict[str, Any] = {
        "valuation_currency": "",
        "valuation_amount_minor": None,
        "valuation_fx_rate": None,
        "valuation_fx_rate_date": None,
        "converted_minor": None,
    }
    if not currency or currency == loan_currency:
        if (
            command.valuation_amount_minor is not None
            or command.valuation_fx_rate is not None
            or command.valuation_fx_rate_date is not None
        ):
            raise LoanSecurityValidationError(
                "An amount, rate and rate date are needed only for a valuation in another currency."
            )
        return empty
    if guarantee:
        raise LoanSecurityValidationError(
            "A guarantee has a scope and a limit, not an asset value or a valuation."
        )
    if len(currency) != 3 or not currency.isalpha():
        raise LoanSecurityValidationError("Enter the valuation currency as a three-letter code.")
    if command.valuation_amount_minor is None or command.valuation_amount_minor < 0:
        raise LoanSecurityValidationError(f"Enter the value in {currency}.")
    rate = command.valuation_fx_rate
    if rate is None or rate <= 0:
        raise LoanSecurityValidationError(f"Enter the rate from {currency} to {loan_currency}.")
    if command.valuation_fx_rate_date is None:
        raise LoanSecurityValidationError("Enter the date of the rate.")
    converted = (Decimal(command.valuation_amount_minor) * rate).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return {
        "valuation_currency": currency,
        "valuation_amount_minor": int(command.valuation_amount_minor),
        "valuation_fx_rate": rate,
        "valuation_fx_rate_date": command.valuation_fx_rate_date,
        "converted_minor": int(converted),
    }


def ltv_basis_minor(loan: Loan) -> int:
    """F16: the sum of the values that count in the loan-to-value (not released, no guarantee)."""
    return sum(
        int(item.value_minor or 0)
        for item in loan.securities.filter(counts_in_ltv=True).exclude(
            status=LoanSecurityStatus.RELEASED
        )
        if not is_guarantee(item.security_type)
    )


def _main_security(loan: Loan) -> LoanSecurity | None:
    return (
        loan.securities.filter(is_main=True).first()
        or loan.securities.order_by("position", "created_at").first()
    )


def _sync_loan_summary(loan: Loan) -> None:
    """The main security gives the summary; the counted assets give the collateral value (C06)."""
    main = _main_security(loan)
    if main is None:
        return
    if not main.is_main:
        LoanSecurity.objects.filter(pk=main.pk).update(is_main=True)
    changed = []
    for name, new in (
        ("collateral_type", main.security_type),
        ("collateral_description", main.description),
        ("collateral_value_minor", ltv_basis_minor(loan)),
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
    if (
        current is not None
        and current.is_main
        and values["status"] == LoanSecurityStatus.RELEASED
        and loan.securities.exclude(pk=current.pk)
        .exclude(status=LoanSecurityStatus.RELEASED)
        .exists()
    ):
        raise LoanSecurityValidationError(
            "Choose another main security before you release this one."
        )
    if current is None:
        last = loan.securities.order_by("-position").first()
        current = LoanSecurity.objects.create(
            loan=loan,
            position=0 if last is None else last.position + 1,
            is_main=not loan.securities.filter(is_main=True).exists(),
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
                "counts_in_ltv": current.counts_in_ltv,
                "ltv_basis_minor": int(loan.collateral_value_minor),
            },
        )
    )
    current.refresh_from_db()
    return security_payload(current, _borrower_documents(loan))


@transaction.atomic
def set_main_loan_security(*, actor: Model, loan_id: str, security_id: str) -> list[dict[str, Any]]:
    """C06: the admin chooses the main security explicitly (the summary of the loan)."""
    _require_admin(actor)
    loan = _loan(loan_id)
    security = LoanSecurity.objects.select_for_update().filter(id=security_id, loan=loan).first()
    if security is None:
        raise LoanSecurityValidationError("This security does not exist for the loan.")
    if security.status == LoanSecurityStatus.RELEASED:
        raise LoanSecurityValidationError("A released security cannot be the main security.")
    previous = loan.securities.filter(is_main=True).exclude(pk=security.pk).first()
    if previous is not None:
        LoanSecurity.objects.filter(pk=previous.pk).update(is_main=False)
    LoanSecurity.objects.filter(pk=security.pk).update(is_main=True)
    _sync_loan_summary(loan)
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="loan.main_security_set",
            target_type="Loan",
            target_id=str(loan.id),
            metadata={
                "decision": "C06",
                "security_id": str(security.id),
                "previous_security_id": None if previous is None else str(previous.id),
            },
        )
    )
    documents = _borrower_documents(loan)
    return [security_payload(item, documents) for item in loan.securities.all()]


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
    """Move a security one place up or down in a draft (the display order). The main security,
    chosen apart (C06), gives the summary; after publication the order stays fixed."""
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
    """The loan form's collateral fields create or change the main security (C06); the loan's
    collateral value is then the sum of the counted assets again."""
    if loan.collateral_type == CollateralType.UNSECURED_EXCEPTION:
        return
    guarantee = is_guarantee(loan.collateral_type)
    value = (
        None if guarantee or not loan.collateral_value_minor else int(loan.collateral_value_minor)
    )
    first = _main_security(loan)
    actor_id = getattr(actor, "pk", None)
    if first is None:
        LoanSecurity.objects.create(
            loan=loan,
            position=0,
            is_main=True,
            security_type=loan.collateral_type,
            description=loan.collateral_description or "",
            value_minor=value,
            counts_in_ltv=loan.collateral_type in LTV_ASSET_SECURITY_TYPES and bool(value),
            created_by_admin_id=actor_id,
            updated_by_admin_id=actor_id,
        )
        _sync_loan_summary(loan)
        return
    changed = False
    type_changed = first.security_type != loan.collateral_type
    for name, new in (
        ("security_type", loan.collateral_type),
        ("description", loan.collateral_description or ""),
        ("value_minor", value),
    ):
        if getattr(first, name) != new:
            setattr(first, name, new)
            changed = True
    if type_changed:
        first.counts_in_ltv = loan.collateral_type in LTV_ASSET_SECURITY_TYPES and bool(value)
    if changed:
        if guarantee:
            first.prior_ranking_debt_minor = None
            first.valuation_date = None
            first.counts_in_ltv = False
        elif not value:
            first.counts_in_ltv = False
        first.updated_by_admin_id = actor_id
        first.save()
    _sync_loan_summary(loan)


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
