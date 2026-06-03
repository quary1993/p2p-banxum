from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import Model, Sum

from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
    user_can_access_financial_features,
)
from backend.apps.platform_core.domain.money import Money, MoneyError, normalize_currency
from backend.apps.platform_core.domain.time import business_date, now_utc, to_business_time
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.selectors.settings import get_platform_setting_value
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event
from backend.apps.secondary_market.models import (
    SecondaryMarketListing,
    SecondaryMarketListingEvent,
    SecondaryMarketListingEventType,
    SecondaryMarketListingPublicationType,
    SecondaryMarketListingStatus,
)


class SecondaryMarketError(ValueError):
    pass


class SecondaryMarketAuthorizationError(SecondaryMarketError):
    pass


class SecondaryMarketValidationError(SecondaryMarketError):
    pass


MAX_IDEMPOTENCY_KEY_LENGTH = 160
PRICE_BPS_MAX = 1_000_000
LISTING_CONTEXT_TYPE = "secondary_market_listing"
LISTING_FINGERPRINT_METADATA_KEY = "listing_request_fingerprint"
APPROVAL_FINGERPRINT_METADATA_KEY = "approval_request_fingerprint"
APPROVAL_IDEMPOTENCY_METADATA_KEY = "approval_idempotency_key"
REJECTION_FINGERPRINT_METADATA_KEY = "rejection_request_fingerprint"
REJECTION_IDEMPOTENCY_METADATA_KEY = "rejection_idempotency_key"
REMOVAL_FINGERPRINT_METADATA_KEY = "removal_request_fingerprint"
REMOVAL_IDEMPOTENCY_METADATA_KEY = "removal_idempotency_key"
PERFORMING_LOAN_STATUS = "funded"
NONSTANDARD_LISTABLE_STATUSES = {"late", "defaulted"}


@dataclass(frozen=True, slots=True)
class SecondaryMarketListingPricing:
    current_principal_minor: int
    transfer_price_minor: int
    discount_premium_bps: int
    accrued_interest_minor: int
    accrued_interest_from_date: Any
    accrued_interest_to_date: Any
    maker_fee_bps: int
    taker_fee_bps: int
    minimum_maker_fee_minor: int
    minimum_taker_fee_minor: int
    maker_fee_minor: int
    taker_fee_minor: int
    seller_net_proceeds_minor: int
    buyer_total_cost_minor: int
    loan_status_at_listing: str
    days_past_due: int
    last_payment_date: Any
    risk_acknowledgement_required: bool


@dataclass(frozen=True, slots=True)
class CreateSecondaryMarketListingCommand:
    actor: Model
    holding_id: str
    price_bps: int
    document_acceptance_id: str
    idempotency_key: str
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ApproveSecondaryMarketListingCommand:
    actor: Model
    listing_id: str
    reason: str
    disclosure_note: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RejectSecondaryMarketListingCommand:
    actor: Model
    listing_id: str
    reason: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RemoveSecondaryMarketListingCommand:
    actor: Model
    listing_id: str
    reason: str
    idempotency_key: str


def _model(app_label: str, model_name: str) -> Any:
    return apps.get_model(app_label, model_name)


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise SecondaryMarketValidationError(f"{label} is required.")
    return cleaned


def _clean_idempotency_key(value: str) -> str:
    key = _clean_required(value, "Idempotency key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise SecondaryMarketValidationError(
            f"Idempotency key cannot exceed {MAX_IDEMPOTENCY_KEY_LENGTH} characters."
        )
    return key


