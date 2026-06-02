from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import Model, Sum

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryInvestmentOrderEvent,
    PrimaryInvestmentOrderEventType,
    PrimaryInvestmentOrderStatus,
)
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
    user_can_access_financial_features,
)
from backend.apps.platform_core.domain.money import Money, MoneyError, normalize_currency
from backend.apps.platform_core.domain.time import business_date, now_utc
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.selectors.settings import get_platform_setting_value
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event


class MarketplacePrimaryError(ValueError):
    pass


class MarketplacePrimaryAuthorizationError(MarketplacePrimaryError):
    pass


class MarketplacePrimaryValidationError(MarketplacePrimaryError):
    pass


MAX_IDEMPOTENCY_KEY_LENGTH = 160
PENDING_ORDER_CAP_DEFAULT = 50
ORDER_FINGERPRINT_METADATA_KEY = "request_fingerprint"
ALLOCATION_FINGERPRINT_METADATA_KEY = "allocation_request_fingerprint"
ALLOCATION_IDEMPOTENCY_METADATA_KEY = "allocation_idempotency_key"
RELEASE_FINGERPRINT_METADATA_KEY = "release_request_fingerprint"
RELEASE_IDEMPOTENCY_METADATA_KEY = "release_idempotency_key"


@dataclass(frozen=True, slots=True)
class CreatePrimaryInvestmentOrderCommand:
    actor: Model
    loan_id: str
    amount_minor: int
    idempotency_key: str
    notes: str = ""


@dataclass(frozen=True, slots=True)
class AllocatePrimaryInvestmentOrderCommand:
    actor: Model
    order_id: str
    document_acceptance_id: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ReleasePrimaryInvestmentOrderCommand:
    actor: Model
    order_id: str
    reason: str
    idempotency_key: str


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise MarketplacePrimaryValidationError(f"{label} is required.")
    return cleaned


def _clean_idempotency_key(value: str) -> str:
    key = _clean_required(value, "Idempotency key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise MarketplacePrimaryValidationError(
            f"Idempotency key cannot exceed {MAX_IDEMPOTENCY_KEY_LENGTH} characters."
        )
    return key


def _stable_json_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _enabled_currency(currency_code: str) -> Currency:
    try:
        code = normalize_currency(currency_code)
    except MoneyError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc
    currency = Currency.objects.filter(code=code, is_enabled=True).first()
    if currency is None:
        raise MarketplacePrimaryValidationError(f"Currency is not enabled: {code}")
    return currency


def _validate_money(amount_minor: int, currency_code: str, label: str) -> int:
    try:
        Money(amount_minor, currency_code)
    except MoneyError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc
    if amount_minor <= 0:
        raise MarketplacePrimaryValidationError(f"{label} must be positive.")
    return amount_minor


def _require_investor_financial_access(actor: Model) -> None:
    if not user_can_access_financial_features(actor):
        raise MarketplacePrimaryAuthorizationError(
            "Investor account cannot access primary-market investment features."
        )


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise MarketplacePrimaryAuthorizationError(
            "Only an active admin can manage primary-market orders."
        )


def _actor_account_type(actor: Model) -> str:
    return str(getattr(actor, "account_type", ""))


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def _loan_for_update(loan_id: str) -> Model:
    loan_model = _model("loans", "Loan")
    loan = cast(Model | None, loan_model.objects.select_for_update().filter(id=loan_id).first())
    if loan is None:
        raise MarketplacePrimaryValidationError("Loan does not exist.")
    return loan


def _loan_for_read(loan_id: str) -> Model:
    loan_model = _model("loans", "Loan")
    loan = cast(Model | None, loan_model.objects.filter(id=loan_id).first())
    if loan is None:
        raise MarketplacePrimaryValidationError("Loan does not exist.")
    return loan


def _assert_published_loan_open(loan: Model) -> None:
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) != "published":
        raise MarketplacePrimaryValidationError("Loan is not published for investment.")
    if business_date(now_utc()) > loan_ref.funding_deadline:
        raise MarketplacePrimaryValidationError("Loan funding deadline has passed.")


