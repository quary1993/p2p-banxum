from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from backend.apps.entities.models import (
    BorrowerDocument,
    BorrowerDocumentType,
    BorrowerEntity,
    BorrowerEntityEvent,
    BorrowerEntityEventType,
    BorrowerEntityType,
    BorrowerKybStatus,
)
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.models import StoredFile
from backend.apps.platform_core.models.files import FileScanStatus
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event


class EntitiesError(ValueError):
    pass


class BorrowerAuthorizationError(EntitiesError):
    pass


class BorrowerValidationError(EntitiesError):
    pass


NONNEGATIVE_FINANCIAL_FIELDS = frozenset(
    {
        "assets_minor",
        "liabilities_minor",
        "revenue_last_year_minor",
    }
)
FINANCIAL_FIELDS = frozenset(
    {
        "assets_minor",
        "liabilities_minor",
        "revenue_last_year_minor",
        "profit_last_year_minor",
    }
)


def _actor_account_type(actor: Model) -> str:
    return str(getattr(actor, "account_type", ""))


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise BorrowerAuthorizationError("Only an active admin can manage borrower entities.")


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise BorrowerValidationError(f"{label} is required.")
    return cleaned


def _optional_clean(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()


def _entity_type(value: str) -> BorrowerEntityType:
    try:
        return BorrowerEntityType(value)
    except ValueError as exc:
        raise BorrowerValidationError(f"Invalid borrower entity type: {value}") from exc


def _kyb_status(value: str) -> BorrowerKybStatus:
    try:
        return BorrowerKybStatus(value)
    except ValueError as exc:
        raise BorrowerValidationError(f"Invalid borrower KYB status: {value}") from exc


def _document_type(value: str) -> BorrowerDocumentType:
    try:
        return BorrowerDocumentType(value)
    except ValueError as exc:
        raise BorrowerValidationError(f"Invalid borrower document type: {value}") from exc


def _validate_year_founded(year_founded: int) -> int:
    current_year = timezone.localdate().year
    if year_founded < 1800 or year_founded > current_year:
        raise BorrowerValidationError("Year founded must be between 1800 and the current year.")
    return year_founded


def _clean_currency(currency: str) -> str:
    cleaned = currency.strip().upper()
    if cleaned and (len(cleaned) != 3 or not cleaned.isalpha()):
        raise BorrowerValidationError("Financials currency must be a 3-letter ISO code.")
    return cleaned


def _validate_financials(data: dict[str, Any]) -> None:
    has_financial_amount = False
    for field in FINANCIAL_FIELDS:
        amount = data.get(field)
        if amount is None:
            continue
        has_financial_amount = True
        if not isinstance(amount, int):
            raise BorrowerValidationError(f"{field} must be stored as integer minor units.")
        if field in NONNEGATIVE_FINANCIAL_FIELDS and amount < 0:
            raise BorrowerValidationError(f"{field} cannot be negative.")
    if has_financial_amount and not data.get("financials_currency"):
        raise BorrowerValidationError(
            "Financials currency is required when financial amounts are set."
        )


def _event_metadata_for_borrower(borrower: BorrowerEntity) -> dict[str, Any]:
    return {
        "legal_name": borrower.legal_name,
        "year_founded": borrower.year_founded,
        "entity_type": borrower.entity_type,
        "kyb_status": borrower.kyb_status,
        "compliance_hold": borrower.compliance_hold,
        "country": borrower.country,
    }


def _record_borrower_event(
    *,
    borrower: BorrowerEntity,
    actor: Model,
    event_type: BorrowerEntityEventType,
    previous_kyb_status: str = "",
    new_kyb_status: str = "",
    note: str = "",
    evidence_summary: str = "",
    metadata: dict[str, Any] | None = None,
) -> BorrowerEntityEvent:
    return cast(
        BorrowerEntityEvent,
        BorrowerEntityEvent.objects.create(
            borrower=borrower,
            event_type=event_type,
            actor_user_id=actor.pk,
            actor_account_type=_actor_account_type(actor),
            previous_kyb_status=previous_kyb_status,
            new_kyb_status=new_kyb_status,
            note=note.strip(),
            evidence_summary=evidence_summary.strip(),
            metadata=metadata or {},
        ),
    )


@dataclass(frozen=True, slots=True)
class CreateBorrowerEntityCommand:
    actor: Model
    legal_name: str
    year_founded: int
    entity_type: str = BorrowerEntityType.SWISS_COMPANY
    kyb_status: str = BorrowerKybStatus.PENDING
    compliance_hold: bool = False
    country: str = ""
    registration_number: str = ""
    registered_address: str = ""
    operating_address: str = ""
    industry_activity: str = ""
    ownership_structure: str = ""
    beneficial_owners: list[dict[str, Any]] | None = None
    directors_officers: list[dict[str, Any]] | None = None
    authorized_signatories: list[dict[str, Any]] | None = None
    bank_account_details: dict[str, Any] | None = None
    financials_currency: str = ""
    assets_minor: int | None = None
    liabilities_minor: int | None = None
    revenue_last_year_minor: int | None = None
    profit_last_year_minor: int | None = None
    note: str = ""
    evidence_summary: str = ""


@dataclass(frozen=True, slots=True)
class UpdateBorrowerEntityCommand:
    actor: Model
    borrower_id: str
    legal_name: str | None = None
    year_founded: int | None = None
    entity_type: str | None = None
    kyb_status: str | None = None
    compliance_hold: bool | None = None
    country: str | None = None
    registration_number: str | None = None
    registered_address: str | None = None
    operating_address: str | None = None
    industry_activity: str | None = None
    ownership_structure: str | None = None
    beneficial_owners: list[dict[str, Any]] | None = None
    directors_officers: list[dict[str, Any]] | None = None
    authorized_signatories: list[dict[str, Any]] | None = None
    bank_account_details: dict[str, Any] | None = None
    financials_currency: str | None = None
    assets_minor: int | None = None
    liabilities_minor: int | None = None
    revenue_last_year_minor: int | None = None
    profit_last_year_minor: int | None = None
    clear_assets: bool = False
    clear_liabilities: bool = False
    clear_revenue_last_year: bool = False
    clear_profit_last_year: bool = False
    note: str = ""
    evidence_summary: str = ""


@dataclass(frozen=True, slots=True)
class AddBorrowerDocumentCommand:
    actor: Model
    borrower_id: str
    stored_file_id: str
    document_type: str
    display_name: str
    description: str = ""
    investor_visible: bool = False
    note: str = ""


@transaction.atomic
def create_borrower_entity(command: CreateBorrowerEntityCommand) -> BorrowerEntity:
    _require_admin_actor(command.actor)
    financials_currency = _clean_currency(command.financials_currency)
    financial_data: dict[str, Any] = {
        "financials_currency": financials_currency,
        "assets_minor": command.assets_minor,
        "liabilities_minor": command.liabilities_minor,
        "revenue_last_year_minor": command.revenue_last_year_minor,
        "profit_last_year_minor": command.profit_last_year_minor,
    }
    _validate_financials(financial_data)
    borrower = BorrowerEntity.objects.create(
        legal_name=_clean_required(command.legal_name, "Legal name"),
        year_founded=_validate_year_founded(command.year_founded),
        entity_type=_entity_type(command.entity_type),
        kyb_status=_kyb_status(command.kyb_status),
        compliance_hold=command.compliance_hold,
        country=command.country.strip(),
        registration_number=command.registration_number.strip(),
        registered_address=command.registered_address.strip(),
        operating_address=command.operating_address.strip(),
        industry_activity=command.industry_activity.strip(),
        ownership_structure=command.ownership_structure.strip(),
        beneficial_owners=command.beneficial_owners or [],
        directors_officers=command.directors_officers or [],
        authorized_signatories=command.authorized_signatories or [],
        bank_account_details=command.bank_account_details or {},
        financials_currency=financials_currency,
        assets_minor=command.assets_minor,
        liabilities_minor=command.liabilities_minor,
        revenue_last_year_minor=command.revenue_last_year_minor,
        profit_last_year_minor=command.profit_last_year_minor,
        created_by_admin_id=command.actor.pk,
    )
    metadata = _event_metadata_for_borrower(borrower)
    _record_borrower_event(
        borrower=borrower,
        actor=command.actor,
        event_type=BorrowerEntityEventType.CREATED,
        new_kyb_status=borrower.kyb_status,
        note=command.note,
        evidence_summary=command.evidence_summary,
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="borrower.created",
            target_type="BorrowerEntity",
            target_id=str(borrower.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="BorrowerEntityCreated",
            aggregate_type="BorrowerEntity",
            aggregate_id=str(borrower.id),
            payload=metadata,
            idempotency_key=f"borrower:{borrower.id}:created",
        )
    )
    return borrower


def _set_if_changed(
    *,
    borrower: BorrowerEntity,
    field: str,
    value: Any,
    changes: dict[str, dict[str, str]],
) -> None:
    previous = getattr(borrower, field)
    if previous != value:
        changes[field] = {"previous": str(previous or ""), "new": str(value or "")}
        setattr(borrower, field, value)


@transaction.atomic
def update_borrower_entity(command: UpdateBorrowerEntityCommand) -> BorrowerEntity:
    _require_admin_actor(command.actor)
    borrower = BorrowerEntity.objects.select_for_update().filter(id=command.borrower_id).first()
    if borrower is None:
        raise BorrowerValidationError("Borrower entity does not exist.")

    changes: dict[str, dict[str, str]] = {}
    previous_kyb_status = borrower.kyb_status
    if command.legal_name is not None:
        _set_if_changed(
            borrower=borrower,
            field="legal_name",
            value=_clean_required(command.legal_name, "Legal name"),
            changes=changes,
        )
    if command.year_founded is not None:
        _set_if_changed(
            borrower=borrower,
            field="year_founded",
            value=_validate_year_founded(command.year_founded),
            changes=changes,
        )
    if command.entity_type is not None:
        _set_if_changed(
            borrower=borrower,
            field="entity_type",
            value=_entity_type(command.entity_type),
            changes=changes,
        )
    if command.kyb_status is not None:
        _set_if_changed(
            borrower=borrower,
            field="kyb_status",
            value=_kyb_status(command.kyb_status),
            changes=changes,
        )
    if command.compliance_hold is not None:
        _set_if_changed(
            borrower=borrower,
            field="compliance_hold",
            value=command.compliance_hold,
            changes=changes,
        )
    for field_name in (
        "country",
        "registration_number",
        "registered_address",
        "operating_address",
        "industry_activity",
        "ownership_structure",
    ):
        command_value = _optional_clean(cast(str | None, getattr(command, field_name)))
        if command_value is not None:
            _set_if_changed(
                borrower=borrower,
                field=field_name,
                value=command_value,
                changes=changes,
            )
    for field_name in (
        "beneficial_owners",
        "directors_officers",
        "authorized_signatories",
        "bank_account_details",
    ):
        command_value = getattr(command, field_name)
        if command_value is not None:
            _set_if_changed(
                borrower=borrower,
                field=field_name,
                value=command_value,
                changes=changes,
            )
    if command.financials_currency is not None:
        _set_if_changed(
            borrower=borrower,
            field="financials_currency",
            value=_clean_currency(command.financials_currency),
            changes=changes,
        )
    financial_clear_map = {
        "assets_minor": command.clear_assets,
        "liabilities_minor": command.clear_liabilities,
        "revenue_last_year_minor": command.clear_revenue_last_year,
        "profit_last_year_minor": command.clear_profit_last_year,
    }
    for field_name, should_clear in financial_clear_map.items():
        if should_clear:
            _set_if_changed(borrower=borrower, field=field_name, value=None, changes=changes)
        else:
            command_value = getattr(command, field_name)
            if command_value is not None:
                _set_if_changed(
                    borrower=borrower,
                    field=field_name,
                    value=command_value,
                    changes=changes,
                )

    _validate_financials(
        {
            "financials_currency": borrower.financials_currency,
            "assets_minor": borrower.assets_minor,
            "liabilities_minor": borrower.liabilities_minor,
            "revenue_last_year_minor": borrower.revenue_last_year_minor,
            "profit_last_year_minor": borrower.profit_last_year_minor,
        }
    )
    if not changes:
        raise BorrowerValidationError("No borrower changes were provided.")
    if (
        "kyb_status" in changes
        and not command.note.strip()
        and not command.evidence_summary.strip()
    ):
        raise BorrowerValidationError("A note or evidence summary is required for KYB changes.")

    borrower.updated_by_admin_id = command.actor.pk
    borrower.save(
        update_fields=[
            "legal_name",
            "year_founded",
            "entity_type",
            "kyb_status",
            "compliance_hold",
            "country",
            "registration_number",
            "registered_address",
            "operating_address",
            "industry_activity",
            "ownership_structure",
            "beneficial_owners",
            "directors_officers",
            "authorized_signatories",
            "bank_account_details",
            "financials_currency",
            "assets_minor",
            "liabilities_minor",
            "revenue_last_year_minor",
            "profit_last_year_minor",
            "updated_by_admin_id",
            "updated_at",
        ]
    )
    event_type = (
        BorrowerEntityEventType.KYB_STATUS_CHANGED
        if "kyb_status" in changes
        else BorrowerEntityEventType.UPDATED
    )
    metadata = {"changes": changes}
    event = _record_borrower_event(
        borrower=borrower,
        actor=command.actor,
        event_type=event_type,
        previous_kyb_status=previous_kyb_status,
        new_kyb_status=borrower.kyb_status,
        note=command.note,
        evidence_summary=command.evidence_summary,
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="borrower.updated",
            target_type="BorrowerEntity",
            target_id=str(borrower.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="BorrowerEntityUpdated",
            aggregate_type="BorrowerEntity",
            aggregate_id=str(borrower.id),
            payload=metadata,
            idempotency_key=f"borrower:{borrower.id}:event:{event.id}",
        )
    )
    return borrower


@transaction.atomic
def add_borrower_document(command: AddBorrowerDocumentCommand) -> BorrowerDocument:
    _require_admin_actor(command.actor)
    borrower = BorrowerEntity.objects.filter(id=command.borrower_id).first()
    if borrower is None:
        raise BorrowerValidationError("Borrower entity does not exist.")
    stored_file = StoredFile.objects.filter(id=command.stored_file_id).first()
    if stored_file is None:
        raise BorrowerValidationError("Stored file does not exist.")
    document_type = _document_type(command.document_type)
    display_name = _clean_required(command.display_name, "Display name")
    document = BorrowerDocument.objects.create(
        borrower=borrower,
        stored_file=stored_file,
        document_type=document_type,
        display_name=display_name,
        description=command.description.strip(),
        investor_visible=command.investor_visible,
        created_by_admin_id=command.actor.pk,
        created_by_account_type=_actor_account_type(command.actor),
    )
    metadata = {
        "document_id": str(document.id),
        "stored_file_id": str(stored_file.id),
        "document_type": document.document_type,
        "investor_visible": document.investor_visible,
    }
    event = _record_borrower_event(
        borrower=borrower,
        actor=command.actor,
        event_type=BorrowerEntityEventType.DOCUMENT_ADDED,
        new_kyb_status=borrower.kyb_status,
        note=command.note,
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="borrower.document_added",
            target_type="BorrowerEntity",
            target_id=str(borrower.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="BorrowerDocumentAdded",
            aggregate_type="BorrowerEntity",
            aggregate_id=str(borrower.id),
            payload=metadata,
            idempotency_key=f"borrower:{borrower.id}:document:{event.id}",
        )
    )
    return document


def borrower_can_transact(borrower: BorrowerEntity) -> bool:
    return borrower.can_transact


def borrower_investor_disclosure(borrower: BorrowerEntity) -> dict[str, Any]:
    disclosure: dict[str, Any] = {
        "legal_name": borrower.legal_name,
        "year_founded": borrower.year_founded,
    }
    for field in (
        "country",
        "financials_currency",
        "assets_minor",
        "liabilities_minor",
        "revenue_last_year_minor",
        "profit_last_year_minor",
    ):
        value = getattr(borrower, field)
        if value not in {"", None}:
            disclosure[field] = value
    documents = []
    for document in borrower.documents.select_related("stored_file").filter(investor_visible=True):
        if document.stored_file.scan_status != FileScanStatus.CLEAN:
            continue
        documents.append(
            {
                "id": str(document.id),
                "document_type": document.document_type,
                "display_name": document.display_name,
                "description": document.description,
                "stored_file_id": str(document.stored_file_id),
            }
        )
    if documents:
        disclosure["documents"] = documents
    return disclosure
