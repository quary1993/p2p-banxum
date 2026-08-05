from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model, Q, Sum

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryInvestmentOrderEvent,
    PrimaryInvestmentOrderEventType,
    PrimaryInvestmentOrderStatus,
    PrimaryLoanCancellation,
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
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    record_domain_event,
)
from backend.apps.platform_core.services.sensitive_actions import (
    PRIMARY_INVESTMENT_ACTION,
    SensitiveActionVerificationCommand,
    SensitiveActionVerificationError,
    verify_sensitive_action_code,
)


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
CANCEL_FINGERPRINT_METADATA_KEY = "cancel_request_fingerprint"
ONE_HUNDRED_PERCENT_PPM = 1_000_000


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
    sensitive_action_code_id: str = ""
    sensitive_action_code: str = ""
    ip_address: str | None = None
    user_agent: str = ""


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
    as_of_date: date | None = None
    retry_failed: bool = False


@dataclass(frozen=True, slots=True)
class CancelPrimaryLoanFundingCommand:
    actor: Model
    loan_id: str
    reason: str
    investor_message: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class ScanExpiredPrimaryFundingCommand:
    actor: Model
    as_of_date: date | None = None
    loan_ids: tuple[str, ...] = ()
    reason: str = ""
    investor_message: str = ""
    idempotency_key: str = ""
    limit: int = 250


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


def _clean_optional_idempotency_key(value: str) -> str:
    key = value.strip()
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


def _entities_services() -> Any:
    return import_module("backend.apps.entities.services")


def _originator_services() -> Any:
    return import_module("backend.apps.originator_claims.services")


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