def _loan_remaining_capacity_minor(loan: Model) -> int:
    loan_ref = cast(Any, loan)
    return int(loan_ref.principal_minor) - int(loan_ref.committed_principal_minor)


def _minimum_investment_minor(currency_code: str) -> int:
    configured = get_platform_setting_value(
        "investment.minimum_by_currency",
        {"CHF": 100000, "EUR": 100000},
    )
    if isinstance(configured, dict):
        value = configured.get(currency_code)
        if type(value) is int:
            return value
    return 100000


def _pending_order_cap() -> int:
    value = get_platform_setting_value("investment.pending_order_cap", PENDING_ORDER_CAP_DEFAULT)
    if type(value) is int and value > 0:
        return value
    return PENDING_ORDER_CAP_DEFAULT


def _assert_pending_order_cap(investor_user_id: str) -> None:
    pending_count = PrimaryInvestmentOrder.objects.filter(
        investor_user_id=investor_user_id,
        status=PrimaryInvestmentOrderStatus.PENDING,
    ).count()
    if pending_count >= _pending_order_cap():
        raise MarketplacePrimaryValidationError("Investor has too many pending orders.")


def _order_request_fingerprint(
    command: CreatePrimaryInvestmentOrderCommand,
    *,
    investor_user_id: str,
    currency_code: str,
    amount_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "investor_user_id": investor_user_id,
            "loan_id": str(command.loan_id),
            "amount_minor": amount_minor,
            "currency": currency_code,
            "notes": command.notes.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _allocation_request_fingerprint(
    command: AllocatePrimaryInvestmentOrderCommand,
    *,
    order: PrimaryInvestmentOrder,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "order_id": str(order.id),
            "investor_user_id": str(order.investor_user_id),
            "loan_id": str(order.loan_id),
            "requested_amount_minor": order.requested_amount_minor,
            "document_acceptance_id": str(command.document_acceptance_id),
            "idempotency_key": idempotency_key,
        }
    )


