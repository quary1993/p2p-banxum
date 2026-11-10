"""IP of Webby-Soft SRL. U33-DEC-20: the structured part of the credit file kept on the borrower.

- Financial years: the figures of each year, entered once from the financial statements (one
  source). Totals are what investors see; optional details must add up to the totals. Nothing is
  calculated into the history and no projection is stored.
- Existing debt: each facility explained from the documents, at a date.
- Library: metadata of the borrower documents (category, date or period, issuer, version, status).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from django.db import transaction
from django.db.models import Model

from backend.apps.entities.models import (
    FINANCIAL_YEAR_AMOUNT_FIELDS,
    BorrowerDebtFacility,
    BorrowerDocument,
    BorrowerEntity,
    BorrowerFinancialYear,
)
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event

SUPPORTED_CURRENCIES = frozenset({"CHF", "EUR"})
# Expenses and debts that are stored as positive amounts.
NOT_NEGATIVE_FIELDS = frozenset(FINANCIAL_YEAR_AMOUNT_FIELDS) - {
    "operating_profit_minor",
    "profit_before_tax_minor",
    "net_profit_minor",
    "equity_minor",
    "income_tax_minor",
}


class CreditFileError(RuntimeError):
    pass


class CreditFileAuthorizationError(CreditFileError):
    pass


class CreditFileValidationError(CreditFileError):
    pass


def _require_admin(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise CreditFileAuthorizationError("Only an active admin can edit the credit file.")


def _borrower(borrower_id: str) -> BorrowerEntity:
    borrower = BorrowerEntity.objects.filter(id=borrower_id).first()
    if borrower is None:
        raise CreditFileValidationError("Borrower does not exist.")
    return borrower


def _source_document(borrower: BorrowerEntity, document_id: str | None) -> BorrowerDocument | None:
    if not document_id:
        return None
    document = BorrowerDocument.objects.filter(id=document_id, borrower=borrower).first()
    if document is None:
        raise CreditFileValidationError("The source document is not a document of this borrower.")
    return document


def _audit(actor: Model, action: str, borrower: BorrowerEntity, metadata: dict[str, Any]) -> None:
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action=action,
            target_type="BorrowerEntity",
            target_id=str(borrower.id),
            metadata={"decision": "U33-DEC-20", **metadata},
        )
    )


# Financial years


@dataclass(frozen=True, slots=True)
class SaveFinancialYearCommand:
    actor: Model
    borrower_id: str
    year: int
    period_end: date
    currency: str
    amounts: dict[str, int | None] = field(default_factory=dict)
    source_document_id: str | None = None
    financial_year_id: str | None = None


def _sum_matches(total: int | None, parts: list[int | None]) -> bool:
    """True when the total is missing, a part is missing, or the parts add up to the total."""
    if total is None or any(part is None for part in parts):
        return True
    return sum(int(part or 0) for part in parts) == total


def _check_financial_consistency(amounts: dict[str, int | None]) -> None:
    get = amounts.get
    revenue = get("revenue_minor")
    costs = [
        get("materials_costs_minor"),
        get("staff_costs_minor"),
        get("other_operating_costs_minor"),
        get("depreciation_minor"),
    ]
    operating = get("operating_profit_minor")
    if revenue is not None and operating is not None and all(cost is not None for cost in costs):
        if revenue - sum(int(cost or 0) for cost in costs) != operating:
            raise CreditFileValidationError(
                "Revenue less the operating costs does not give the operating profit."
            )
    before_tax = get("profit_before_tax_minor")
    interest = get("interest_expense_minor")
    if operating is not None and interest is not None and before_tax is not None:
        if operating - interest != before_tax:
            raise CreditFileValidationError(
                "Operating profit less the interest expense does not give the profit before tax."
            )
    net = get("net_profit_minor")
    tax = get("income_tax_minor")
    if before_tax is not None and tax is not None and net is not None and before_tax - tax != net:
        raise CreditFileValidationError(
            "Profit before tax less the income tax does not give the net profit."
        )
    if not _sum_matches(
        get("current_assets_minor"),
        [
            get("cash_minor"),
            get("trade_receivables_minor"),
            get("inventories_minor"),
            get("other_current_assets_minor"),
        ],
    ):
        raise CreditFileValidationError("The current assets do not add up.")
    if not _sum_matches(
        get("total_assets_minor"),
        [
            get("current_assets_minor"),
            get("property_plant_equipment_minor"),
            get("other_non_current_assets_minor"),
        ],
    ):
        raise CreditFileValidationError("The total assets do not add up.")
    if not _sum_matches(
        get("financial_debt_minor"),
        [get("current_financial_debt_minor"), get("non_current_financial_debt_minor")],
    ):
        raise CreditFileValidationError("The financial debt does not add up.")
    total_assets = get("total_assets_minor")
    equity = get("equity_minor")
    if total_assets is not None and equity is not None:
        liabilities = total_assets - equity
        if not _sum_matches(
            liabilities,
            [
                get("financial_debt_minor"),
                get("trade_payables_minor"),
                get("other_operating_liabilities_minor"),
            ],
        ):
            raise CreditFileValidationError(
                "Financial debt and operating liabilities do not equal total assets less equity."
            )


@transaction.atomic
def save_financial_year(command: SaveFinancialYearCommand) -> dict[str, Any]:
    _require_admin(command.actor)
    borrower = _borrower(command.borrower_id)
    currency = command.currency.strip().upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise CreditFileValidationError("The currency must be CHF or EUR.")
    if not 1900 <= command.year <= 2100:
        raise CreditFileValidationError("The financial year is not plausible.")
    if command.period_end.year not in {command.year, command.year + 1}:
        raise CreditFileValidationError(
            "The period end must fall in or just after the financial year."
        )
    unknown = set(command.amounts) - set(FINANCIAL_YEAR_AMOUNT_FIELDS)
    if unknown:
        raise CreditFileValidationError(f"Unknown figures: {', '.join(sorted(unknown))}.")
    amounts = {name: command.amounts.get(name) for name in FINANCIAL_YEAR_AMOUNT_FIELDS}
    for name in NOT_NEGATIVE_FIELDS:
        value = amounts[name]
        if value is not None and value < 0:
            raise CreditFileValidationError(
                "Costs, assets and debts are entered as positive amounts."
            )
    _check_financial_consistency(amounts)
    source = _source_document(borrower, command.source_document_id)
    if command.financial_year_id:
        row = (
            BorrowerFinancialYear.objects.select_for_update()
            .filter(id=command.financial_year_id, borrower=borrower)
            .first()
        )
        if row is None:
            raise CreditFileValidationError("This financial year does not exist for the borrower.")
    else:
        row = BorrowerFinancialYear(borrower=borrower)
    duplicate = BorrowerFinancialYear.objects.filter(borrower=borrower, year=command.year)
    if row.pk:
        duplicate = duplicate.exclude(pk=row.pk)
    if duplicate.exists():
        raise CreditFileValidationError("This financial year is already recorded.")
    row.year = command.year
    row.period_end = command.period_end
    row.currency = currency
    for name, value in amounts.items():
        setattr(row, name, value)
    row.source_document = source
    row.updated_by_admin_id = command.actor.pk
    row.save()
    _audit(command.actor, "borrower.financial_year_saved", borrower, {"year": command.year})
    return financial_year_payload(row)


@transaction.atomic
def remove_financial_year(*, actor: Model, borrower_id: str, financial_year_id: str) -> None:
    _require_admin(actor)
    borrower = _borrower(borrower_id)
    row = BorrowerFinancialYear.objects.filter(id=financial_year_id, borrower=borrower).first()
    if row is None:
        raise CreditFileValidationError("This financial year does not exist for the borrower.")
    year = row.year
    row.delete()
    _audit(actor, "borrower.financial_year_removed", borrower, {"year": year})


def financial_year_payload(row: BorrowerFinancialYear) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(row.id),
        "year": row.year,
        "period_end": row.period_end,
        "currency": row.currency,
        "source_document": (
            {"id": str(row.source_document_id), "display_name": row.source_document.display_name}
            if row.source_document_id and row.source_document is not None
            else None
        ),
    }
    for name in FINANCIAL_YEAR_AMOUNT_FIELDS:
        payload[name] = getattr(row, name)
    return payload


def list_financial_years(*, actor: Model, borrower_id: str) -> list[dict[str, Any]]:
    _require_admin(actor)
    borrower = _borrower(borrower_id)
    return [
        financial_year_payload(row)
        for row in borrower.financial_years.select_related("source_document")
    ]


# Existing debt


@dataclass(frozen=True, slots=True)
class SaveDebtFacilityCommand:
    actor: Model
    borrower_id: str
    facility_type: str
    currency: str
    balance_minor: int
    as_at: date
    current_portion_minor: int | None = None
    security_description: str = ""
    source_document_id: str | None = None
    facility_id: str | None = None


def debt_facility_payload(row: BorrowerDebtFacility) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "position": row.position,
        "facility_type": row.facility_type,
        "currency": row.currency,
        "balance_minor": row.balance_minor,
        "current_portion_minor": row.current_portion_minor,
        "non_current_portion_minor": (
            row.balance_minor - row.current_portion_minor
            if row.current_portion_minor is not None
            else None
        ),
        "security_description": row.security_description,
        "as_at": row.as_at,
        "source_document": (
            {"id": str(row.source_document_id), "display_name": row.source_document.display_name}
            if row.source_document_id and row.source_document is not None
            else None
        ),
    }


@transaction.atomic
def save_debt_facility(command: SaveDebtFacilityCommand) -> dict[str, Any]:
    _require_admin(command.actor)
    borrower = _borrower(command.borrower_id)
    facility_type = command.facility_type.strip()
    if not facility_type:
        raise CreditFileValidationError("Name the facility.")
    currency = command.currency.strip().upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise CreditFileValidationError("The currency must be CHF or EUR.")
    if command.balance_minor < 0:
        raise CreditFileValidationError("The balance cannot be negative.")
    if command.current_portion_minor is not None and not (
        0 <= command.current_portion_minor <= command.balance_minor
    ):
        raise CreditFileValidationError(
            "The part due within a year must be between 0 and the balance."
        )
    source = _source_document(borrower, command.source_document_id)
    if command.facility_id:
        row = (
            BorrowerDebtFacility.objects.select_for_update()
            .filter(id=command.facility_id, borrower=borrower)
            .first()
        )
        if row is None:
            raise CreditFileValidationError("This facility does not exist for the borrower.")
    else:
        last = borrower.debt_facilities.order_by("-position").first()
        row = BorrowerDebtFacility(
            borrower=borrower, position=0 if last is None else last.position + 1
        )
    row.facility_type = facility_type
    row.currency = currency
    row.balance_minor = command.balance_minor
    row.current_portion_minor = command.current_portion_minor
    row.security_description = command.security_description.strip()
    row.as_at = command.as_at
    row.source_document = source
    row.updated_by_admin_id = command.actor.pk
    row.save()
    _audit(command.actor, "borrower.debt_facility_saved", borrower, {"facility_id": str(row.id)})
    return debt_facility_payload(row)


@transaction.atomic
def remove_debt_facility(*, actor: Model, borrower_id: str, facility_id: str) -> None:
    _require_admin(actor)
    borrower = _borrower(borrower_id)
    deleted, _ = BorrowerDebtFacility.objects.filter(id=facility_id, borrower=borrower).delete()
    if not deleted:
        raise CreditFileValidationError("This facility does not exist for the borrower.")
    _audit(actor, "borrower.debt_facility_removed", borrower, {"facility_id": str(facility_id)})


def list_debt_facilities(*, actor: Model, borrower_id: str) -> list[dict[str, Any]]:
    _require_admin(actor)
    borrower = _borrower(borrower_id)
    return [
        debt_facility_payload(row)
        for row in borrower.debt_facilities.select_related("source_document")
    ]


# Library metadata


@dataclass(frozen=True, slots=True)
class DocumentMetadataCommand:
    actor: Model
    borrower_id: str
    document_id: str
    category: str = ""
    document_date: date | None = None
    period_label: str = ""
    issuer: str = ""
    version: str = ""
    document_status: str = ""


@transaction.atomic
def set_document_metadata(command: DocumentMetadataCommand) -> BorrowerDocument:
    _require_admin(command.actor)
    borrower = _borrower(command.borrower_id)
    document = (
        BorrowerDocument.objects.select_for_update()
        .filter(id=command.document_id, borrower=borrower)
        .first()
    )
    if document is None:
        raise CreditFileValidationError("This document does not exist for the borrower.")
    document.category = command.category.strip()
    document.document_date = command.document_date
    document.period_label = command.period_label.strip()
    document.issuer = command.issuer.strip()
    document.version = command.version.strip()
    document.document_status = command.document_status.strip()
    document.save(
        update_fields=[
            "category",
            "document_date",
            "period_label",
            "issuer",
            "version",
            "document_status",
            "updated_at",
        ]
    )
    _audit(
        command.actor, "borrower.document_metadata_set", borrower, {"document_id": str(document.id)}
    )
    return document


# For investors


def _visible_source(payload: dict[str, Any], row: Any) -> dict[str, Any]:
    if row.source_document_id and not row.source_document.investor_visible:
        payload["source_document"] = None
    return payload


def investor_credit_file(borrower: BorrowerEntity) -> dict[str, Any]:
    """The financial years (oldest first) and the existing debt of a borrower, for investors.

    A source document is named only when investors can see it.
    """
    years = borrower.financial_years.select_related("source_document").order_by("year")
    facilities = borrower.debt_facilities.select_related("source_document")
    return {
        "financial_years": [_visible_source(financial_year_payload(row), row) for row in years],
        "debt_facilities": [_visible_source(debt_facility_payload(row), row) for row in facilities],
    }