def _cancel_request_fingerprint(
    command: CancelPrimaryLoanFundingCommand,
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


def _child_idempotency_key(kind: str, parent_key: str, child_id: str) -> str:
    digest = hashlib.sha256(f"{kind}:{parent_key}:{child_id}".encode()).hexdigest()
    return f"{kind}:{digest}"[:MAX_IDEMPOTENCY_KEY_LENGTH]


def _minimum_subscription_required_minor(loan: Model) -> int:
    loan_ref = cast(Any, loan)
    principal_minor = int(loan_ref.principal_minor)
    minimum_bps = int(getattr(loan_ref, "minimum_subscription_bps", 5_000))
    return -(-principal_minor * minimum_bps // 10_000)


def _borrower_allows_funding_close(borrower: Model) -> bool:
    """Allow routine KYB expiry, but never fund through an explicit risk hold."""

    borrower_ref = cast(Any, borrower)
    if bool(borrower_ref.compliance_hold):
        return False
    return str(borrower_ref.kyb_status) in {"approved", "expired"}


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


def _existing_cancellation_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> PrimaryLoanCancellation | None:
    existing = PrimaryLoanCancellation.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(CANCEL_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise MarketplacePrimaryValidationError(
            "Idempotency key was already used for a different cancellation request."
        )
    return cast(PrimaryLoanCancellation, existing)


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


def _admin_ops_services() -> Any:
    return import_module("backend.apps.admin_ops.services")


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


def allocate_primary_order_from_balance(
    command: AllocatePrimaryInvestmentOrderCommand,
) -> PrimaryInvestmentOrder:
    _require_investor_financial_access(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    order = PrimaryInvestmentOrder.objects.filter(
        id=command.order_id,
        investor_user_id=command.actor.pk,
    ).first()
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
    _validate_primary_document_acceptance(
        acceptance_id=command.document_acceptance_id,
        actor=command.actor,
        order=order,
    )

    try:
        verify_sensitive_action_code(
            SensitiveActionVerificationCommand(
                actor=command.actor,
                action=PRIMARY_INVESTMENT_ACTION,
                code_id=command.sensitive_action_code_id,
                raw_code=command.sensitive_action_code,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
    except SensitiveActionVerificationError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc

    return _allocate_primary_order_from_balance_after_sensitive_code(command)


@transaction.atomic
def _allocate_primary_order_from_balance_after_sensitive_code(
    command: AllocatePrimaryInvestmentOrderCommand,
) -> PrimaryInvestmentOrder:
    _require_investor_financial_access(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    order_loan_id = (
        PrimaryInvestmentOrder.objects.filter(
            id=command.order_id,
            investor_user_id=command.actor.pk,
        )
        .values_list("loan_id", flat=True)
        .first()
    )
    if order_loan_id is None:
        raise MarketplacePrimaryValidationError("Primary investment order does not exist.")
    # Every primary-market mutation locks the loan before its orders. The
    # deadline resolver uses the same order, so allocation cannot deadlock with
    # an automatic close while acquiring the same rows in reverse order.
    loan = _loan_for_update(str(order_loan_id))
    order = (
        PrimaryInvestmentOrder.objects.select_for_update()
        .filter(
            id=command.order_id,
            investor_user_id=command.actor.pk,
            loan_id=order_loan_id,
        )
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
    order_loan_id = (
        PrimaryInvestmentOrder.objects.filter(id=command.order_id)
        .values_list("loan_id", flat=True)
        .first()
    )
    if order_loan_id is None:
        raise MarketplacePrimaryValidationError("Primary investment order does not exist.")
    # Match allocation, close and cancellation: loan first, then order.
    loan = _loan_for_update(str(order_loan_id))
    order = (
        PrimaryInvestmentOrder.objects.select_for_update()
        .filter(id=command.order_id, loan_id=order_loan_id)
        .first()
    )
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
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) not in {"published", "funding_close_failed"}:
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


def _holding_share_ppm_by_order(
    *,
    allocated_orders: list[PrimaryInvestmentOrder],
    accepted_principal_minor: int,
) -> dict[str, int]:
    if accepted_principal_minor <= 0:
        raise MarketplacePrimaryValidationError("Accepted funded principal must be positive.")
    base_shares: dict[str, int] = {}
    ranked_remainders: list[tuple[int, int, str]] = []
    for index, order in enumerate(allocated_orders):
        product = order.allocated_amount_minor * ONE_HUNDRED_PERCENT_PPM
        base_shares[str(order.id)] = product // accepted_principal_minor
        ranked_remainders.append((product % accepted_principal_minor, index, str(order.id)))

    residue = ONE_HUNDRED_PERCENT_PPM - sum(base_shares.values())
    for _remainder, _index, order_id in sorted(
        ranked_remainders,
        key=lambda item: (-item[0], item[1]),
    )[:residue]:
        base_shares[order_id] += 1
    return base_shares


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


def _record_loan_funding_cancelled_event(
    *,
    loan: Model,
    actor: Model,
    previous_status: str,
    cancellation: PrimaryLoanCancellation,
    metadata: dict[str, Any],
) -> None:
    loan_ref = cast(Any, loan)
    loan_event_model = _model("loans", "LoanEvent")
    loan_event_model.objects.create(
        loan=loan,
        event_type="funding_cancelled",
        actor_user_id=actor.pk,
        actor_account_type=_actor_account_type(actor),
        previous_status=previous_status,
        new_status=str(loan_ref.status),
        note=cancellation.reason,
        metadata=metadata,
    )
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.funding_cancelled",
            target_type="Loan",
            target_id=str(loan_ref.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanFundingCancelled",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=metadata,
            idempotency_key=f"loan:{loan_ref.id}:funding-cancelled",
        )
    )


def _record_loan_funding_close_failed_event(
    *,
    loan: Model,
    actor: Model,
    previous_status: str,
    note: str,
    metadata: dict[str, Any],
) -> Model:
    loan_ref = cast(Any, loan)
    loan_event_model = _model("loans", "LoanEvent")
    event = cast(
        Model,
        loan_event_model.objects.create(
            loan=loan,
            event_type="funding_close_failed",
            actor_user_id=actor.pk,
            actor_account_type=_actor_account_type(actor),
            previous_status=previous_status,
            new_status=str(loan_ref.status),
            note=note,
            metadata=metadata,
        ),
    )
    event_metadata = {**metadata, "loan_event_id": str(event.pk)}
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="loan.funding_close_failed",
            target_type="Loan",
            target_id=str(loan_ref.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="LoanFundingCloseFailed",
            aggregate_type="Loan",
            aggregate_id=str(loan_ref.id),
            payload=event_metadata,
            idempotency_key=f"loan:{loan_ref.id}:funding-close-failed:{event.pk}",
        )
    )
    return event


def _mark_funding_close_failed(
    *,
    loan: Model,
    actor: Model,
    as_of_date: date,
    resolution_action: str,
    error: Exception,
) -> dict[str, str]:
    loan_ref = cast(Any, loan)
    previous_status = str(loan_ref.status)
    error_message = str(error).strip() or error.__class__.__name__
    loan_ref.status = "funding_close_failed"
    loan_ref.updated_by_admin_id = actor.pk
    loan.save(update_fields=["status", "updated_by_admin_id", "updated_at"])
    metadata = {
        "loan_id": str(loan_ref.id),
        "as_of_date": as_of_date.isoformat(),
        "resolution_action": resolution_action,
        "failure_type": error.__class__.__name__,
        "failure_reason": error_message,
        "currency": str(loan_ref.currency_id),
        "principal_minor": int(loan_ref.principal_minor),
        "committed_principal_minor": int(loan_ref.committed_principal_minor),
        "minimum_subscription_bps": int(loan_ref.minimum_subscription_bps),
        "minimum_required_minor": _minimum_subscription_required_minor(loan),
        "reservations_preserved": True,
    }
    event = _record_loan_funding_close_failed_event(
        loan=loan,
        actor=actor,
        previous_status=previous_status,
        note=error_message,
        metadata=metadata,
    )
    admin_ops = _admin_ops_services()
    task = admin_ops.ensure_loan_funding_close_failure_task(
        admin_ops.EnsureLoanFundingCloseFailureTaskCommand(
            actor=actor,
            loan_id=str(loan_ref.id),
            loan_title=str(loan_ref.title),
            currency=str(loan_ref.currency_id),
            committed_principal_minor=int(loan_ref.committed_principal_minor),
            target_principal_minor=int(loan_ref.principal_minor),
            minimum_subscription_bps=int(loan_ref.minimum_subscription_bps),
            failure_reason=error_message,
            failure_event_id=str(event.pk),
        )
    )
    operations_email = str(
        getattr(settings, "OPERATIONS_ALERT_EMAIL", "") or "hq@banxum.com"
    ).strip()
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=f"email:loan-funding-close-failed:{event.pk}",
            topic="email.loan_funding_close_failed",
            payload={
                "email": operations_email,
                "subject": f"BANXUM funding close failed: {loan_ref.title}",
                "headline": "Automatic funding close needs attention",
                "status_label": "Urgent action",
                "status_tone": "danger",
                "body_text": (
                    f"The automatic {resolution_action} step failed for loan {loan_ref.title} "
                    f"({loan_ref.id}).\n\n"
                    f"Reason: {error_message}\n\n"
                    "The loan is no longer public. Investor reservations remain locked and "
                    "unchanged. Resolve the cause, then retry the deterministic funding "
                    "resolution or cancel and refund the campaign from the admin console."
                ),
                "template_key": "ops.loan_funding_close_failed.v1",
                "data_rows": [
                    ["Loan", str(loan_ref.title)],
                    ["Loan ID", str(loan_ref.id)],
                    ["Resolution", resolution_action],
                    ["Reserved minor units", str(loan_ref.committed_principal_minor)],
                    ["Admin task", str(task.id)],
                ],
                "metadata": {
                    **metadata,
                    "admin_task_id": str(task.id),
                    "loan_event_id": str(event.pk),
                },
            },
        )
    )
    return {
        "loan_id": str(loan_ref.id),
        "reason": error_message,
        "resolution_action": resolution_action,
        "task_id": str(task.id),
        "event_id": str(event.pk),
    }


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
    loan_status = str(loan_ref.status)
    if loan_status == "published":
        if command.as_of_date is None:
            raise MarketplacePrimaryValidationError(
                "Published loans close automatically after their funding deadline; "
                "run the funding expiry resolution instead."
            )
        if loan_ref.funding_deadline is None or loan_ref.funding_deadline >= command.as_of_date:
            raise MarketplacePrimaryValidationError(
                "Loan funding cannot close before its funding deadline has passed."
            )
    elif loan_status == "funding_close_failed":
        if not command.retry_failed:
            raise MarketplacePrimaryValidationError(
                "A failed funding close must be retried through funding expiry resolution."
            )
    else:
        raise MarketplacePrimaryValidationError(
            "Only an expired published loan or a failed funding close can be closed."
        )
    if not _borrower_allows_funding_close(cast(Model, loan_ref.borrower)):
        raise MarketplacePrimaryValidationError(
            "Borrower is declined, under review, or subject to a compliance hold. "
            "Routine KYB expiry does not block funding close."
        )
    minimum_required_minor = _minimum_subscription_required_minor(loan)
    if int(loan_ref.committed_principal_minor) < minimum_required_minor:
        raise MarketplacePrimaryValidationError(
            "Committed principal is below the loan's minimum subscription threshold."
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
                funding_close_adjustment=True,
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
    holding_share_ppm_by_order = _holding_share_ppm_by_order(
        allocated_orders=allocated_orders,
        accepted_principal_minor=accepted_principal,
    )
    close_metadata = {
        CLOSE_FINGERPRINT_METADATA_KEY: close_fingerprint,
        "loan_id": str(loan_ref.id),
        "close_type": str(close_type),
        "currency": str(loan_ref.currency_id),
        "accepted_principal_minor": accepted_principal,
        "minimum_subscription_bps": int(loan_ref.minimum_subscription_bps),
        "minimum_required_minor": minimum_required_minor,
        "allocated_order_ids": [str(order.id) for order in allocated_orders],
        "pending_order_ids_closed_not_invested": [str(order.id) for order in pending_orders],
        "funding_close_journal_entry_id": str(ledger_result.journal_entry.id),
        "holding_share_ppm_total": sum(holding_share_ppm_by_order.values()),
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
                loan_share_ppm=holding_share_ppm_by_order[str(order.id)],
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


@transaction.atomic
def cancel_primary_loan_funding(
    command: CancelPrimaryLoanFundingCommand,
) -> PrimaryLoanCancellation:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    reason = _clean_required(command.reason, "Cancellation reason")
    cancel_fingerprint = _cancel_request_fingerprint(
        command,
        idempotency_key=idempotency_key,
    )
    existing = _existing_cancellation_for_idempotency(
        idempotency_key,
        expected_fingerprint=cancel_fingerprint,
    )
    if existing is not None:
        return existing
    if PrimaryLoanClose.objects.filter(loan_id=command.loan_id).exists():
        raise MarketplacePrimaryValidationError("Closed loan funding cannot be cancelled.")

    loan = _loan_for_update(command.loan_id)
    loan_ref = cast(Any, loan)
    existing = _existing_cancellation_for_idempotency(
        idempotency_key,
        expected_fingerprint=cancel_fingerprint,
    )
    if existing is not None:
        return existing
    if str(loan_ref.status) == "cancelled":
        existing_for_loan = PrimaryLoanCancellation.objects.filter(loan_id=command.loan_id).first()
        if existing_for_loan is not None:
            raise MarketplacePrimaryValidationError("Loan funding is already cancelled.")
    if str(loan_ref.status) not in {"published", "funding_close_failed"}:
        raise MarketplacePrimaryValidationError(
            "Only published loans or failed funding closes can be cancelled."
        )

    allocated_orders = _allocated_orders_for_close(str(loan_ref.id))
    pending_orders = _pending_orders_for_close(str(loan_ref.id))
    investor_message = command.investor_message.strip()
    if (allocated_orders or pending_orders) and not investor_message:
        raise MarketplacePrimaryValidationError(
            "Investor message is required when cancelling a loan with investor orders."
        )

    cancelled_at = now_utc()
    released_order_ids: list[str] = []
    release_journal_entry_ids: list[str] = []
    released_principal = 0
    for order in allocated_orders:
        released = release_primary_order_balance(
            ReleasePrimaryInvestmentOrderCommand(
                actor=command.actor,
                order_id=str(order.id),
                reason=reason,
                idempotency_key=_child_idempotency_key(
                    "primary-cancel-release",
                    idempotency_key,
                    str(order.id),
                ),
            )
        )
        released_order_ids.append(str(released.id))
        released_principal += int(released.allocated_amount_minor)
        if released.release_journal_entry_id:
            release_journal_entry_ids.append(str(released.release_journal_entry_id))

    closed_not_invested_order_ids: list[str] = []
    for order in pending_orders:
        previous_status = str(order.status)
        order.status = PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
        order.closed_at = cancelled_at
        order.closed_by_admin_id = command.actor.pk
        order.admin_notes = reason
        order.metadata = {
            **cast(dict[str, Any], order.metadata),
            "cancel_idempotency_key": idempotency_key,
            "closed_reason": "Loan funding cancelled before order allocation.",
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
        closed_not_invested_order_ids.append(str(order.id))
        _record_order_event(
            order=order,
            actor=command.actor,
            event_type=PrimaryInvestmentOrderEventType.CLOSED_NOT_INVESTED,
            previous_status=previous_status,
            new_status=order.status,
            note=reason,
            metadata={"reason": "loan_funding_cancelled"},
        )

    loan.refresh_from_db()
    loan_ref = cast(Any, loan)
    if int(loan_ref.committed_principal_minor) != 0:
        raise MarketplacePrimaryValidationError(
            "Loan committed principal must be zero after cancellation releases."
        )

    metadata = {
        CANCEL_FINGERPRINT_METADATA_KEY: cancel_fingerprint,
        "loan_id": str(loan_ref.id),
        "currency": str(loan_ref.currency_id),
        "released_order_ids": released_order_ids,
        "release_journal_entry_ids": release_journal_entry_ids,
        "closed_not_invested_order_ids": closed_not_invested_order_ids,
        "released_principal_minor": released_principal,
    }
    try:
        cancellation = cast(
            PrimaryLoanCancellation,
            PrimaryLoanCancellation.objects.create(
                loan=cast(Any, loan),
                currency_id=str(loan_ref.currency_id),
                released_order_count=len(released_order_ids),
                closed_not_invested_order_count=len(closed_not_invested_order_ids),
                released_principal_minor=released_principal,
                created_by_admin_id=command.actor.pk,
                cancelled_at=cancelled_at,
                reason=reason,
                investor_message=investor_message,
                metadata=metadata,
                idempotency_key=idempotency_key,
            ),
        )
    except IntegrityError:
        existing_after_race = _existing_cancellation_for_idempotency(
            idempotency_key,
            expected_fingerprint=cancel_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    previous_loan_status = str(loan_ref.status)
    loan_ref.status = "cancelled"
    loan_ref.updated_by_admin_id = command.actor.pk
    loan.save(update_fields=["status", "updated_by_admin_id", "updated_at"])
    event_metadata = {**metadata, "primary_cancellation_id": str(cancellation.id)}
    _record_loan_funding_cancelled_event(
        loan=loan,
        actor=command.actor,
        previous_status=previous_loan_status,
        cancellation=cancellation,
        metadata=event_metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="marketplace_primary.loan_funding_cancelled",
            target_type="PrimaryLoanCancellation",
            target_id=str(cancellation.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="PrimaryLoanFundingCancelled",
            aggregate_type="PrimaryLoanCancellation",
            aggregate_id=str(cancellation.id),
            payload=event_metadata,
            idempotency_key=f"primary-loan-cancellation:{cancellation.id}:cancelled",
        )
    )
    return cancellation


@transaction.atomic
def _resolve_expired_primary_loan_funding(
    *,
    actor: Model,
    loan_id: str,
    as_of_date: date,
    parent_key: str,
    cancellation_reason: str,
    cancellation_message: str,
) -> tuple[str, Any]:
    """Resolve one campaign while holding the same lock used by allocation and close."""

    loan_model = _model("loans", "Loan")
    loan = (
        loan_model.objects.select_for_update()
        .select_related("currency", "borrower")
        .filter(id=loan_id)
        .first()
    )
    if loan is None:
        return "skipped", {"loan_id": loan_id, "reason": "Loan no longer exists."}
    loan_ref = cast(Any, loan)
    status = str(loan_ref.status)
    if status == "published":
        if loan_ref.funding_deadline is None or loan_ref.funding_deadline >= as_of_date:
            return "skipped", {
                "loan_id": loan_id,
                "reason": "Funding deadline has not passed.",
            }
    elif status != "funding_close_failed":
        return "skipped", {
            "loan_id": loan_id,
            "reason": f"Loan is no longer awaiting funding resolution ({status}).",
        }

    committed = int(loan_ref.committed_principal_minor)
    minimum_required_minor = _minimum_subscription_required_minor(loan)
    should_close = committed > 0 and committed >= minimum_required_minor
    resolution_action = "close" if should_close else "cancel and refund"
    try:
        # Keep the financial resolution and failure-task transition in one savepoint.
        # If either fails, the close/cancellation rolls back before we preserve the
        # reservations and surface the operational failure below.
        with transaction.atomic():
            if should_close:
                close = close_primary_loan_funding(
                    ClosePrimaryLoanFundingCommand(
                        actor=actor,
                        loan_id=loan_id,
                        reason=(
                            "Funding deadline reached with the minimum subscription met; "
                            f"closed at the subscribed amount on {as_of_date.isoformat()}."
                        ),
                        investor_message=(
                            "The funding window closed with the minimum subscription met. "
                            "The loan was made at the amount subscribed by the deadline."
                        ),
                        idempotency_key=_child_idempotency_key(
                            "primary-expiry-close",
                            parent_key,
                            loan_id,
                        ),
                        as_of_date=as_of_date,
                        retry_failed=status == "funding_close_failed",
                    )
                )
                if status == "funding_close_failed":
                    _admin_ops_services().resolve_loan_funding_close_failure_task(
                        actor=actor,
                        loan_id=loan_id,
                        completion_note=(
                            "The deterministic funding resolution was retried successfully and "
                            "the loan funding was closed."
                        ),
                    )
                return "closed", close
            cancellation = cancel_primary_loan_funding(
                CancelPrimaryLoanFundingCommand(
                    actor=actor,
                    loan_id=loan_id,
                    reason=cancellation_reason,
                    investor_message=cancellation_message,
                    idempotency_key=_child_idempotency_key(
                        "primary-expiry-cancel",
                        parent_key,
                        loan_id,
                    ),
                )
            )
            if status == "funding_close_failed":
                _admin_ops_services().resolve_loan_funding_close_failure_task(
                    actor=actor,
                    loan_id=loan_id,
                    completion_note=(
                        "The failed campaign was cancelled and all investor reservations were "
                        "released."
                    ),
                )
            return "cancelled", cancellation
    except Exception as exc:  # noqa: BLE001 - any recoverable close failure becomes an ops case.
        failure = _mark_funding_close_failed(
            loan=loan,
            actor=actor,
            as_of_date=as_of_date,
            resolution_action=resolution_action,
            error=exc,
        )
        return "failed", failure


def scan_expired_primary_loan_funding(
    command: ScanExpiredPrimaryFundingCommand,
) -> dict[str, Any]:
    _require_admin_actor(command.actor)
    as_of_date = command.as_of_date or business_date(now_utc())
    limit = command.limit
    if limit < 1 or limit > 1000:
        raise MarketplacePrimaryValidationError("Scan limit must be between 1 and 1000.")
    parent_key = _clean_optional_idempotency_key(command.idempotency_key) or (
        f"primary-expiry-scan:{as_of_date.isoformat()}"
    )
    default_reason = (
        f"Funding deadline passed below the minimum subscription by {as_of_date.isoformat()}."
    )
    default_message = (
        "The campaign closed below its minimum subscription. No loan was made and any "
        "reserved balance was released to your BANXUM account."
    )
    cancellation_reason = command.reason.strip() or default_reason
    cancellation_message = command.investor_message.strip() or default_message

    loan_model = _model("loans", "Loan")
    if command.loan_ids:
        query = loan_model.objects.filter(id__in=command.loan_ids).filter(
            Q(status="funding_close_failed")
            | Q(status="published", funding_deadline__lt=as_of_date)
        )
    else:
        query = loan_model.objects.filter(
            status="published",
            funding_deadline__lt=as_of_date,
        )
    loan_ids = [
        str(value)
        for value in query.order_by("funding_deadline", "id").values_list("id", flat=True)[:limit]
    ]
    cancellations: list[PrimaryLoanCancellation] = []
    closes: list[PrimaryLoanClose] = []
    failures: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for loan_id in loan_ids:
        outcome, payload = _resolve_expired_primary_loan_funding(
            actor=command.actor,
            loan_id=loan_id,
            as_of_date=as_of_date,
            parent_key=parent_key,
            cancellation_reason=cancellation_reason,
            cancellation_message=cancellation_message,
        )
        if outcome == "closed":
            closes.append(cast(PrimaryLoanClose, payload))
        elif outcome == "cancelled":
            cancellations.append(cast(PrimaryLoanCancellation, payload))
        elif outcome == "failed":
            failures.append(cast(dict[str, str], payload))
        else:
            skipped.append(cast(dict[str, str], payload))

    return {
        "as_of_date": as_of_date,
        "scanned_count": len(loan_ids),
        "cancelled_count": len(cancellations),
        "closed_count": len(closes),
        "failed_count": len(failures),
        "closes": closes,
        "cancellations": cancellations,
        "failures": failures,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }


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
        "product_type": str(loan_ref.product_type),
        "investment_flow": "primary_order",
        "title": str(loan_ref.title),
        "purpose": str(loan_ref.purpose),
        "collateral_type": str(loan_ref.collateral_type),
        "interest_rate_bps": int(loan_ref.interest_rate_bps),
        "yield_bps": int(loan_ref.interest_rate_bps),
        "underlying_interest_rate_bps": int(loan_ref.interest_rate_bps),
        "term_months": int(loan_ref.term_months),
        "remaining_term_days": None,
        "risk_rating": str(loan_ref.risk_rating),
        "funding_deadline": loan_ref.funding_deadline,
        "maturity_date": None,
        "status": str(loan_ref.status),
        "loan_status": str(loan_ref.status),
        "opportunity_status": "open",
        "fillable_amount_minor": progress["remaining_capacity_minor"],
        "minimum_investment_minor": _minimum_investment_minor(str(loan_ref.currency_id)),
        "ltv_bps": loan_ref.ltv_bps,
        "is_refinancing": bool(loan_ref.is_refinancing),
        "originator_id": None,
        "originator_name": None,
        "borrower_display_name": None,
        "skin_in_the_game_bps": int(getattr(loan_ref, "skin_in_the_game_bps", 0)),
        "minimum_subscription_bps": int(getattr(loan_ref, "minimum_subscription_bps", 5_000)),
    }


def full_marketplace_listing_payload(loan: Model) -> dict[str, Any]:
    loan_ref = cast(Any, loan)
    if str(loan_ref.product_type) == "originator_claim":
        raise MarketplacePrimaryValidationError(
            "Originator claim details must use the originator investor projection."
        )
    borrower = cast(Model, loan_ref.borrower)
    entities_services = _entities_services()
    payload = public_marketplace_listing_payload(loan)
    payload.update(
        {
            "borrower_id": str(loan_ref.borrower_id),
            "borrower_disclosure": entities_services.borrower_investor_disclosure(borrower),
            "investor_summary": str(loan_ref.investor_summary),
            "purpose_description": str(loan_ref.purpose_description),
            "collateral_value_minor": int(loan_ref.collateral_value_minor),
            "collateral_description": str(loan_ref.collateral_description),
            "default_penalty_interest_bps": int(loan_ref.default_penalty_interest_bps),
            "ltv_bps": loan_ref.ltv_bps,
            "ltv_warnings": loan_ref.ltv_warnings,
            "original_principal_minor": int(loan_ref.original_principal_minor),
            "original_interest_rate_bps": (
                int(loan_ref.original_interest_rate_bps)
                if loan_ref.original_interest_rate_bps is not None
                else None
            ),
            "original_term_months": (
                int(loan_ref.original_term_months)
                if loan_ref.original_term_months is not None
                else None
            ),
            "original_repayment_type": (
                str(loan_ref.original_repayment_type) if loan_ref.original_repayment_type else None
            ),
            "original_interest_only_months": (
                int(loan_ref.original_interest_only_months)
                if loan_ref.original_interest_only_months is not None
                else None
            ),
            "original_loan_start_date": loan_ref.original_loan_start_date,
            "repayment_type": str(loan_ref.repayment_type),
            "loan_start_date": loan_ref.loan_start_date,
            "first_payment_date": loan_ref.first_payment_date,
            "schedule_version": int(loan_ref.schedule_version),
            "originator_schedule": [],
            "originator_payment_history": [],
            "schedule_revision": None,
            "pricing_as_of_date": None,
        }
    )
    if bool(loan_ref.is_refinancing):
        loans_services = _loans_services()
        payload["original_loan_schedule"] = loans_services.original_schedule_payload(loan)
    return payload


def list_public_marketplace_loans(*, limit: int = 100) -> list[dict[str, Any]]:
    loan_model = _model("loans", "Loan")
    loans = loan_model.objects.filter(status="published", product_type="direct").order_by(
        "funding_deadline", "id"
    )[:limit]
    payloads = [public_marketplace_listing_payload(cast(Model, loan)) for loan in loans]
    payloads.extend(_originator_services().list_open_originator_marketplace_payloads(limit=limit))
    # Fetch each product independently before applying the shared response limit so
    # a full direct-loan page cannot make open originator claims disappear.
    return sorted(
        payloads,
        key=lambda item: (
            str(item.get("funding_deadline") or item.get("maturity_date") or "9999-12-31"),
            str(item.get("title", "")),
            str(item.get("loan_id", "")),
        ),
    )[:limit]


def get_full_marketplace_loan(*, actor: Model, loan_id: str) -> dict[str, Any]:
    _require_investor_financial_access(actor)
    loan = _loan_for_read(loan_id)
    if str(cast(Any, loan).product_type) == "originator_claim":
        originator_services = _originator_services()
        try:
            return cast(
                dict[str, Any],
                originator_services.get_originator_marketplace_payload(
                    actor=actor,
                    loan_id=loan_id,
                ),
            )
        except originator_services.OriginatorClaimsError as exc:
            raise MarketplacePrimaryValidationError(str(exc)) from exc
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