def _stable_json_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _round_minor(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _enabled_currency(currency_code: str) -> Currency:
    try:
        code = normalize_currency(currency_code)
    except MoneyError as exc:
        raise SecondaryMarketValidationError(str(exc)) from exc
    currency = Currency.objects.filter(code=code, is_enabled=True).first()
    if currency is None:
        raise SecondaryMarketValidationError(f"Currency is not enabled: {code}")
    return currency


def _validate_money(amount_minor: int, currency_code: str, label: str) -> int:
    try:
        Money(amount_minor, currency_code)
    except MoneyError as exc:
        raise SecondaryMarketValidationError(str(exc)) from exc
    if amount_minor <= 0:
        raise SecondaryMarketValidationError(f"{label} must be positive.")
    return amount_minor


def _require_investor_financial_access(actor: Model) -> None:
    if not user_can_access_financial_features(actor):
        raise SecondaryMarketAuthorizationError(
            "Investor account cannot access secondary-market listing features."
        )


def _require_admin_actor(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise SecondaryMarketAuthorizationError(
            "Only an active admin can manage secondary-market listings."
        )


def _actor_account_type(actor: Model) -> str:
    return str(getattr(actor, "account_type", ""))


def _platform_int_setting(key: str, default: int, *, minimum: int = 0) -> int:
    value = get_platform_setting_value(key, default)
    if type(value) is int and value >= minimum:
        return value
    return default


def _minimum_fee_minor(setting_key: str, currency_code: str) -> int:
    configured = get_platform_setting_value(setting_key, {})
    if isinstance(configured, dict):
        value = configured.get(currency_code)
        if type(value) is int and value >= 0:
            return value
    return 0


def _fee_minor(transfer_price_minor: int, fee_bps: int, minimum_fee_minor: int) -> int:
    calculated = _round_minor(
        Decimal(transfer_price_minor) * Decimal(fee_bps) / Decimal(10_000)
    )
    return max(calculated, minimum_fee_minor)


def _transfer_price_minor(current_principal_minor: int, price_bps: int) -> int:
    return _round_minor(
        Decimal(current_principal_minor) * Decimal(price_bps) / Decimal(10_000)
    )


def _last_payment_date(loan_id: str) -> Any:
    event_model = _model("servicing", "BorrowerRepaymentEvent")
    event = (
        event_model.objects.filter(loan_id=loan_id)
        .order_by("-value_date", "-created_at")
        .first()
    )
    if event is None:
        return None
    return cast(Any, event).value_date


def _paid_totals_by_installment_id(loan_id: str) -> dict[str, int]:
    event_model = _model("servicing", "BorrowerRepaymentEvent")
    rows = (
        event_model.objects.filter(loan_id=loan_id)
        .values("installment_id")
        .annotate(
            principal_sum=Sum("principal_applied_minor"),
            interest_sum=Sum("interest_applied_minor"),
        )
    )
    return {
        str(row["installment_id"]): int(row["principal_sum"] or 0) + int(row["interest_sum"] or 0)
        for row in rows
    }


def _days_past_due(loan: Model, as_of_date: Any) -> int:
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) == PERFORMING_LOAN_STATUS:
        return 0
    installment_model = _model("loans", "LoanInstallment")
    paid_totals = _paid_totals_by_installment_id(str(loan_ref.id))
    installments = installment_model.objects.filter(
        loan_id=loan_ref.id,
        schedule_version=loan_ref.schedule_version,
    ).order_by("due_date", "installment_number", "id")
    for installment in installments:
        installment_ref = cast(Any, installment)
        scheduled = int(installment_ref.principal_minor) + int(installment_ref.interest_minor)
        paid = paid_totals.get(str(installment_ref.id), 0)
        if paid < scheduled:
            return int(max(0, (as_of_date - installment_ref.due_date).days))
    return 0


def _accrued_interest(
    *,
    holding: Model,
    loan: Model,
    last_payment_date: Any,
    as_of_date: Any,
) -> tuple[int, Any, Any]:
    loan_ref = cast(Any, loan)
    if str(loan_ref.status) != PERFORMING_LOAN_STATUS:
        return 0, None, as_of_date
    holding_ref = cast(Any, holding)
    assigned_date = to_business_time(holding_ref.assignment_effective_at).date()
    from_date = max(assigned_date, last_payment_date) if last_payment_date else assigned_date
    days = max(0, (as_of_date - from_date).days)
    if days == 0:
        return 0, from_date, as_of_date
    accrued = (
        Decimal(int(holding_ref.current_principal_minor))
        * Decimal(int(loan_ref.interest_rate_bps))
        * Decimal(days)
        / Decimal(10_000 * 365)
    )
    return _round_minor(accrued), from_date, as_of_date


def _pricing_snapshot(
    *,
    holding: Model,
    loan: Model,
    price_bps: int,
    as_of_date: Any,
) -> SecondaryMarketListingPricing:
    holding_ref = cast(Any, holding)
    loan_ref = cast(Any, loan)
    currency_code = str(holding_ref.currency_id)
    current_principal_minor = _validate_money(
        int(holding_ref.current_principal_minor),
        currency_code,
        "Current holding principal",
    )
    transfer_price_minor = _transfer_price_minor(current_principal_minor, price_bps)
    _validate_money(transfer_price_minor, currency_code, "Transfer price")
    maker_fee_bps = _platform_int_setting("secondary_market.maker_fee_bps", 25)
    taker_fee_bps = _platform_int_setting("secondary_market.taker_fee_bps", 75)
    minimum_maker_fee_minor = _minimum_fee_minor(
        "secondary_market.minimum_maker_fee_minor_by_currency",
        currency_code,
    )
    minimum_taker_fee_minor = _minimum_fee_minor(
        "secondary_market.minimum_taker_fee_minor_by_currency",
        currency_code,
    )
    maker_fee_minor = _fee_minor(transfer_price_minor, maker_fee_bps, minimum_maker_fee_minor)
    taker_fee_minor = _fee_minor(transfer_price_minor, taker_fee_bps, minimum_taker_fee_minor)
    last_payment_date = _last_payment_date(str(loan_ref.id))
    accrued_interest_minor, accrued_from_date, accrued_to_date = _accrued_interest(
        holding=holding,
        loan=loan,
        last_payment_date=last_payment_date,
        as_of_date=as_of_date,
    )
    seller_net = transfer_price_minor + accrued_interest_minor - maker_fee_minor
    if seller_net < 0:
        raise SecondaryMarketValidationError("Seller fee exceeds listing proceeds.")
    buyer_total = transfer_price_minor + accrued_interest_minor + taker_fee_minor
    status = str(loan_ref.status)
    return SecondaryMarketListingPricing(
        current_principal_minor=current_principal_minor,
        transfer_price_minor=transfer_price_minor,
        discount_premium_bps=price_bps - 10_000,
        accrued_interest_minor=accrued_interest_minor,
        accrued_interest_from_date=accrued_from_date,
        accrued_interest_to_date=accrued_to_date,
        maker_fee_bps=maker_fee_bps,
        taker_fee_bps=taker_fee_bps,
        minimum_maker_fee_minor=minimum_maker_fee_minor,
        minimum_taker_fee_minor=minimum_taker_fee_minor,
        maker_fee_minor=maker_fee_minor,
        taker_fee_minor=taker_fee_minor,
        seller_net_proceeds_minor=seller_net,
        buyer_total_cost_minor=buyer_total,
        loan_status_at_listing=status,
        days_past_due=_days_past_due(loan, as_of_date),
        last_payment_date=last_payment_date,
        risk_acknowledgement_required=status != PERFORMING_LOAN_STATUS,
    )


def _validate_listing_price_bps(price_bps: int) -> int:
    if type(price_bps) is not int:
        raise SecondaryMarketValidationError("Sale price percentage must be an integer bps value.")
    if price_bps <= 0:
        raise SecondaryMarketValidationError("Sale price percentage must be positive.")
    if price_bps > PRICE_BPS_MAX:
        raise SecondaryMarketValidationError("Sale price percentage is outside the launch limit.")
    return price_bps


def _validate_listing_acceptance(
    *,
    acceptance_id: str,
    actor: Model,
    holding: Model,
) -> Model:
    acceptance_model = _model("documents", "DocumentAcceptanceEvidence")
    acceptance = cast(
        Model | None,
        acceptance_model.objects.select_related("template", "template_version")
        .filter(id=acceptance_id, user_id=actor.pk)
        .first(),
    )
    if acceptance is None:
        raise SecondaryMarketValidationError("Document acceptance does not exist.")
    acceptance_ref = cast(Any, acceptance)
    if str(acceptance_ref.category) != "secondary_market_listing":
        raise SecondaryMarketValidationError("Document acceptance category is not valid.")
    if str(acceptance_ref.context_type) != LISTING_CONTEXT_TYPE:
        raise SecondaryMarketValidationError("Document acceptance context is not valid.")
    if str(acceptance_ref.context_id) != str(cast(Any, holding).id):
        raise SecondaryMarketValidationError(
            "Document acceptance does not match this holding."
        )
    if str(acceptance_ref.template.current_published_version_id) != str(
        acceptance_ref.template_version_id
    ):
        raise SecondaryMarketValidationError("Document acceptance is no longer current.")
    return acceptance


def _listing_request_fingerprint(
    command: CreateSecondaryMarketListingCommand,
    *,
    seller_user_id: str,
    loan_id: str,
    pricing: SecondaryMarketListingPricing,
    currency_code: str,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "seller_user_id": seller_user_id,
            "holding_id": str(command.holding_id),
            "loan_id": loan_id,
            "price_bps": command.price_bps,
            "document_acceptance_id": str(command.document_acceptance_id),
            "currency": currency_code,
            "current_principal_minor": pricing.current_principal_minor,
            "transfer_price_minor": pricing.transfer_price_minor,
            "accrued_interest_minor": pricing.accrued_interest_minor,
            "maker_fee_bps": pricing.maker_fee_bps,
            "taker_fee_bps": pricing.taker_fee_bps,
            "notes": command.notes.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _admin_transition_fingerprint(
    *,
    listing_id: str,
    action: str,
    reason: str,
    disclosure_note: str = "",
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "listing_id": str(listing_id),
            "action": action,
            "reason": reason.strip(),
            "disclosure_note": disclosure_note.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _existing_listing_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> SecondaryMarketListing | None:
    existing = SecondaryMarketListing.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(LISTING_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise SecondaryMarketValidationError(
            "Idempotency key was already used for a different listing request."
        )
    return existing


def _record_listing_event(
    *,
    listing: SecondaryMarketListing,
    actor: Model,
    event_type: SecondaryMarketListingEventType,
    previous_status: str = "",
    new_status: str = "",
    note: str = "",
    metadata: dict[str, Any] | None = None,
) -> SecondaryMarketListingEvent:
    return cast(
        SecondaryMarketListingEvent,
        SecondaryMarketListingEvent.objects.create(
            listing=listing,
            holding_id=listing.holding_id,
            loan_id=listing.loan_id,
            seller_user_id=listing.seller_user_id,
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
    listing: SecondaryMarketListing,
    metadata: dict[str, Any],
) -> None:
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action=action,
            target_type="SecondaryMarketListing",
            target_id=str(listing.id),
            metadata=metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type=event_type,
            aggregate_type="SecondaryMarketListing",
            aggregate_id=str(listing.id),
            payload=metadata,
            idempotency_key=f"secondary-listing:{listing.id}:{event_type}",
        )
    )


def _open_listing_exists_for_holding(holding_id: str) -> bool:
    return SecondaryMarketListing.objects.filter(
        holding_id=cast(Any, holding_id),
        status__in=[
            SecondaryMarketListingStatus.ACTIVE,
            SecondaryMarketListingStatus.APPROVAL_REQUESTED,
        ],
    ).exists()


@transaction.atomic
def create_secondary_market_listing(
    command: CreateSecondaryMarketListingCommand,
) -> SecondaryMarketListing:
    _require_investor_financial_access(command.actor)
    seller_user_id = str(command.actor.pk)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    price_bps = _validate_listing_price_bps(command.price_bps)
    holding_model = _model("holdings", "InvestorLoanHolding")
    holding = cast(
        Model | None,
        holding_model.objects.select_for_update()
        .select_related("loan", "currency")
        .filter(id=command.holding_id, investor_user_id=command.actor.pk)
        .first(),
    )
    if holding is None:
        raise SecondaryMarketValidationError("Holding does not exist.")
    holding_ref = cast(Any, holding)
    loan = cast(Model, holding_ref.loan)
    loan_ref = cast(Any, loan)
    if str(holding_ref.status) != "active":
        raise SecondaryMarketValidationError("Only active holdings can be listed.")
    if int(holding_ref.current_principal_minor) <= 0:
        raise SecondaryMarketValidationError("Only holdings with principal can be listed.")
    if str(holding_ref.currency_id) != str(loan_ref.currency_id):
        raise SecondaryMarketValidationError("Holding currency does not match loan currency.")
    loan_status = str(loan_ref.status)
    if loan_status not in {PERFORMING_LOAN_STATUS, *NONSTANDARD_LISTABLE_STATUSES}:
        raise SecondaryMarketValidationError("Loan status is not listable on the secondary market.")
    currency = _enabled_currency(str(holding_ref.currency_id))
    acceptance = _validate_listing_acceptance(
        acceptance_id=command.document_acceptance_id,
        actor=command.actor,
        holding=holding,
    )
    snapshot_date = business_date(now_utc())
    pricing = _pricing_snapshot(
        holding=holding,
        loan=loan,
        price_bps=price_bps,
        as_of_date=snapshot_date,
    )
    request_fingerprint = _listing_request_fingerprint(
        command,
        seller_user_id=seller_user_id,
        loan_id=str(loan_ref.id),
        pricing=pricing,
        currency_code=currency.code,
        idempotency_key=idempotency_key,
    )
    existing = _existing_listing_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    if _open_listing_exists_for_holding(str(holding_ref.id)):
        raise SecondaryMarketValidationError(
            "Holding already has an open secondary-market listing."
        )
    now = now_utc()
    is_performing = loan_status == PERFORMING_LOAN_STATUS
    status = (
        SecondaryMarketListingStatus.ACTIVE
        if is_performing
        else SecondaryMarketListingStatus.APPROVAL_REQUESTED
    )
    publication_type = (
        SecondaryMarketListingPublicationType.AUTOMATIC
        if is_performing
        else SecondaryMarketListingPublicationType.ADMIN_APPROVED
    )
    metadata = {
        LISTING_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "pricing_date": str(snapshot_date),
        "notes": command.notes.strip(),
        "terms_context": {
            "context_type": LISTING_CONTEXT_TYPE,
            "context_id": str(holding_ref.id),
        },
        "accrual_day_count": "ACT/365",
    }
    try:
        listing = SecondaryMarketListing.objects.create(
            holding=cast(Any, holding),
            loan=cast(Any, loan),
            seller_user_id=command.actor.pk,
            status=status,
            publication_type=publication_type,
            current_principal_minor=pricing.current_principal_minor,
            currency=currency,
            price_bps=price_bps,
            transfer_price_minor=pricing.transfer_price_minor,
            discount_premium_bps=pricing.discount_premium_bps,
            accrued_interest_minor=pricing.accrued_interest_minor,
            accrued_interest_from_date=pricing.accrued_interest_from_date,
            accrued_interest_to_date=pricing.accrued_interest_to_date,
            maker_fee_bps=pricing.maker_fee_bps,
            taker_fee_bps=pricing.taker_fee_bps,
            minimum_maker_fee_minor=pricing.minimum_maker_fee_minor,
            minimum_taker_fee_minor=pricing.minimum_taker_fee_minor,
            maker_fee_minor=pricing.maker_fee_minor,
            taker_fee_minor=pricing.taker_fee_minor,
            seller_net_proceeds_minor=pricing.seller_net_proceeds_minor,
            buyer_total_cost_minor=pricing.buyer_total_cost_minor,
            loan_status_at_listing=pricing.loan_status_at_listing,
            days_past_due=pricing.days_past_due,
            last_payment_date=pricing.last_payment_date,
            risk_acknowledgement_required=pricing.risk_acknowledgement_required,
            document_acceptance=cast(Any, acceptance),
            listed_at=now if is_performing else None,
            created_by_user_id=command.actor.pk,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
    except IntegrityError:
        existing_after_race = _existing_listing_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is not None:
            return existing_after_race
        if _open_listing_exists_for_holding(str(holding_ref.id)):
            raise SecondaryMarketValidationError(
                "Holding already has an open secondary-market listing."
            ) from None
        raise
    event_metadata = {
        "seller_user_id": seller_user_id,
        "holding_id": str(holding_ref.id),
        "loan_id": str(loan_ref.id),
        "currency": currency.code,
        "current_principal_minor": pricing.current_principal_minor,
        "price_bps": price_bps,
        "transfer_price_minor": pricing.transfer_price_minor,
        "accrued_interest_minor": pricing.accrued_interest_minor,
        "maker_fee_minor": pricing.maker_fee_minor,
        "taker_fee_minor": pricing.taker_fee_minor,
        "loan_status_at_listing": pricing.loan_status_at_listing,
        "risk_acknowledgement_required": pricing.risk_acknowledgement_required,
    }
    _record_listing_event(
        listing=listing,
        actor=command.actor,
        event_type=SecondaryMarketListingEventType.CREATED,
        new_status=listing.status,
        note=command.notes,
        metadata=event_metadata,
    )
    follow_on_event = (
        SecondaryMarketListingEventType.AUTO_PUBLISHED
        if is_performing
        else SecondaryMarketListingEventType.APPROVAL_REQUESTED
    )
    _record_listing_event(
        listing=listing,
        actor=command.actor,
        event_type=follow_on_event,
        new_status=listing.status,
        metadata=event_metadata,
    )
    _record_audit_and_domain(
        actor=command.actor,
        action="secondary_market.listing_created",
        event_type="SecondaryMarketListingCreated",
        listing=listing,
        metadata=event_metadata,
    )
    return listing


def _ensure_transition_idempotency(
    *,
    listing: SecondaryMarketListing,
    metadata_key: str,
    idempotency_key_metadata_key: str,
    idempotency_key: str,
    expected_fingerprint: str,
    terminal_status: SecondaryMarketListingStatus,
) -> bool:
    metadata = cast(dict[str, Any], listing.metadata)
    if str(listing.status) != terminal_status:
        return False
    if (
        metadata.get(idempotency_key_metadata_key) == idempotency_key
        and metadata.get(metadata_key) == expected_fingerprint
    ):
        return True
    raise SecondaryMarketValidationError("Listing is not in the required status.")


@transaction.atomic
def approve_secondary_market_listing(
    command: ApproveSecondaryMarketListingCommand,
) -> SecondaryMarketListing:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    reason = _clean_required(command.reason, "Approval reason")
    disclosure_note = _clean_required(command.disclosure_note, "Disclosure note")
    listing = (
        SecondaryMarketListing.objects.select_for_update()
        .filter(id=command.listing_id)
        .first()
    )
    if listing is None:
        raise SecondaryMarketValidationError("Secondary-market listing does not exist.")
    fingerprint = _admin_transition_fingerprint(
        listing_id=str(listing.id),
        action="approve",
        reason=reason,
        disclosure_note=disclosure_note,
        idempotency_key=idempotency_key,
    )
    if _ensure_transition_idempotency(
        listing=listing,
        metadata_key=APPROVAL_FINGERPRINT_METADATA_KEY,
        idempotency_key_metadata_key=APPROVAL_IDEMPOTENCY_METADATA_KEY,
        idempotency_key=idempotency_key,
        expected_fingerprint=fingerprint,
        terminal_status=SecondaryMarketListingStatus.ACTIVE,
    ):
        return listing
    if listing.status != SecondaryMarketListingStatus.APPROVAL_REQUESTED:
        raise SecondaryMarketValidationError("Only requested listings can be approved.")
    previous_status = str(listing.status)
    now = now_utc()
    listing.status = SecondaryMarketListingStatus.ACTIVE
    listing.listed_at = now
    listing.approved_by_admin_id = command.actor.pk
    listing.approved_at = now
    listing.approval_reason = reason
    listing.public_disclosure_note = disclosure_note
    listing.metadata = {
        **cast(dict[str, Any], listing.metadata),
        APPROVAL_IDEMPOTENCY_METADATA_KEY: idempotency_key,
        APPROVAL_FINGERPRINT_METADATA_KEY: fingerprint,
    }
    listing.save(
        update_fields=[
            "status",
            "listed_at",
            "approved_by_admin_id",
            "approved_at",
            "approval_reason",
            "public_disclosure_note",
            "metadata",
            "updated_at",
        ]
    )
    event_metadata = {
        "reason": reason,
        "disclosure_note": disclosure_note,
        "approved_by_admin_id": str(command.actor.pk),
    }
    _record_listing_event(
        listing=listing,
        actor=command.actor,
        event_type=SecondaryMarketListingEventType.APPROVED,
        previous_status=previous_status,
        new_status=listing.status,
        note=reason,
        metadata=event_metadata,
    )
    _record_audit_and_domain(
        actor=command.actor,
        action="secondary_market.listing_approved",
        event_type="SecondaryMarketListingApproved",
        listing=listing,
        metadata=event_metadata,
    )
    return listing


@transaction.atomic
def reject_secondary_market_listing(
    command: RejectSecondaryMarketListingCommand,
) -> SecondaryMarketListing:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    reason = _clean_required(command.reason, "Rejection reason")
    listing = (
        SecondaryMarketListing.objects.select_for_update()
        .filter(id=command.listing_id)
        .first()
    )
    if listing is None:
        raise SecondaryMarketValidationError("Secondary-market listing does not exist.")
    fingerprint = _admin_transition_fingerprint(
        listing_id=str(listing.id),
        action="reject",
        reason=reason,
        idempotency_key=idempotency_key,
    )
    if _ensure_transition_idempotency(
        listing=listing,
        metadata_key=REJECTION_FINGERPRINT_METADATA_KEY,
        idempotency_key_metadata_key=REJECTION_IDEMPOTENCY_METADATA_KEY,
        idempotency_key=idempotency_key,
        expected_fingerprint=fingerprint,
        terminal_status=SecondaryMarketListingStatus.REJECTED,
    ):
        return listing
    if listing.status != SecondaryMarketListingStatus.APPROVAL_REQUESTED:
        raise SecondaryMarketValidationError("Only requested listings can be rejected.")
    previous_status = str(listing.status)
    now = now_utc()
    listing.status = SecondaryMarketListingStatus.REJECTED
    listing.rejected_by_admin_id = command.actor.pk
    listing.rejected_at = now
    listing.rejection_reason = reason
    listing.metadata = {
        **cast(dict[str, Any], listing.metadata),
        REJECTION_IDEMPOTENCY_METADATA_KEY: idempotency_key,
        REJECTION_FINGERPRINT_METADATA_KEY: fingerprint,
    }
    listing.save(
        update_fields=[
            "status",
            "rejected_by_admin_id",
            "rejected_at",
            "rejection_reason",
            "metadata",
            "updated_at",
        ]
    )
    event_metadata = {
        "reason": reason,
        "rejected_by_admin_id": str(command.actor.pk),
    }
    _record_listing_event(
        listing=listing,
        actor=command.actor,
        event_type=SecondaryMarketListingEventType.REJECTED,
        previous_status=previous_status,
        new_status=listing.status,
        note=reason,
        metadata=event_metadata,
    )
    _record_audit_and_domain(
        actor=command.actor,
        action="secondary_market.listing_rejected",
        event_type="SecondaryMarketListingRejected",
        listing=listing,
        metadata=event_metadata,
    )
    return listing


@transaction.atomic
def remove_secondary_market_listing(
    command: RemoveSecondaryMarketListingCommand,
) -> SecondaryMarketListing:
    _require_admin_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    reason = _clean_required(command.reason, "Removal reason")
    listing = (
        SecondaryMarketListing.objects.select_for_update()
        .filter(id=command.listing_id)
        .first()
    )
    if listing is None:
        raise SecondaryMarketValidationError("Secondary-market listing does not exist.")
    fingerprint = _admin_transition_fingerprint(
        listing_id=str(listing.id),
        action="remove",
        reason=reason,
        idempotency_key=idempotency_key,
    )
    if _ensure_transition_idempotency(
        listing=listing,
        metadata_key=REMOVAL_FINGERPRINT_METADATA_KEY,
        idempotency_key_metadata_key=REMOVAL_IDEMPOTENCY_METADATA_KEY,
        idempotency_key=idempotency_key,
        expected_fingerprint=fingerprint,
        terminal_status=SecondaryMarketListingStatus.REMOVED,
    ):
        return listing
    if listing.status not in {
        SecondaryMarketListingStatus.ACTIVE,
        SecondaryMarketListingStatus.APPROVAL_REQUESTED,
    }:
        raise SecondaryMarketValidationError("Only open listings can be removed.")
    previous_status = str(listing.status)
    now = now_utc()
    listing.status = SecondaryMarketListingStatus.REMOVED
    listing.removed_by_admin_id = command.actor.pk
    listing.removed_at = now
    listing.removal_reason = reason
    listing.metadata = {
        **cast(dict[str, Any], listing.metadata),
        REMOVAL_IDEMPOTENCY_METADATA_KEY: idempotency_key,
        REMOVAL_FINGERPRINT_METADATA_KEY: fingerprint,
    }
    listing.save(
        update_fields=[
            "status",
            "removed_by_admin_id",
            "removed_at",
            "removal_reason",
            "metadata",
            "updated_at",
        ]
    )
    event_metadata = {
        "reason": reason,
        "removed_by_admin_id": str(command.actor.pk),
    }
    _record_listing_event(
        listing=listing,
        actor=command.actor,
        event_type=SecondaryMarketListingEventType.REMOVED,
        previous_status=previous_status,
        new_status=listing.status,
        note=reason,
        metadata=event_metadata,
    )
    _record_audit_and_domain(
        actor=command.actor,
        action="secondary_market.listing_removed",
        event_type="SecondaryMarketListingRemoved",
        listing=listing,
        metadata=event_metadata,
    )
    return listing


def list_active_secondary_market_listings(
    *,
    actor: Model,
    limit: int = 100,
) -> list[SecondaryMarketListing]:
    _require_investor_financial_access(actor)
    safe_limit = min(max(int(limit), 1), 250)
    return list(
        SecondaryMarketListing.objects.select_related("holding", "loan", "currency")
        .filter(status=SecondaryMarketListingStatus.ACTIVE)
        .order_by("-listed_at", "-created_at", "-id")[:safe_limit]
    )