def _release_request_fingerprint(
    command: ReleasePrimaryInvestmentOrderCommand,
    *,
    order: PrimaryInvestmentOrder,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "order_id": str(order.id),
            "investor_user_id": str(order.investor_user_id),
            "loan_id": str(order.loan_id),
            "allocated_amount_minor": order.allocated_amount_minor,
            "reason": command.reason.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _existing_order_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> PrimaryInvestmentOrder | None:
    existing = PrimaryInvestmentOrder.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(ORDER_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise MarketplacePrimaryValidationError(
            "Idempotency key was already used for a different request."
        )
    return existing


def _record_order_event(
    *,
    order: PrimaryInvestmentOrder,
    actor: Model,
    event_type: PrimaryInvestmentOrderEventType,
    previous_status: str = "",
    new_status: str = "",
    note: str = "",
    metadata: dict[str, Any] | None = None,
) -> PrimaryInvestmentOrderEvent:
    return cast(
        PrimaryInvestmentOrderEvent,
        PrimaryInvestmentOrderEvent.objects.create(
            order=order,
            loan_id=order.loan_id,
            event_type=event_type,
            actor_user_id=actor.pk,
            actor_account_type=_actor_account_type(actor),
            previous_status=previous_status,
            new_status=new_status,
            note=note.strip(),
            metadata=metadata or {},
        ),
    )


def _record_audit_and_domain(
    *,
    actor: Model,
    action: str,
    event_type: str,
    order: PrimaryInvestmentOrder,
    metadata: dict[str, Any],
) -> None:
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action=action,
            target_type="PrimaryInvestmentOrder",
            target_id=str(order.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type=event_type,
            aggregate_type="PrimaryInvestmentOrder",
            aggregate_id=str(order.id),
            payload=metadata,
            idempotency_key=f"primary-order:{order.id}:{event_type}",
        )
    )


def _validate_primary_document_acceptance(
    *,
    acceptance_id: str,
    actor: Model,
    order: PrimaryInvestmentOrder,
) -> Model:
    acceptance_model = _model("documents", "DocumentAcceptanceEvidence")
    acceptance = cast(
        Model | None,
        acceptance_model.objects.filter(id=acceptance_id, user_id=actor.pk).first(),
    )
    if acceptance is None:
        raise MarketplacePrimaryValidationError("Document acceptance does not exist.")
    acceptance_ref = cast(Any, acceptance)
    if str(acceptance_ref.category) != "primary_market_investment":
        raise MarketplacePrimaryValidationError("Document acceptance category is not valid.")
    if str(acceptance_ref.context_type) != "primary_order":
        raise MarketplacePrimaryValidationError("Document acceptance context is not valid.")
    if str(acceptance_ref.context_id) != str(order.id):
        raise MarketplacePrimaryValidationError("Document acceptance does not match this order.")
    return acceptance


def _ledger_services() -> Any:
    return import_module("backend.apps.ledger.services")


@transaction.atomic
def create_primary_investment_order(
    command: CreatePrimaryInvestmentOrderCommand,
) -> PrimaryInvestmentOrder:
    _require_investor_financial_access(command.actor)
    investor_id = str(command.actor.pk)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    loan = _loan_for_update(command.loan_id)
    _assert_published_loan_open(loan)
    loan_ref = cast(Any, loan)
    currency = _enabled_currency(str(loan_ref.currency_id))
    amount_minor = _validate_money(command.amount_minor, currency.code, "Investment amount")
    minimum = _minimum_investment_minor(currency.code)
    if amount_minor < minimum:
        raise MarketplacePrimaryValidationError("Investment amount is below the launch minimum.")
    remaining_capacity = _loan_remaining_capacity_minor(loan)
    if remaining_capacity <= 0:
        raise MarketplacePrimaryValidationError("Loan has no remaining investment capacity.")
    if amount_minor > remaining_capacity:
        raise MarketplacePrimaryValidationError(
            "Investment amount exceeds remaining loan capacity."
        )
    request_fingerprint = _order_request_fingerprint(
        command,
        investor_user_id=investor_id,
        currency_code=currency.code,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_order_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    _assert_pending_order_cap(investor_id)
    metadata = {
        ORDER_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "remaining_capacity_at_order_minor": remaining_capacity,
    }
    try:
        order = PrimaryInvestmentOrder.objects.create(
            loan_id=loan_ref.id,
            investor_user_id=command.actor.pk,
            requested_amount_minor=amount_minor,
            currency=currency,
            created_by_user_id=command.actor.pk,
            notes=command.notes.strip(),
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
    except IntegrityError:
        existing_after_race = _existing_order_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    event_metadata = {
        "investor_user_id": investor_id,
        "loan_id": str(order.loan_id),
        "currency": currency.code,
        "requested_amount_minor": amount_minor,
    }
    _record_order_event(
        order=order,
        actor=command.actor,
        event_type=PrimaryInvestmentOrderEventType.CREATED,
        new_status=order.status,
        note=command.notes,
        metadata=event_metadata,
    )
    _record_audit_and_domain(
        actor=command.actor,
        action="marketplace_primary.order_created",
        event_type="PrimaryInvestmentOrderCreated",
        order=order,
        metadata=event_metadata,
    )
    return order


@transaction.atomic
def allocate_primary_order_from_balance(
    command: AllocatePrimaryInvestmentOrderCommand,
) -> PrimaryInvestmentOrder:
    _require_investor_financial_access(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    order = (
        PrimaryInvestmentOrder.objects.select_for_update()
        .filter(id=command.order_id, investor_user_id=command.actor.pk)
        .first()
    )
    if order is None:
        raise MarketplacePrimaryValidationError("Primary investment order does not exist.")
    allocation_fingerprint = _allocation_request_fingerprint(
        command,
        order=order,
        idempotency_key=idempotency_key,
    )
    metadata = dict(cast(dict[str, Any], order.metadata))
    if order.status in {
        PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED,
        PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED,
    }:
        if (
            metadata.get(ALLOCATION_IDEMPOTENCY_METADATA_KEY) == idempotency_key
            and metadata.get(ALLOCATION_FINGERPRINT_METADATA_KEY) == allocation_fingerprint
        ):
            return order
        raise MarketplacePrimaryValidationError("Primary investment order is already allocated.")
    if order.status != PrimaryInvestmentOrderStatus.PENDING:
        raise MarketplacePrimaryValidationError("Only pending orders can be allocated.")
    loan = _loan_for_update(str(order.loan_id))
    _assert_published_loan_open(loan)
    loan_ref = cast(Any, loan)
    if order.currency_id != str(loan_ref.currency_id):
        raise MarketplacePrimaryValidationError("Order currency does not match loan currency.")
    acceptance = _validate_primary_document_acceptance(
        acceptance_id=command.document_acceptance_id,
        actor=command.actor,
        order=order,
    )
    remaining_capacity = _loan_remaining_capacity_minor(loan)
    if remaining_capacity <= 0:
        previous_status = str(order.status)
        order.status = PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
        order.closed_at = now_utc()
        order.metadata = {
            **metadata,
            ALLOCATION_IDEMPOTENCY_METADATA_KEY: idempotency_key,
            ALLOCATION_FINGERPRINT_METADATA_KEY: allocation_fingerprint,
            "closed_reason": "No loan capacity remained at allocation time.",
        }
        order.save(update_fields=["status", "closed_at", "metadata", "updated_at"])
        _record_order_event(
            order=order,
            actor=command.actor,
            event_type=PrimaryInvestmentOrderEventType.CLOSED_NOT_INVESTED,
            previous_status=previous_status,
            new_status=order.status,
            metadata={"reason": "no_capacity_at_allocation"},
        )
        return order
    amount_to_allocate = min(order.requested_amount_minor, remaining_capacity)
    ledger = _ledger_services()
    try:
        reservation_result = ledger.reserve_investor_balance_for_investment(
            ledger.ReserveInvestmentBalanceCommand(
                actor=command.actor,
                investor_user_id=str(order.investor_user_id),
                loan_id=str(order.loan_id),
                amount_minor=amount_to_allocate,
                currency=order.currency_id,
                loan_funding_deadline=loan_ref.funding_deadline,
                source_type="primary_investment_order",
                source_id=str(order.id),
                idempotency_key=idempotency_key,
            )
        )
    except ledger.LedgerError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc
    previous_status = str(order.status)
    allocated_at = now_utc()
    order.status = (
        PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED
        if amount_to_allocate == order.requested_amount_minor
        else PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED
    )
    order.allocated_amount_minor = amount_to_allocate
    order.document_acceptance_id = cast(Any, acceptance).id
    order.reservation_journal_entry = reservation_result.journal_entry
    order.lot_allocations = reservation_result.lot_allocations
    order.allocated_at = allocated_at
    order.metadata = {
        **metadata,
        ALLOCATION_IDEMPOTENCY_METADATA_KEY: idempotency_key,
        ALLOCATION_FINGERPRINT_METADATA_KEY: allocation_fingerprint,
        "remaining_capacity_at_allocation_minor": remaining_capacity,
        "unallocated_requested_amount_minor": order.requested_amount_minor - amount_to_allocate,
    }
    order.save(
        update_fields=[
            "status",
            "allocated_amount_minor",
            "document_acceptance",
            "reservation_journal_entry",
            "lot_allocations",
            "allocated_at",
            "metadata",
            "updated_at",
        ]
    )
    loan_ref.committed_principal_minor = (
        int(loan_ref.committed_principal_minor) + amount_to_allocate
    )
    loan.save(update_fields=["committed_principal_minor", "updated_at"])
    event_metadata = {
        "investor_user_id": str(order.investor_user_id),
        "loan_id": str(order.loan_id),
        "currency": order.currency_id,
        "requested_amount_minor": order.requested_amount_minor,
        "allocated_amount_minor": amount_to_allocate,
        "reservation_journal_entry_id": str(reservation_result.journal_entry.id),
        "lot_allocations": reservation_result.lot_allocations,
    }
    _record_order_event(
        order=order,
        actor=command.actor,
        event_type=PrimaryInvestmentOrderEventType.BALANCE_ALLOCATED,
        previous_status=previous_status,
        new_status=order.status,
        metadata=event_metadata,
    )
    _record_audit_and_domain(
        actor=command.actor,
        action="marketplace_primary.order_balance_allocated",
        event_type="PrimaryInvestmentOrderBalanceAllocated",
        order=order,
        metadata=event_metadata,
    )
    return order


@transaction.atomic
def release_primary_order_balance(
    command: ReleasePrimaryInvestmentOrderCommand,
) -> PrimaryInvestmentOrder:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    reason = _clean_required(command.reason, "Release reason")
    order = PrimaryInvestmentOrder.objects.select_for_update().filter(id=command.order_id).first()
    if order is None:
        raise MarketplacePrimaryValidationError("Primary investment order does not exist.")
    release_fingerprint = _release_request_fingerprint(
        command,
        order=order,
        idempotency_key=idempotency_key,
    )
    metadata = dict(cast(dict[str, Any], order.metadata))
    if order.status == PrimaryInvestmentOrderStatus.BALANCE_RELEASED:
        if (
            metadata.get(RELEASE_IDEMPOTENCY_METADATA_KEY) == idempotency_key
            and metadata.get(RELEASE_FINGERPRINT_METADATA_KEY) == release_fingerprint
        ):
            return order
        raise MarketplacePrimaryValidationError("Primary investment order is already released.")
    if order.status == PrimaryInvestmentOrderStatus.PENDING:
        previous_status = str(order.status)
        order.status = PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
        order.closed_at = now_utc()
        order.closed_by_admin_id = command.actor.pk
        order.admin_notes = reason
        order.metadata = {
            **metadata,
            RELEASE_IDEMPOTENCY_METADATA_KEY: idempotency_key,
            RELEASE_FINGERPRINT_METADATA_KEY: release_fingerprint,
        }
        order.save(
            update_fields=[
                "status",
                "closed_at",
                "closed_by_admin_id",
                "admin_notes",
                "metadata",
                "updated_at",
            ]
        )
        _record_order_event(
            order=order,
            actor=command.actor,
            event_type=PrimaryInvestmentOrderEventType.CLOSED_NOT_INVESTED,
            previous_status=previous_status,
            new_status=order.status,
            note=reason,
        )
        return order
    if order.status not in {
        PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED,
        PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED,
    }:
        raise MarketplacePrimaryValidationError(
            "Order balance cannot be released from this status."
        )
    if order.reservation_journal_entry is None:
        raise MarketplacePrimaryValidationError("Order has no reservation journal to release.")
    loan = _loan_for_update(str(order.loan_id))
    ledger = _ledger_services()
    try:
        release_result = ledger.release_investor_balance_investment_reservation(
            ledger.ReleaseInvestmentBalanceReservationCommand(
                actor=command.actor,
                investor_user_id=str(order.investor_user_id),
                loan_id=str(order.loan_id),
                amount_minor=order.allocated_amount_minor,
                currency=order.currency_id,
                source_type="primary_investment_order",
                source_id=str(order.id),
                reservation_journal_entry_id=str(order.reservation_journal_entry_id),
                lot_allocations=list(cast(list[dict[str, Any]], order.lot_allocations)),
                reason=reason,
                idempotency_key=idempotency_key,
            )
        )
    except ledger.LedgerError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc
    previous_status = str(order.status)
    order.status = PrimaryInvestmentOrderStatus.BALANCE_RELEASED
    order.release_journal_entry = release_result.journal_entry
    order.released_at = now_utc()
    order.closed_by_admin_id = command.actor.pk
    order.admin_notes = reason
    order.metadata = {
        **metadata,
        RELEASE_IDEMPOTENCY_METADATA_KEY: idempotency_key,
        RELEASE_FINGERPRINT_METADATA_KEY: release_fingerprint,
    }
    order.save(
        update_fields=[
            "status",
            "release_journal_entry",
            "released_at",
            "closed_by_admin_id",
            "admin_notes",
            "metadata",
            "updated_at",
        ]
    )
    loan_ref = cast(Any, loan)
    committed = int(loan_ref.committed_principal_minor) - order.allocated_amount_minor
    loan_ref.committed_principal_minor = max(0, committed)
    loan.save(update_fields=["committed_principal_minor", "updated_at"])
    event_metadata = {
        "investor_user_id": str(order.investor_user_id),
        "loan_id": str(order.loan_id),
        "currency": order.currency_id,
        "released_amount_minor": order.allocated_amount_minor,
        "release_journal_entry_id": str(release_result.journal_entry.id),
        "reason": reason,
    }
    _record_order_event(
        order=order,
        actor=command.actor,
        event_type=PrimaryInvestmentOrderEventType.BALANCE_RELEASED,
        previous_status=previous_status,
        new_status=order.status,
        note=reason,
        metadata=event_metadata,
    )
    _record_audit_and_domain(
        actor=command.actor,
        action="marketplace_primary.order_balance_released",
        event_type="PrimaryInvestmentOrderBalanceReleased",
        order=order,
        metadata=event_metadata,
    )
    return order


def loan_funding_progress(loan_id: str) -> dict[str, Any]:
    loan = _loan_for_read(loan_id)
    loan_ref = cast(Any, loan)
    committed = int(loan_ref.committed_principal_minor)
    principal = int(loan_ref.principal_minor)
    return {
        "loan_id": str(loan_ref.id),
        "currency": str(loan_ref.currency_id),
        "principal_minor": principal,
        "committed_principal_minor": committed,
        "remaining_capacity_minor": max(0, principal - committed),
    }


def public_marketplace_listing_payload(loan: Model) -> dict[str, Any]:
    loan_ref = cast(Any, loan)
    progress = loan_funding_progress(str(loan_ref.id))
    return {
        **progress,
        "title": str(loan_ref.title),
        "purpose": str(loan_ref.purpose),
        "collateral_type": str(loan_ref.collateral_type),
        "interest_rate_bps": int(loan_ref.interest_rate_bps),
        "term_months": int(loan_ref.term_months),
        "risk_rating": str(loan_ref.risk_rating),
        "funding_deadline": loan_ref.funding_deadline,
        "status": str(loan_ref.status),
    }


def full_marketplace_listing_payload(loan: Model) -> dict[str, Any]:
    loan_ref = cast(Any, loan)
    payload = public_marketplace_listing_payload(loan)
    payload.update(
        {
            "borrower_id": str(loan_ref.borrower_id),
            "investor_summary": str(loan_ref.investor_summary),
            "purpose_description": str(loan_ref.purpose_description),
            "collateral_value_minor": int(loan_ref.collateral_value_minor),
            "collateral_description": str(loan_ref.collateral_description),
            "ltv_bps": loan_ref.ltv_bps,
            "ltv_warnings": loan_ref.ltv_warnings,
            "repayment_type": str(loan_ref.repayment_type),
            "first_payment_date": loan_ref.first_payment_date,
            "schedule_version": int(loan_ref.schedule_version),
        }
    )
    return payload


def list_public_marketplace_loans(*, limit: int = 100) -> list[dict[str, Any]]:
    loan_model = _model("loans", "Loan")
    loans = loan_model.objects.filter(status="published").order_by("funding_deadline", "id")[
        :limit
    ]
    return [public_marketplace_listing_payload(cast(Model, loan)) for loan in loans]


def get_full_marketplace_loan(*, actor: Model, loan_id: str) -> dict[str, Any]:
    _require_investor_financial_access(actor)
    loan = _loan_for_read(loan_id)
    _assert_published_loan_open(loan)
    return full_marketplace_listing_payload(loan)


def allocated_primary_order_total_minor(*, loan_id: str) -> int:
    aggregate = PrimaryInvestmentOrder.objects.filter(
        loan_id=loan_id,
        status__in=[
            PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED,
            PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED,
        ],
    ).aggregate(total=Sum("allocated_amount_minor"))
    return int(aggregate["total"] or 0)
