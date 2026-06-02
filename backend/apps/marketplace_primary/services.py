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
    PrimaryLoanClose,
    PrimaryLoanCloseType,
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
CLOSE_FINGERPRINT_METADATA_KEY = "close_request_fingerprint"


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


@dataclass(frozen=True, slots=True)
class ClosePrimaryLoanFundingCommand:
    actor: Model
    loan_id: str
    reason: str
    investor_message: str
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


def _close_request_fingerprint(
    command: ClosePrimaryLoanFundingCommand,
    *,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "reason": command.reason.strip(),
            "investor_message": command.investor_message.strip(),
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


def _existing_close_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> PrimaryLoanClose | None:
    existing = PrimaryLoanClose.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(CLOSE_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise MarketplacePrimaryValidationError(
            "Idempotency key was already used for a different close request."
        )
    return cast(PrimaryLoanClose, existing)


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
        acceptance_model.objects.select_related("template", "template_version")
        .filter(id=acceptance_id, user_id=actor.pk)
        .first(),
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
    if str(acceptance_ref.template.current_published_version_id) != str(
        acceptance_ref.template_version_id
    ):
        raise MarketplacePrimaryValidationError("Document acceptance is no longer current.")
    return acceptance


def _ledger_services() -> Any:
    return import_module("backend.apps.ledger.services")


def _holdings_services() -> Any:
    return import_module("backend.apps.holdings.services")


def _loans_services() -> Any:
    return import_module("backend.apps.loans.services")


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
    if order.status == PrimaryInvestmentOrderStatus.CLOSED_INVESTED:
        raise MarketplacePrimaryValidationError("Closed loan orders cannot be released.")
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
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) != "published":
        raise MarketplacePrimaryValidationError("Closed loan orders cannot be released.")
    if int(loan_ref.committed_principal_minor) < order.allocated_amount_minor:
        raise MarketplacePrimaryValidationError("Loan committed principal would underflow.")
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
    committed = int(loan_ref.committed_principal_minor) - order.allocated_amount_minor
    loan_ref.committed_principal_minor = committed
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


def _allocated_orders_for_close(loan_id: str) -> list[PrimaryInvestmentOrder]:
    return list(
        PrimaryInvestmentOrder.objects.select_for_update()
        .filter(
            loan_id=loan_id,
            status__in=[
                PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED,
                PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED,
            ],
        )
        .order_by("allocated_at", "created_at", "id")
    )


def _pending_orders_for_close(loan_id: str) -> list[PrimaryInvestmentOrder]:
    return list(
        PrimaryInvestmentOrder.objects.select_for_update()
        .filter(loan_id=loan_id, status=PrimaryInvestmentOrderStatus.PENDING)
        .order_by("created_at", "id")
    )


def _record_loan_funding_closed_event(
    *,
    loan: Model,
    actor: Model,
    previous_status: str,
    new_status: str,
    close: PrimaryLoanClose,
    metadata: dict[str, Any],
) -> None:
    loan_ref = cast(Any, loan)
    loan_event_model = _model("loans", "LoanEvent")
    loan_event_model.objects.create(
        loan=loan,
        event_type="funding_closed",
        actor_user_id=actor.pk,
        actor_account_type=_actor_account_type(actor),
        previous_status=previous_status,
        new_status=new_status,
        note=close.reason,
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.funding_closed",
            target_type="Loan",
            target_id=str(loan_ref.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanFundingClosed",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=metadata,
            idempotency_key=f"loan:{loan_ref.id}:funding-closed",
        )
    )


@transaction.atomic
def close_primary_loan_funding(
    command: ClosePrimaryLoanFundingCommand,
) -> PrimaryLoanClose:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    reason = _clean_required(command.reason, "Close reason")
    close_fingerprint = _close_request_fingerprint(command, idempotency_key=idempotency_key)
    existing = _existing_close_for_idempotency(
        idempotency_key,
        expected_fingerprint=close_fingerprint,
    )
    if existing is not None:
        return existing
    if PrimaryLoanClose.objects.filter(loan_id=command.loan_id).exists():
        raise MarketplacePrimaryValidationError("Loan funding is already closed.")

    loan = _loan_for_update(command.loan_id)
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) != "published":
        raise MarketplacePrimaryValidationError("Only published loans can be closed.")
    if not bool(getattr(loan_ref.borrower, "can_transact", False)):
        raise MarketplacePrimaryValidationError(
            "Borrower KYB must be approved and free of compliance hold."
        )
    allocated_orders = _allocated_orders_for_close(str(loan_ref.id))
    if not allocated_orders:
        raise MarketplacePrimaryValidationError("Loan has no allocated investment orders to close.")
    accepted_principal = sum(order.allocated_amount_minor for order in allocated_orders)
    if accepted_principal <= 0:
        raise MarketplacePrimaryValidationError("Accepted funded principal must be positive.")
    if accepted_principal != int(loan_ref.committed_principal_minor):
        raise MarketplacePrimaryValidationError(
            "Allocated orders do not match the loan committed principal."
        )
    if accepted_principal > int(loan_ref.principal_minor):
        raise MarketplacePrimaryValidationError("Accepted funded principal exceeds loan principal.")

    close_type = (
        PrimaryLoanCloseType.FULL
        if accepted_principal == int(loan_ref.principal_minor)
        else PrimaryLoanCloseType.PARTIAL
    )
    investor_message = command.investor_message.strip()
    if close_type == PrimaryLoanCloseType.PARTIAL:
        if not investor_message:
            raise MarketplacePrimaryValidationError(
                "Investor message is required for partial loan close."
            )
        loans = _loans_services()
        loan = loans.update_loan(
            loans.UpdateLoanCommand(
                actor=command.actor,
                loan_id=str(loan_ref.id),
                principal_minor=accepted_principal,
                investor_message=investor_message,
                note=reason,
            )
        )
        loan_ref = cast(Any, loan)

    closed_at = now_utc()
    ledger = _ledger_services()
    try:
        ledger_result = ledger.close_primary_loan_funding(
            ledger.ClosePrimaryLoanFundingCommand(
                actor=command.actor,
                loan_id=str(loan_ref.id),
                borrower_id=str(loan_ref.borrower_id),
                accepted_principal_minor=accepted_principal,
                borrower_success_fee_bps=int(loan_ref.borrower_success_fee_bps),
                currency=str(loan_ref.currency_id),
                source_type="primary_loan_close",
                source_id=str(loan_ref.id),
                idempotency_key=idempotency_key,
                as_of=closed_at,
            )
        )
    except ledger.LedgerError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc

    pending_orders = _pending_orders_for_close(str(loan_ref.id))
    close_metadata = {
        CLOSE_FINGERPRINT_METADATA_KEY: close_fingerprint,
        "loan_id": str(loan_ref.id),
        "close_type": str(close_type),
        "currency": str(loan_ref.currency_id),
        "accepted_principal_minor": accepted_principal,
        "allocated_order_ids": [str(order.id) for order in allocated_orders],
        "pending_order_ids_closed_not_invested": [str(order.id) for order in pending_orders],
        "funding_close_journal_entry_id": str(ledger_result.journal_entry.id),
    }
    try:
        close = cast(
            PrimaryLoanClose,
            PrimaryLoanClose.objects.create(
                loan=cast(Any, loan),
                close_type=close_type,
                accepted_principal_minor=accepted_principal,
                currency_id=str(loan_ref.currency_id),
                allocated_order_count=len(allocated_orders),
                closed_not_invested_order_count=len(pending_orders),
                borrower_success_fee_bps=int(loan_ref.borrower_success_fee_bps),
                borrower_success_fee_minor=ledger_result.borrower_success_fee_minor,
                borrower_disbursement_payable_minor=(
                    ledger_result.borrower_disbursement_payable_minor
                ),
                funding_close_journal_entry=ledger_result.journal_entry,
                created_by_admin_id=command.actor.pk,
                closed_at=closed_at,
                reason=reason,
                investor_message=investor_message,
                metadata=close_metadata,
                idempotency_key=idempotency_key,
            ),
        )
    except IntegrityError:
        existing_after_race = _existing_close_for_idempotency(
            idempotency_key,
            expected_fingerprint=close_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    holdings = _holdings_services()
    holding_ids: list[str] = []
    for order in allocated_orders:
        holding = holdings.create_primary_market_holding(
            holdings.CreatePrimaryMarketHoldingCommand(
                actor=command.actor,
                investor_user_id=str(order.investor_user_id),
                loan_id=str(loan_ref.id),
                primary_order_id=str(order.id),
                principal_minor=order.allocated_amount_minor,
                accepted_loan_principal_minor=accepted_principal,
                currency=str(order.currency_id),
                assignment_effective_at=closed_at,
                idempotency_key=f"primary-close-holding:{order.id}",
                metadata={
                    "primary_close_id": str(close.id),
                    "document_acceptance_id": str(order.document_acceptance_id or ""),
                    "reservation_journal_entry_id": str(order.reservation_journal_entry_id or ""),
                },
            )
        )
        holding_ids.append(str(holding.id))
        previous_status = str(order.status)
        order.status = PrimaryInvestmentOrderStatus.CLOSED_INVESTED
        order.closed_at = closed_at
        order.closed_by_admin_id = command.actor.pk
        order.admin_notes = reason
        order.metadata = {
            **cast(dict[str, Any], order.metadata),
            "primary_close_id": str(close.id),
            "holding_id": str(holding.id),
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
            event_type=PrimaryInvestmentOrderEventType.CLOSED_INVESTED,
            previous_status=previous_status,
            new_status=order.status,
            note=reason,
            metadata={
                "primary_close_id": str(close.id),
                "holding_id": str(holding.id),
                "allocated_amount_minor": order.allocated_amount_minor,
            },
        )

    for order in pending_orders:
        previous_status = str(order.status)
        order.status = PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
        order.closed_at = closed_at
        order.closed_by_admin_id = command.actor.pk
        order.admin_notes = reason
        order.metadata = {
            **cast(dict[str, Any], order.metadata),
            "primary_close_id": str(close.id),
            "closed_reason": "Loan funding closed before order allocation.",
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
            metadata={"primary_close_id": str(close.id), "reason": "loan_funding_closed"},
        )

    previous_loan_status = str(loan_ref.status)
    loan_ref.status = "funded"
    loan_ref.updated_by_admin_id = command.actor.pk
    loan.save(update_fields=["status", "updated_by_admin_id", "updated_at"])
    event_metadata = {
        **close_metadata,
        "primary_close_id": str(close.id),
        "holding_ids": holding_ids,
        "borrower_success_fee_bps": close.borrower_success_fee_bps,
        "borrower_success_fee_minor": close.borrower_success_fee_minor,
        "borrower_disbursement_payable_minor": close.borrower_disbursement_payable_minor,
    }
    _record_loan_funding_closed_event(
        loan=loan,
        actor=command.actor,
        previous_status=previous_loan_status,
        new_status=str(loan_ref.status),
        close=close,
        metadata=event_metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="marketplace_primary.loan_funding_closed",
            target_type="PrimaryLoanClose",
            target_id=str(close.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="PrimaryLoanFundingClosed",
            aggregate_type="PrimaryLoanClose",
            aggregate_id=str(close.id),
            payload=event_metadata,
            idempotency_key=f"primary-loan-close:{close.id}:closed",
        )
    )
    return close


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
