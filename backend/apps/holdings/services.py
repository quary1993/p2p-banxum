from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Model

from backend.apps.holdings.models import (
    InvestorLoanHolding,
    InvestorLoanHoldingEvent,
    InvestorLoanHoldingEventType,
    InvestorLoanHoldingSourceType,
    InvestorLoanHoldingStatus,
)
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
    is_lender_actor,
)
from backend.apps.platform_core.domain.money import Money, MoneyError, normalize_currency
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event


class HoldingsError(ValueError):
    pass


class HoldingsAuthorizationError(HoldingsError):
    pass


class HoldingsValidationError(HoldingsError):
    pass


MAX_IDEMPOTENCY_KEY_LENGTH = 160
REQUEST_FINGERPRINT_METADATA_KEY = "request_fingerprint"
ONE_HUNDRED_PERCENT_PPM = 1_000_000


@dataclass(frozen=True, slots=True)
class CreatePrimaryMarketHoldingCommand:
    actor: Model
    investor_user_id: str
    loan_id: str
    primary_order_id: str
    principal_minor: int
    accepted_loan_principal_minor: int
    currency: str
    assignment_effective_at: datetime
    idempotency_key: str
    loan_share_ppm: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class TransferSecondaryMarketHoldingCommand:
    actor: Model
    seller_holding_id: str
    buyer_user_id: str
    purchase_id: str
    principal_minor: int
    currency: str
    assignment_effective_at: datetime
    idempotency_key: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SecondaryMarketHoldingTransferResult:
    seller_holding: InvestorLoanHolding
    buyer_holding: InvestorLoanHolding


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise HoldingsAuthorizationError("Only an active admin can create investor holdings.")


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HoldingsValidationError(f"{label} is required.")
    return cleaned


def _clean_idempotency_key(value: str) -> str:
    key = _clean_required(value, "Idempotency key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise HoldingsValidationError(
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
        raise HoldingsValidationError(str(exc)) from exc
    currency = Currency.objects.filter(code=code, is_enabled=True).first()
    if currency is None:
        raise HoldingsValidationError(f"Currency is not enabled: {code}")
    return currency


def _validate_money(amount_minor: int, currency_code: str, label: str) -> int:
    try:
        Money(amount_minor, currency_code)
    except MoneyError as exc:
        raise HoldingsValidationError(str(exc)) from exc
    if amount_minor <= 0:
        raise HoldingsValidationError(f"{label} must be positive.")
    return amount_minor


def _loan_share_ppm(*, principal_minor: int, accepted_loan_principal_minor: int) -> int:
    if accepted_loan_principal_minor <= 0:
        raise HoldingsValidationError("Accepted loan principal must be positive.")
    share = (
        Decimal(principal_minor)
        * Decimal(ONE_HUNDRED_PERCENT_PPM)
        / Decimal(accepted_loan_principal_minor)
    )
    return int(share.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _validated_loan_share_ppm(value: int | None) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise HoldingsValidationError("Loan share ppm must be an integer.")
    if value < 0 or value > ONE_HUNDRED_PERCENT_PPM:
        raise HoldingsValidationError("Loan share ppm must be between 0 and 1,000,000.")
    return value


def _request_fingerprint(
    command: CreatePrimaryMarketHoldingCommand,
    *,
    currency_code: str,
    principal_minor: int,
    accepted_loan_principal_minor: int,
    loan_share_ppm: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "investor_user_id": str(command.investor_user_id),
            "loan_id": str(command.loan_id),
            "primary_order_id": str(command.primary_order_id),
            "principal_minor": principal_minor,
            "accepted_loan_principal_minor": accepted_loan_principal_minor,
            "loan_share_ppm": loan_share_ppm,
            "currency": currency_code,
            "assignment_effective_at": command.assignment_effective_at,
            "idempotency_key": idempotency_key,
        }
    )


def _existing_holding_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> InvestorLoanHolding | None:
    existing = InvestorLoanHolding.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(REQUEST_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise HoldingsValidationError(
            "Idempotency key was already used for a different holding request."
        )
    return existing


def _lender_account_for_id(investor_user_id: str) -> Model:
    user_model = get_user_model()
    investor = cast(Model | None, user_model.objects.filter(id=investor_user_id).first())
    if investor is None:
        raise HoldingsValidationError("Investor account does not exist.")
    if not is_lender_actor(investor):
        raise HoldingsValidationError("Investor account must be an active lender account.")
    return investor


def _secondary_transfer_request_fingerprint(
    command: TransferSecondaryMarketHoldingCommand,
    *,
    seller_user_id: str,
    buyer_user_id: str,
    loan_id: str,
    currency_code: str,
    principal_minor: int,
    loan_share_ppm: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "seller_holding_id": str(command.seller_holding_id),
            "seller_user_id": seller_user_id,
            "buyer_user_id": buyer_user_id,
            "loan_id": loan_id,
            "purchase_id": str(command.purchase_id),
            "principal_minor": principal_minor,
            "loan_share_ppm": loan_share_ppm,
            "currency": currency_code,
            "assignment_effective_at": command.assignment_effective_at,
            "idempotency_key": idempotency_key,
        }
    )


def _record_holding_event(
    *,
    holding: InvestorLoanHolding,
    actor: Model,
    event_type: InvestorLoanHoldingEventType,
    previous_status: str = "",
    new_status: str = "",
    note: str = "",
    metadata: dict[str, Any] | None = None,
) -> InvestorLoanHoldingEvent:
    return cast(
        InvestorLoanHoldingEvent,
        InvestorLoanHoldingEvent.objects.create(
            holding=holding,
            loan_id=holding.loan_id,
            investor_user_id=holding.investor_user_id,
            event_type=event_type,
            actor_user_id=actor.pk,
            actor_account_type=str(getattr(actor, "account_type", "")),
            previous_status=previous_status,
            new_status=new_status,
            note=note.strip(),
            metadata=metadata or {},
        ),
    )


@transaction.atomic
def transfer_holding_for_secondary_market_purchase(
    command: TransferSecondaryMarketHoldingCommand,
) -> SecondaryMarketHoldingTransferResult:
    buyer = _lender_account_for_id(command.buyer_user_id)
    buyer_id = str(buyer.pk)
    currency = _enabled_currency(command.currency)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    seller_holding = (
        InvestorLoanHolding.objects.select_for_update()
        .select_related("loan", "currency")
        .filter(id=command.seller_holding_id)
        .first()
    )
    if seller_holding is None:
        raise HoldingsValidationError("Seller holding does not exist.")
    seller_id = str(seller_holding.investor_user_id)
    if seller_id == buyer_id:
        raise HoldingsValidationError("Buyer and seller must be different investors.")
    if seller_holding.currency_id != currency.code:
        raise HoldingsValidationError("Holding currency does not match transfer currency.")
    principal_minor = _validate_money(
        command.principal_minor,
        currency.code,
        "Secondary-market holding principal",
    )
    request_fingerprint = _secondary_transfer_request_fingerprint(
        command,
        seller_user_id=seller_id,
        buyer_user_id=buyer_id,
        loan_id=str(seller_holding.loan_id),
        currency_code=currency.code,
        principal_minor=principal_minor,
        loan_share_ppm=seller_holding.loan_share_ppm,
        idempotency_key=idempotency_key,
    )
    existing = _existing_holding_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return SecondaryMarketHoldingTransferResult(
            seller_holding=seller_holding,
            buyer_holding=existing,
        )
    if seller_holding.status != InvestorLoanHoldingStatus.ACTIVE:
        raise HoldingsValidationError("Only active holdings can be transferred.")
    if int(seller_holding.current_principal_minor) != principal_minor:
        raise HoldingsValidationError("Transfer principal must equal the full current holding.")
    metadata = {
        **(command.metadata or {}),
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "seller_holding_id": str(seller_holding.id),
        "purchase_id": str(command.purchase_id),
    }
    try:
        buyer_holding = InvestorLoanHolding.objects.create(
            loan=seller_holding.loan,
            investor_user_id=buyer_id,
            source_type=InvestorLoanHoldingSourceType.SECONDARY_MARKET,
            source_id=str(command.purchase_id),
            status=InvestorLoanHoldingStatus.ACTIVE,
            original_principal_minor=principal_minor,
            current_principal_minor=principal_minor,
            currency=currency,
            loan_share_ppm=seller_holding.loan_share_ppm,
            assignment_effective_at=command.assignment_effective_at,
            created_by_admin_id=command.actor.pk,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
    except IntegrityError:
        existing_after_race = _existing_holding_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return SecondaryMarketHoldingTransferResult(
            seller_holding=seller_holding,
            buyer_holding=existing_after_race,
        )

    previous_status = str(seller_holding.status)
    seller_metadata = dict(cast(dict[str, Any], seller_holding.metadata))
    seller_metadata["transferred_to_holding_id"] = str(buyer_holding.id)
    seller_metadata["secondary_market_purchase_id"] = str(command.purchase_id)
    seller_holding.status = InvestorLoanHoldingStatus.TRANSFERRED
    seller_holding.current_principal_minor = 0
    seller_holding.metadata = seller_metadata
    seller_holding.save(
        update_fields=["status", "current_principal_minor", "metadata", "updated_at"]
    )
    seller_event_metadata = {
        "purchase_id": str(command.purchase_id),
        "seller_holding_id": str(seller_holding.id),
        "buyer_holding_id": str(buyer_holding.id),
        "seller_user_id": seller_id,
        "buyer_user_id": buyer_id,
        "loan_id": str(seller_holding.loan_id),
        "currency": currency.code,
        "principal_minor": principal_minor,
    }
    _record_holding_event(
        holding=seller_holding,
        actor=command.actor,
        event_type=InvestorLoanHoldingEventType.TRANSFERRED,
        previous_status=previous_status,
        new_status=seller_holding.status,
        metadata=seller_event_metadata,
    )
    _record_holding_event(
        holding=buyer_holding,
        actor=command.actor,
        event_type=InvestorLoanHoldingEventType.CREATED,
        new_status=buyer_holding.status,
        metadata=seller_event_metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="holding.secondary_market_transferred",
            target_type="InvestorLoanHolding",
            target_id=str(seller_holding.id),
            metadata=seller_event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="InvestorLoanHoldingTransferred",
            aggregate_type="InvestorLoanHolding",
            aggregate_id=str(seller_holding.id),
            payload=seller_event_metadata,
            idempotency_key=f"holding:{seller_holding.id}:secondary-market-transferred",
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="InvestorLoanHoldingCreated",
            aggregate_type="InvestorLoanHolding",
            aggregate_id=str(buyer_holding.id),
            payload=seller_event_metadata,
            idempotency_key=f"holding:{buyer_holding.id}:created",
        )
    )
    return SecondaryMarketHoldingTransferResult(
        seller_holding=seller_holding,
        buyer_holding=buyer_holding,
    )


@transaction.atomic
def create_primary_market_holding(
    command: CreatePrimaryMarketHoldingCommand,
) -> InvestorLoanHolding:
    _require_admin_actor(command.actor)
    currency = _enabled_currency(command.currency)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    principal_minor = _validate_money(command.principal_minor, currency.code, "Holding principal")
    accepted_principal_minor = _validate_money(
        command.accepted_loan_principal_minor,
        currency.code,
        "Accepted loan principal",
    )
    if principal_minor > accepted_principal_minor:
        raise HoldingsValidationError("Holding principal cannot exceed accepted loan principal.")
    loan_share_ppm = _validated_loan_share_ppm(command.loan_share_ppm)
    if loan_share_ppm is None:
        loan_share_ppm = _loan_share_ppm(
            principal_minor=principal_minor,
            accepted_loan_principal_minor=accepted_principal_minor,
        )
    request_fingerprint = _request_fingerprint(
        command,
        currency_code=currency.code,
        principal_minor=principal_minor,
        accepted_loan_principal_minor=accepted_principal_minor,
        loan_share_ppm=loan_share_ppm,
        idempotency_key=idempotency_key,
    )
    existing = _existing_holding_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    metadata = {
        **(command.metadata or {}),
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "accepted_loan_principal_minor": accepted_principal_minor,
    }
    try:
        holding = InvestorLoanHolding.objects.create(
            loan_id=command.loan_id,
            investor_user_id=command.investor_user_id,
            source_type=InvestorLoanHoldingSourceType.PRIMARY_MARKET,
            source_id=str(command.primary_order_id),
            source_primary_order_id=command.primary_order_id,
            status=InvestorLoanHoldingStatus.ACTIVE,
            original_principal_minor=principal_minor,
            current_principal_minor=principal_minor,
            currency=currency,
            loan_share_ppm=loan_share_ppm,
            assignment_effective_at=command.assignment_effective_at,
            created_by_admin_id=command.actor.pk,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
    except IntegrityError:
        existing_after_race = _existing_holding_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    event_metadata = {
        "loan_id": str(holding.loan_id),
        "investor_user_id": str(holding.investor_user_id),
        "primary_order_id": str(command.primary_order_id),
        "currency": currency.code,
        "principal_minor": principal_minor,
        "loan_share_ppm": holding.loan_share_ppm,
    }
    _record_holding_event(
        holding=holding,
        actor=command.actor,
        event_type=InvestorLoanHoldingEventType.CREATED,
        new_status=holding.status,
        metadata=event_metadata,
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="holding.created",
            target_type="InvestorLoanHolding",
            target_id=str(holding.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="InvestorLoanHoldingCreated",
            aggregate_type="InvestorLoanHolding",
            aggregate_id=str(holding.id),
            payload=event_metadata,
            idempotency_key=f"holding:{holding.id}:created",
        )
    )
    return holding
