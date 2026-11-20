# IP of Webby-Soft SRL.
# build-origin: ATEW5bUMtfGj80bXzkGFbtEIwTx0cb6Qig3qkx90kV_Srfdc012ga6e8Ddq5v4qj1nbItbZAfx4ZDA==
from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from datetime import date, timedelta
from importlib import import_module
from typing import Any, NoReturn, cast

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Model, Q, Sum

from backend.apps.marketplace_primary import investor_limit as investor_limits
from backend.apps.marketplace_primary import notices as investor_notices
from backend.apps.marketplace_primary.models import (
    LoanOpeningAlert,
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
from backend.apps.platform_core.domain.actors import ActorRef
from backend.apps.platform_core.domain.investor_limit import (
    SWISS_INVESTOR_LIMIT_CODE,
    InvestorLimit,
    swiss_investor_limit_message,
)
from backend.apps.platform_core.domain.money import (
    Money,
    MoneyError,
    format_amount_minor,
    normalize_currency,
)
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
    SensitiveActionPinError,
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


class MarketplacePrimaryOrderNotPendingError(MarketplacePrimaryValidationError):
    """The order was closed (for example replaced or expired) before allocation."""

    code = "order_not_pending"


class MarketplacePrimarySwissInvestorLimitError(MarketplacePrimaryValidationError):
    """A new investor needs a place on a Swiss-borrower loan that has none left (409)."""

    code = SWISS_INVESTOR_LIMIT_CODE


MAX_IDEMPOTENCY_KEY_LENGTH = 160
PENDING_ORDER_CAP_DEFAULT = 50
# An order the investor did not confirm within this time no longer counts as an
# open intent: the next order of the same investor closes it (no money moves).
PENDING_ORDER_TTL_MINUTES_DEFAULT = 60
ORDER_NOT_PENDING_MESSAGE = (
    "This order was closed before it was confirmed. Nothing was invested. Place the order again."
)
ORDER_FINGERPRINT_METADATA_KEY = "request_fingerprint"
ALLOCATION_FINGERPRINT_METADATA_KEY = "allocation_request_fingerprint"
ALLOCATION_IDEMPOTENCY_METADATA_KEY = "allocation_idempotency_key"
RELEASE_FINGERPRINT_METADATA_KEY = "release_request_fingerprint"
RELEASE_IDEMPOTENCY_METADATA_KEY = "release_idempotency_key"
CLOSE_FINGERPRINT_METADATA_KEY = "close_request_fingerprint"
CANCEL_FINGERPRINT_METADATA_KEY = "cancel_request_fingerprint"
ONE_HUNDRED_PERCENT_PPM = 1_000_000

logger = logging.getLogger(__name__)


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
    pin: str = dataclass_field(default="", repr=False)
    ip_address: str | None = None
    user_agent: str = ""
    # 18.9 (E-03): the investor confirmed the sandbox notice of this version (sandbox mode only).
    sandbox_notice_confirmed: bool = False
    sandbox_notice_version: str = ""


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


def _require_no_compliance_block(actor: Model) -> None:
    """18.10: declarations missing, a necessary review open or re-verification overdue."""
    declarations: Any = import_module("backend.apps.kyc_compliance.declarations")
    reason = declarations.investment_block(actor)
    if reason is not None:
        raise MarketplacePrimaryValidationError(declarations.BLOCK_MESSAGES[reason])


def _require_no_compliance_block_locked(actor: Model) -> None:
    """Audit S7-2: the same check under the investor row lock, just before money is reserved."""
    declarations: Any = import_module("backend.apps.kyc_compliance.declarations")
    try:
        declarations.assert_can_invest_locked(actor)
    except declarations.InvestmentComplianceBlock as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc


def _require_verified_securities(loan: Model) -> None:
    """Audit S7-4: a verified loan takes no new order or allocation while a security needs a
    new verification. Called with the loan row locked."""
    proofs: Any = import_module("backend.apps.loans.security_proofs")
    try:
        proofs.assert_investment_allowed(loan)
    except proofs.SecurityProofError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc


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


def order_reserved_amount_minor(order: Model) -> int:
    """What the order reserved: the principal, plus the accrued interest of an 18.7 offer."""
    metadata = cast(dict[str, Any], getattr(order, "metadata", None) or {})
    allocated = int(cast(Any, order).allocated_amount_minor)
    return allocated + int(metadata.get("price_accrued_interest_minor", 0) or 0)


def _originator_services() -> Any:
    return import_module("backend.apps.originator_claims.services")


def _resolve_fully_subscribed_originator_round(*, actor: Model, loan_id: str) -> None:
    """Close a full v2 LO round only after its reservation transaction commits."""

    loan_model = _model("loans", "Loan")
    loan = loan_model.objects.filter(
        id=loan_id,
        product_type="originator_claim",
        status="published",
    ).first()
    if loan is None:
        return
    profile = _originator_subscription_profile(cast(Model, loan))
    if profile is None:
        return
    profile_ref = cast(Any, profile)
    if bool(profile_ref.is_on_hold) or str(profile_ref.opportunity_status) != "open":
        return
    if _loan_remaining_capacity_minor(cast(Model, loan)) != 0:
        return

    originator = _originator_services()
    try:
        originator.close_originator_subscription_round(
            originator.CloseOriginatorSubscriptionRoundCommand(
                actor=actor,
                loan_id=loan_id,
                as_of_date=business_date(now_utc()),
                close_reason="Loan Originator subscription fully allocated.",
                idempotency_key=f"originator-round-auto-close:{loan_id}",
            )
        )
    except originator.OriginatorOfferFailedError:
        # Re-audit R6-1: F04 failed the offer in its own committed transaction (participations
        # cancelled, reservations released, investors told). Not a close failure.
        return
    except Exception as exc:  # The reservation is already committed by design.
        try:
            originator.mark_originator_funding_close_failed(
                triggering_actor=actor,
                loan_id=loan_id,
                as_of_date=business_date(now_utc()),
                resolution_action="full-subscription auto-close",
                error=exc,
            )
        except Exception:
            logger.exception(
                "Could not record Loan Originator funding-close failure for loan %s",
                loan_id,
            )


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
    profile = _originator_subscription_profile(loan)
    if profile is not None:
        profile_ref = cast(Any, profile)
        if bool(profile_ref.is_on_hold):
            raise MarketplacePrimaryValidationError(
                "This Loan Originator subscription is on administrative hold."
            )
        if str(profile_ref.opportunity_status) != "open":
            raise MarketplacePrimaryValidationError(
                "This Loan Originator subscription is not open for investment."
            )


def _originator_subscription_profile(loan: Model) -> Model | None:
    loan_ref = cast(Any, loan)
    if str(loan_ref.product_type) != "originator_claim":
        return None
    profile_model = _model("originator_claims", "OriginatorLoanProfile")
    profile = cast(
        Model | None,
        profile_model.objects.select_related("originator")
        .filter(loan_id=loan_ref.id, distribution_model="par_component_v2")
        .first(),
    )
    return profile


def _loan_remaining_capacity_minor(loan: Model) -> int:
    loan_ref = cast(Any, loan)
    profile = _originator_subscription_profile(loan)
    if profile is not None:
        originator = _originator_services()
        try:
            return int(originator.originator_subscription_available_minor(profile))
        except originator.OriginatorClaimsError as exc:
            raise MarketplacePrimaryValidationError(str(exc)) from exc
    return int(loan_ref.principal_minor) - int(loan_ref.committed_principal_minor)


def _loan_minimum_investment_minor(loan: Model) -> int:
    profile = _originator_subscription_profile(loan)
    if profile is not None:
        return int(cast(Any, profile).minimum_investment_minor)
    return _minimum_investment_minor(str(cast(Any, loan).currency_id))


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


def creditor_mode_fields(loan: Model) -> dict[str, Any]:
    """18.9: the Swiss creditor mode of the loan's borrower and, in sandbox mode, the notice."""
    regimes = import_module("backend.apps.marketplace_primary.creditor_regime")
    return {
        "creditor_mode": regimes.creditor_mode_payload(loan),
        "sandbox_notice": regimes.sandbox_notice(loan, borrower_name=_borrower_public_name(loan)),
    }


def _assert_sandbox_notice_confirmed(loan: Model, command: Any) -> None:
    """E-03 / F06.2: a borrower in sandbox mode needs the investor's explicit confirmation of the
    notice (the version shown), recorded with the order."""
    regimes = import_module("backend.apps.marketplace_primary.creditor_regime")
    notice = regimes.sandbox_notice(loan, borrower_name=_borrower_public_name(loan))
    if notice is None:
        return
    if not bool(getattr(command, "sandbox_notice_confirmed", False)) or str(
        getattr(command, "sandbox_notice_version", "") or ""
    ) != str(notice["version"]):
        raise MarketplacePrimaryValidationError(
            "Confirm that you read the sandbox notice of this borrower before investing."
        )


def _borrower_public_name(loan: Model) -> str:
    loan_ref = cast(Any, loan)
    if str(loan_ref.product_type) == "originator_claim":
        profile = (
            _model("originator_claims", "OriginatorLoanProfile")
            .objects.filter(loan_id=loan_ref.pk)
            .only("borrower_display_name")
            .first()
        )
        return str(getattr(profile, "borrower_display_name", "") or "")
    borrower = getattr(loan_ref, "borrower", None)
    return str(getattr(borrower, "legal_name", "") or "")


def _loan_investor_limit(loan: Model) -> InvestorLimit:
    """The Swiss-borrower investor limit of a loan (MKT-DEC-028); count under the loan lock."""
    return investor_limits.loan_investor_limit(loan)


def _raise_swiss_investor_limit(limit: InvestorLimit, *, prefix: str = "") -> NoReturn:
    message = swiss_investor_limit_message(int(limit.max_investors or 0))
    raise MarketplacePrimarySwissInvestorLimitError(f"{prefix}{message}")


def _swiss_new_investor_minimum_message(loan: Model, limit: InvestorLimit, minimum: int) -> str:
    amount = format_amount_minor(minimum, str(cast(Any, loan).currency_id))
    return (
        f"This loan to a Swiss company can have at most {limit.max_investors} investors, "
        f"so the minimum for a new investor is now {amount}. Invest at least {amount}."
    )


def _order_minimum_minor(
    *,
    loan: Model,
    limit: InvestorLimit,
    investor_user_id: str,
    remaining_capacity_minor: int,
) -> int:
    """The minimum this investor must invest in the loan now.

    Without a Swiss-borrower limit this is the loan minimum. With it, a new investor
    must invest the minimum that lets the places left fill the loan, and is refused
    (409 ``swiss_investor_limit``) when no place is left; an investor who already
    invests keeps the loan minimum, capped by the remaining capacity.
    """
    minimum = _loan_minimum_investment_minor(loan)
    if not limit.applies or remaining_capacity_minor <= 0:
        return minimum
    if limit.refuses_new_investor(investor_user_id):
        _raise_swiss_investor_limit(limit)
    return limit.investor_minimum_minor(
        investor_user_id=investor_user_id,
        minimum_minor=minimum,
        remaining_minor=remaining_capacity_minor,
    )


def _assert_order_within_investor_limit(
    *,
    loan: Model,
    limit: InvestorLimit,
    order: PrimaryInvestmentOrder,
    remaining_capacity_minor: int,
) -> None:
    """At allocation, a new investor still needs a free place and the minimum of now.

    Other investors may have joined since the order was created: the order is refused
    (it stays pending, nothing moves) and the investor places a new one.
    """
    investor_user_id = str(order.investor_user_id)
    if not limit.applies or remaining_capacity_minor <= 0 or limit.is_investor(investor_user_id):
        return
    minimum = _order_minimum_minor(
        loan=loan,
        limit=limit,
        investor_user_id=investor_user_id,
        remaining_capacity_minor=remaining_capacity_minor,
    )
    if int(order.requested_amount_minor) < minimum:
        raise MarketplacePrimaryValidationError(
            f"{_swiss_new_investor_minimum_message(loan, limit, minimum)} "
            "Nothing was invested. Place the order again."
        )


def _pending_order_cap() -> int:
    value = get_platform_setting_value("investment.pending_order_cap", PENDING_ORDER_CAP_DEFAULT)
    if type(value) is int and value > 0:
        return value
    return PENDING_ORDER_CAP_DEFAULT


def _pending_order_ttl_minutes() -> int:
    value = get_platform_setting_value(
        "investment.pending_order_ttl_minutes",
        PENDING_ORDER_TTL_MINUTES_DEFAULT,
    )
    if type(value) is int and value > 0:
        return value
    return PENDING_ORDER_TTL_MINUTES_DEFAULT


def _close_abandoned_pending_orders(*, actor: Model, investor_user_id: str, loan_id: str) -> int:
    """Close the investor's own unconfirmed orders before a new order is created.

    A pending order holds no balance and no loan capacity. It is left behind when a
    confirmation fails (wrong or expired code, lost race) or is abandoned. The
    investor cannot cancel it, so the platform closes it here: every earlier
    pending order on the same loan (replaced by the new order) and every pending
    order older than the pending-order time limit. This keeps the pending-order
    cap for spam control without blocking an investor with their own abandoned
    attempts.
    """
    cutoff = now_utc() - timedelta(minutes=_pending_order_ttl_minutes())
    stale_orders = list(
        PrimaryInvestmentOrder.objects.select_for_update()
        .filter(
            investor_user_id=investor_user_id,
            status=PrimaryInvestmentOrderStatus.PENDING,
            allocated_amount_minor=0,
        )
        .filter(Q(loan_id=loan_id) | Q(created_at__lt=cutoff))
        .order_by("created_at", "id")
    )
    closed_at = now_utc()
    for order in stale_orders:
        same_loan = str(order.loan_id) == str(loan_id)
        reason_code = "replaced_by_new_order" if same_loan else "pending_order_expired"
        reason = (
            "Replaced by a newer order on the same loan before confirmation."
            if same_loan
            else "Not confirmed within the pending-order time limit."
        )
        previous_status = str(order.status)
        order.status = PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
        order.closed_at = closed_at
        order.metadata = {
            **dict(cast(dict[str, Any], order.metadata)),
            "closed_reason": reason,
            "closed_reason_code": reason_code,
        }
        order.save(update_fields=["status", "closed_at", "metadata", "updated_at"])
        _record_order_event(
            order=order,
            actor=actor,
            event_type=PrimaryInvestmentOrderEventType.CLOSED_NOT_INVESTED,
            previous_status=previous_status,
            new_status=order.status,
            metadata={"reason": reason_code},
        )
    return len(stale_orders)


def _raise_order_not_pending(order: PrimaryInvestmentOrder) -> NoReturn:
    if (
        order.status == PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
        and int(order.allocated_amount_minor) == 0
    ):
        raise MarketplacePrimaryOrderNotPendingError(ORDER_NOT_PENDING_MESSAGE)
    raise MarketplacePrimaryOrderNotPendingError("Only pending orders can be allocated.")


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
    """Use the same offline-company compliance boundary as publication."""
    return bool(getattr(borrower, "can_transact", False))


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


def _require_verified_return_account(actor: Model, currency: str) -> None:
    """U33-DEC-04: a verified bank account in the currency before investing.

    The ledger reservation enforces the same rule; this check gives the clear message
    before an order is started.
    """
    ledger = _ledger_services()
    if not ledger.investor_has_verified_return_account(str(actor.pk), currency):
        raise MarketplacePrimaryValidationError(ledger.verified_return_account_message(currency))


def _ledger_services() -> Any:
    return import_module("backend.apps.ledger.services")


def _holdings_services() -> Any:
    return import_module("backend.apps.holdings.services")


def _lock_borrower_regime(loan: Model) -> None:
    """18.9: lock the borrower's creditor regime row (after the loan row). Audit S6-5: a Swiss
    loan without a valid UID is refused."""
    regimes = import_module("backend.apps.marketplace_primary.creditor_regime")
    try:
        regimes.lock_borrower(loan)
    except regimes.CreditorRegimeViolation as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc


def _loans_services() -> Any:
    return import_module("backend.apps.loans.services")


def _admin_ops_services() -> Any:
    return import_module("backend.apps.admin_ops.services")


def _documents_services() -> Any:
    return import_module("backend.apps.documents.services")


@transaction.atomic
def create_primary_investment_order(
    command: CreatePrimaryInvestmentOrderCommand,
) -> PrimaryInvestmentOrder:
    _require_investor_financial_access(command.actor)
    _require_no_compliance_block(command.actor)
    investor_id = str(command.actor.pk)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    loan = _loan_for_update(command.loan_id)
    _assert_published_loan_open(loan)
    _require_verified_securities(loan)
    loan_ref = cast(Any, loan)
    currency = _enabled_currency(str(loan_ref.currency_id))
    amount_minor = _validate_money(command.amount_minor, currency.code, "Investment amount")
    # Audit S6-10: the minimum for a new creditor is quoted under the borrower's regime lock
    # (after the loan lock), like the allocation that checks it again; a Swiss loan without a
    # valid UID takes no order (audit S6-5).
    _lock_borrower_regime(loan)
    remaining_capacity = _loan_remaining_capacity_minor(loan)
    investor_limit = _loan_investor_limit(loan)
    minimum = _order_minimum_minor(
        loan=loan,
        limit=investor_limit,
        investor_user_id=investor_id,
        remaining_capacity_minor=remaining_capacity,
    )
    if amount_minor < minimum:
        loan_minimum = _loan_minimum_investment_minor(loan)
        if minimum > loan_minimum:
            message = _swiss_new_investor_minimum_message(loan, investor_limit, minimum)
        elif _originator_subscription_profile(loan) is not None or minimum < loan_minimum:
            message = "Investment amount is below this loan's minimum."
        else:
            message = "Investment amount is below the launch minimum."
        raise MarketplacePrimaryValidationError(message)
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
    _require_verified_return_account(command.actor, currency.code)
    _close_abandoned_pending_orders(
        actor=command.actor,
        investor_user_id=investor_id,
        loan_id=str(loan_ref.id),
    )
    _assert_pending_order_cap(investor_id)
    metadata = {
        ORDER_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "remaining_capacity_at_order_minor": remaining_capacity,
        # Audit S6-10: the inputs of the quoted minimum (checked again at allocation).
        "quoted_minimum_minor": minimum,
        "quoted_creditor_mode": investor_limit.mode,
        "quoted_places_left": investor_limit.places_left_for(investor_id),
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
    _require_no_compliance_block(command.actor)
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
        PrimaryInvestmentOrderStatus.CLOSED_INVESTED,
    }:
        if (
            metadata.get(ALLOCATION_IDEMPOTENCY_METADATA_KEY) == idempotency_key
            and metadata.get(ALLOCATION_FINGERPRINT_METADATA_KEY) == allocation_fingerprint
        ):
            _resolve_fully_subscribed_originator_round(
                actor=command.actor,
                loan_id=str(order.loan_id),
            )
            order.refresh_from_db()
            return order
        raise MarketplacePrimaryValidationError("Primary investment order is already allocated.")
    if order.status != PrimaryInvestmentOrderStatus.PENDING:
        if (
            order.status == PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
            and metadata.get(ALLOCATION_IDEMPOTENCY_METADATA_KEY) == idempotency_key
            and metadata.get(ALLOCATION_FINGERPRINT_METADATA_KEY) == allocation_fingerprint
        ):
            # Replay of an allocation that closed the order as not invested.
            return order
        _raise_order_not_pending(order)
    # Early Swiss-borrower limit check, before the email code is used. The
    # authoritative check repeats under the loan lock.
    order_loan = _loan_for_read(str(order.loan_id))
    order_limit = _loan_investor_limit(order_loan)
    if order_limit.applies and str(cast(Any, order_loan).status) == "published":
        _assert_order_within_investor_limit(
            loan=order_loan,
            limit=order_limit,
            order=order,
            remaining_capacity_minor=_loan_remaining_capacity_minor(order_loan),
        )
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
                pin=command.pin,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                operation={
                    "amount_minor": int(order.requested_amount_minor),
                    "currency": str(order.currency_id),
                    "loan_id": str(order.loan_id),
                },
            )
        )
    except SensitiveActionPinError:
        raise
    except SensitiveActionVerificationError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc

    allocated = _allocate_primary_order_from_balance_after_sensitive_code(command)
    _resolve_fully_subscribed_originator_round(
        actor=command.actor,
        loan_id=str(allocated.loan_id),
    )
    allocated.refresh_from_db()
    return allocated


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
        if (
            order.status == PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
            and metadata.get(ALLOCATION_IDEMPOTENCY_METADATA_KEY) == idempotency_key
            and metadata.get(ALLOCATION_FINGERPRINT_METADATA_KEY) == allocation_fingerprint
        ):
            # Replay of an allocation that closed the order as not invested.
            return order
        _raise_order_not_pending(order)
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
    # Swiss creditor limit (18.9): counted under the loan lock taken above and the borrower's
    # regime lock, so two new creditors of the same UID cannot both take the last place.
    _lock_borrower_regime(loan)
    _require_no_compliance_block_locked(command.actor)
    _require_verified_securities(loan)
    _assert_sandbox_notice_confirmed(loan, command)
    investor_limit = _loan_investor_limit(loan)
    _assert_order_within_investor_limit(
        loan=loan,
        limit=investor_limit,
        order=order,
        remaining_capacity_minor=remaining_capacity,
    )
    subscription_profile = _originator_subscription_profile(loan)
    minimum_order_minor = _loan_minimum_investment_minor(loan)
    # A partial allocation must still reach the loan's minimum order. Direct loans
    # follow the Loan Originator rule: when another investor took the capacity and
    # less than the minimum is left, the order closes as not invested and no money
    # moves (no allocation below the minimum). On a Swiss-borrower loan an order may
    # ask for exactly the remaining capacity below the minimum; only a partial fill
    # below the minimum closes.
    partial_fill = remaining_capacity < order.requested_amount_minor
    below_minimum = remaining_capacity < minimum_order_minor and (
        partial_fill or (subscription_profile is not None and not investor_limit.applies)
    )
    if below_minimum:
        previous_status = str(order.status)
        order.status = PrimaryInvestmentOrderStatus.CLOSED_NOT_INVESTED
        order.closed_at = now_utc()
        order.metadata = {
            **metadata,
            ALLOCATION_IDEMPOTENCY_METADATA_KEY: idempotency_key,
            ALLOCATION_FINGERPRINT_METADATA_KEY: allocation_fingerprint,
            "closed_reason": (
                "Remaining Loan Originator subscription capacity was below the loan minimum."
                if subscription_profile is not None
                else "Remaining loan capacity was below the minimum order."
            ),
            "remaining_capacity_at_allocation_minor": remaining_capacity,
            "minimum_order_minor": minimum_order_minor,
        }
        order.save(update_fields=["status", "closed_at", "metadata", "updated_at"])
        _record_order_event(
            order=order,
            actor=command.actor,
            event_type=PrimaryInvestmentOrderEventType.CLOSED_NOT_INVESTED,
            previous_status=previous_status,
            new_status=order.status,
            metadata={"reason": "remaining_capacity_below_loan_minimum"},
        )
        return order
    amount_to_allocate = min(order.requested_amount_minor, remaining_capacity)
    # 18.7 (Q09, F02): an offer priced as principal + accrued interest reserves the whole price,
    # fixed for the planned settlement day (no maximum price, no reconfirmation).
    accrued_interest_minor = 0
    if subscription_profile is not None:
        originator = _originator_services()
        try:
            accrued_interest_minor = int(
                originator.accrued_interest_for_principal(subscription_profile, amount_to_allocate)
            )
        except originator.OriginatorClaimsError as exc:
            raise MarketplacePrimaryValidationError(str(exc)) from exc
    reserved_amount_minor = amount_to_allocate + accrued_interest_minor
    ledger = _ledger_services()
    try:
        reservation_result = ledger.reserve_investor_balance_for_investment(
            ledger.ReserveInvestmentBalanceCommand(
                actor=command.actor,
                investor_user_id=str(order.investor_user_id),
                loan_id=str(order.loan_id),
                amount_minor=reserved_amount_minor,
                currency=order.currency_id,
                loan_funding_deadline=loan_ref.funding_deadline,
                # F01 (18.4): direct loans need the payout margin before day 56 of each lot.
                direct_loan=str(loan_ref.product_type) != "originator_claim",
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
    if accrued_interest_minor:
        order.metadata["price_accrued_interest_minor"] = accrued_interest_minor
        order.metadata["reserved_amount_minor"] = reserved_amount_minor
    if getattr(command, "sandbox_notice_confirmed", False):
        # E-03: proof of the notice version the investor confirmed.
        order.metadata["sandbox_notice_version"] = str(command.sandbox_notice_version)
        order.metadata["sandbox_notice_confirmed_at"] = now_utc().isoformat()
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
    investor_notices.notify_order_allocated(order)
    return order


@transaction.atomic
def release_primary_order_balance(
    command: ReleasePrimaryInvestmentOrderCommand,
    *,
    funding_resolution: bool = False,
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
    if not funding_resolution and (
        str(loan_ref.status) == "funding_close_failed"
        or (
            loan_ref.funding_deadline is not None
            and loan_ref.funding_deadline < business_date(now_utc())
        )
    ):
        raise MarketplacePrimaryValidationError(
            "Reservations are frozen for automatic funding resolution; "
            "an admin cannot change the subscribed amount after the deadline."
        )
    releaseable_statuses = {"published", "funding_close_failed"}
    if str(loan_ref.product_type) == "originator_claim":
        profile_model = _model("originator_claims", "OriginatorLoanProfile")
        profile = (
            profile_model.objects.filter(loan_id=loan_ref.id)
            .only("distribution_model", "opportunity_status")
            .first()
        )
        if (
            profile is not None
            and str(cast(Any, profile).distribution_model) == "par_component_v2"
            and str(cast(Any, profile).opportunity_status) == "awaiting_activation"
        ):
            releaseable_statuses.add("funded")
    if str(loan_ref.status) not in releaseable_statuses:
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
                amount_minor=order_reserved_amount_minor(order),
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
        "released_amount_minor": order_reserved_amount_minor(order),
        "release_journal_entry_id": str(release_result.journal_entry.id),
        "reason": reason,
        # Q26: the investor-facing reason of the release (the admin's reason stays internal).
        "reason_code": "loan_funding_cancelled" if funding_resolution else "released_by_banxum",
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
    if not funding_resolution:
        # Funding cancellations send their own notice with the investor message.
        investor_notices.notify_order_released(order)
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
            idempotency_key=f"email:loan-funding-close-failed:{loan_ref.id}:{as_of_date.isoformat()}",
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
                    "unchanged. The system retries the stored threshold decision automatically. "
                    "Repair the reported cause promptly; no admin funding decision is required."
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
    if command.as_of_date and command.as_of_date > business_date(now_utc()):
        raise MarketplacePrimaryValidationError(
            "Funding resolution cannot run for a future date. Use the QA clock to advance time."
        )
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
    if str(loan_ref.product_type) == "originator_claim":
        raise MarketplacePrimaryValidationError(
            "Loan Originator subscriptions must use the Loan Originator funding lifecycle."
        )
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
    # 18.9 (F08): the creditor mode is checked again before the close; a failure stops it.
    regimes = import_module("backend.apps.marketplace_primary.creditor_regime")
    try:
        regimes.check_before_close(loan, on=business_date(now_utc()))
    except regimes.CreditorRegimeViolation as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc
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
    investor_notices.notify_funding_closed(close)
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
    if str(loan_ref.product_type) == "originator_claim":
        raise MarketplacePrimaryValidationError(
            "Loan Originator subscriptions must use the Loan Originator funding lifecycle."
        )
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
    if (
        (
            str(loan_ref.status) == "funding_close_failed"
            or loan_ref.funding_deadline < business_date(now_utc())
        )
        and int(loan_ref.committed_principal_minor) > 0
        and int(loan_ref.committed_principal_minor) >= _minimum_subscription_required_minor(loan)
    ):
        raise MarketplacePrimaryValidationError(
            "The published minimum is met. Funding must resolve automatically; "
            "an admin cannot replace that result with cancellation."
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
            ),
            funding_resolution=True,
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
    investor_notices.notify_funding_cancelled(cancellation)
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
        loan_model.objects.select_for_update(of=("self",))
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
    if as_of_date > business_date(now_utc()):
        raise MarketplacePrimaryValidationError(
            "Funding resolution cannot run for a future date. Use the QA clock to advance time."
        )
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
        query = loan_model.objects.filter(
            id__in=command.loan_ids,
            product_type="direct",
        ).filter(
            Q(status="funding_close_failed")
            | Q(status="published", funding_deadline__lt=as_of_date)
        )
    else:
        query = loan_model.objects.filter(product_type="direct").filter(
            Q(status="funding_close_failed")
            | Q(status="published", funding_deadline__lt=as_of_date)
        )
    loan_ids = [
        str(value)
        for value in query.order_by("funding_deadline", "id")
        .values_list("id", flat=True)
        .iterator(chunk_size=limit)
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


def _recovery_stages_for(loan_ref: Any) -> dict[str, Any]:
    """U33-DEC-22: the recorded stages and the known next step, for the credit file."""
    loan_id = str(loan_ref.id)
    return cast(
        dict[str, Any],
        import_module("backend.apps.servicing.recovery_stages").investor_recovery_stages([loan_id])[
            loan_id
        ],
    )


def _loan_securities_module() -> Any:
    return import_module("backend.apps.loans.securities")


def public_marketplace_listing_payload(
    loan: Model,
    *,
    viewer_user_id: str | None = None,
) -> dict[str, Any]:
    """Investor marketplace data of a Direct loan (behind KYC, MKT-DEC-002).

    With a viewer, ``minimum_investment_minor`` is what that investor must invest now;
    without one, what a new investor must invest (Swiss-borrower limit, MKT-DEC-028).
    """
    loan_ref = cast(Any, loan)
    borrower = getattr(loan_ref, "borrower", None)
    progress = loan_funding_progress(str(loan_ref.id))
    limit_fields = investor_limits.investor_limit_payload(
        _loan_investor_limit(loan),
        minimum_minor=_minimum_investment_minor(str(loan_ref.currency_id)),
        remaining_minor=int(progress["remaining_capacity_minor"]),
        viewer_user_id=viewer_user_id,
    )
    return {
        **creditor_mode_fields(loan),
        **progress,
        "product_type": str(loan_ref.product_type),
        "investment_flow": "primary_order",
        "title": str(loan_ref.title),
        "purpose": str(loan_ref.purpose),
        "collateral_type": str(loan_ref.collateral_type),
        # U33-DEC-21: every security type in force, for the filters and Smart Invest.
        "security_types": _loan_securities_module().loan_security_types(loan_ref),
        "interest_rate_bps": int(loan_ref.interest_rate_bps),
        "yield_bps": int(loan_ref.interest_rate_bps),
        "underlying_interest_rate_bps": int(loan_ref.interest_rate_bps),
        "term_months": int(loan_ref.term_months),
        "remaining_term_days": None,
        "funding_deadline": loan_ref.funding_deadline,
        "maturity_date": None,
        "status": str(loan_ref.status),
        "loan_status": str(loan_ref.status),
        "opportunity_status": "open",
        "fillable_amount_minor": progress["remaining_capacity_minor"],
        **limit_fields,
        "ltv_bps": loan_ref.ltv_bps,
        "is_refinancing": bool(loan_ref.is_refinancing),
        "originator_id": None,
        "originator_name": None,
        # The borrower's legal name and country are part of the investor disclosure of every
        # Direct loan (entities.borrower_investor_disclosure); the U33 cards show them.
        "borrower_display_name": str(getattr(borrower, "legal_name", "") or "") or None,
        "borrower_country": str(getattr(borrower, "country", "") or ""),
        "borrower_city": str(getattr(borrower, "city", "") or ""),
        "repayment_type": str(loan_ref.repayment_type),
        "collateral_description": str(loan_ref.collateral_description),
        "published_at": loan_ref.published_at,
        "skin_in_the_game_bps": int(getattr(loan_ref, "skin_in_the_game_bps", 0)),
        "minimum_subscription_bps": int(getattr(loan_ref, "minimum_subscription_bps", 5_000)),
    }


def _direct_loan_schedule_payload(loan: Model) -> list[dict[str, Any]]:
    """Reuse servicing history plus remaining installments, including advance payments."""
    servicing = import_module("backend.apps.servicing.services")
    rows = servicing.get_loan_repayment_schedule_snapshots(
        loans=[loan], as_of_date=business_date(now_utc())
    )[str(loan.pk)]
    outstanding = sum(int(row.principal_minor) for row in rows)
    payload: list[dict[str, Any]] = []
    for row in rows:
        outstanding -= int(row.principal_minor)
        payload.append(
            {
                **asdict(row),
                "outstanding_after_minor": max(0, outstanding),
            }
        )
    return payload


def _story_payload(value: Any) -> dict[str, Any]:
    """Investor-facing story document; always a well-formed (possibly empty) document."""
    if isinstance(value, dict) and isinstance(value.get("blocks"), list):
        return {"version": 1, "blocks": list(value["blocks"])}
    return {"version": 1, "blocks": []}


def full_marketplace_listing_payload(
    loan: Model,
    *,
    viewer_user_id: str | None = None,
) -> dict[str, Any]:
    loan_ref = cast(Any, loan)
    if str(loan_ref.product_type) == "originator_claim":
        raise MarketplacePrimaryValidationError(
            "Originator claim details must use the originator investor projection."
        )
    borrower = cast(Model, loan_ref.borrower)
    entities_services = _entities_services()
    payload = public_marketplace_listing_payload(loan, viewer_user_id=viewer_user_id)
    payload.update(
        {
            "borrower_id": str(loan_ref.borrower_id),
            "borrower_disclosure": entities_services.borrower_investor_disclosure(borrower),
            "story": _story_payload(getattr(borrower, "investor_story", None)),
            "investor_summary": str(loan_ref.investor_summary),
            "purpose_description": str(loan_ref.purpose_description),
            "collateral_value_minor": int(loan_ref.collateral_value_minor),
            "collateral_description": str(loan_ref.collateral_description),
            "securities": _loan_securities_module().investor_securities([str(loan_ref.id)])[
                str(loan_ref.id)
            ],
            # U33-DEC-20: structured credit file (financial years, existing debt, checks).
            **import_module("backend.apps.entities.credit_file").investor_credit_file(borrower),
            **import_module("backend.apps.loans.credit_checks").investor_checks(loan_ref),
            # 18.3: the credit file's "Updated" date.
            "credit_file_updated_at": import_module(
                "backend.apps.loans.credit_checks"
            ).credit_file_updated_at(loan_ref, borrower),
            "recovery_stages": _recovery_stages_for(loan_ref),
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
            "loan_schedule": _direct_loan_schedule_payload(loan),
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


def list_open_marketplace_loans(
    *,
    limit: int = 100,
    viewer_user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Every open opportunity with its full investor-facing preview data.

    Not for anonymous visitors: risk, collateral, funding progress, deadlines and
    participation terms are shown only after registration and KYC (MKT-DEC-002).
    Anonymous visitors use the public site projects (``public_site.list_public_projects``).
    With a viewer, the minimum is the viewer's own (Swiss-borrower limit, MKT-DEC-028).
    """
    loan_model = _model("loans", "Loan")
    loans = (
        loan_model.objects.filter(status="published", product_type="direct")
        .select_related("borrower")
        .order_by("funding_deadline", "id")[:limit]
    )
    payloads = [
        public_marketplace_listing_payload(cast(Model, loan), viewer_user_id=viewer_user_id)
        for loan in loans
    ]
    payloads.extend(
        _originator_services().list_open_originator_marketplace_payloads(
            limit=limit,
            viewer_user_id=viewer_user_id,
        )
    )
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


# Q04 (2026-11-13): the investor accounts through which Garanta Finanzgruppe AG invests its own
# money (emails of ordinary investor accounts), set by an admin.
BANXUM_INVESTOR_EMAILS_SETTING = "investment.banxum_investor_emails"
_BANXUM_RESERVED_ORDER_STATUSES = ("balance_allocated", "partially_allocated", "closed_invested")


def banxum_invests_loan_ids(loan_ids: list[str]) -> set[str]:
    """Q04: loans with a confirmed reservation or a real participation of a Garanta account.

    The label "Banxum invests" shows no amount. It appears with a confirmed reservation (an
    allocated order), stays after closing while the participation is held, and goes away when
    the participation is cancelled or released.
    """
    emails = get_platform_setting_value(BANXUM_INVESTOR_EMAILS_SETTING, [])
    if not loan_ids or not isinstance(emails, list) or not emails:
        return set()
    user_ids = list(
        apps.get_model("accounts_auth", "User")
        .objects.filter(email__in=[str(email).strip().lower() for email in emails if email])
        .values_list("id", flat=True)
    )
    if not user_ids:
        return set()
    reserved = PrimaryInvestmentOrder.objects.filter(
        loan_id__in=loan_ids,
        investor_user_id__in=user_ids,
        status__in=_BANXUM_RESERVED_ORDER_STATUSES,
    ).values_list("loan_id", flat=True)
    held = (
        apps.get_model("holdings", "InvestorLoanHolding")
        .objects.filter(loan_id__in=loan_ids, investor_user_id__in=user_ids, status="active")
        .values_list("loan_id", flat=True)
    )
    return {str(loan_id) for loan_id in reserved} | {str(loan_id) for loan_id in held}


def _with_banxum_invests(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = banxum_invests_loan_ids([str(payload["loan_id"]) for payload in payloads])
    for payload in payloads:
        payload["banxum_invests"] = str(payload["loan_id"]) in ids
    return payloads


def list_investor_marketplace_loans(*, actor: Model, limit: int = 100) -> list[dict[str, Any]]:
    """The investor marketplace list: full preview data, behind KYC (MKT-DEC-002)."""
    _require_investor_financial_access(actor)
    return _with_banxum_invests(
        list_open_marketplace_loans(limit=limit, viewer_user_id=str(actor.pk))
    )


def marketplace_payload_has_capacity(payload: dict[str, Any]) -> bool:
    """True while an investor can still put money into this loan or claim."""
    available = payload.get("fillable_amount_minor")
    if available is None:
        available = payload.get("remaining_capacity_minor", 0)
    return int(available or 0) > 0


def get_full_marketplace_loan(*, actor: Model, loan_id: str) -> dict[str, Any]:
    return _with_banxum_invests([_full_marketplace_loan(actor=actor, loan_id=loan_id)])[0]


def _full_marketplace_loan(*, actor: Model, loan_id: str) -> dict[str, Any]:
    _require_investor_financial_access(actor)
    loan = _loan_for_read(loan_id)
    if _is_coming_soon(loan):
        return _coming_soon_payload(loan, viewer_user_id=str(actor.pk), full=True)
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
    _assert_direct_loan_readable(loan)
    return full_marketplace_listing_payload(loan, viewer_user_id=str(actor.pk))


def _assert_direct_loan_readable(loan: Model) -> None:
    """An investor can read a Direct loan while it is open or after it was published and funded."""
    if str(cast(Any, loan).status) not in {
        "funded",
        "active",
        "late",
        "defaulted",
        "repaid",
        "written_off",
    }:
        _assert_published_loan_open(loan)
    elif cast(Any, loan).published_at is None:
        raise MarketplacePrimaryValidationError("This loan has not been published.")


def download_marketplace_borrower_document(
    *,
    actor: Model,
    loan_id: str,
    document_id: str,
    audit_actor: Model | None = None,
) -> dict[str, Any]:
    """File of a borrower document listed on a loan page, for an investor who can read the loan."""
    _require_investor_financial_access(actor)
    loan = _loan_for_read(loan_id)
    loan_ref = cast(Any, loan)
    if str(loan_ref.product_type) == "originator_claim" or loan_ref.borrower_id is None:
        raise MarketplacePrimaryValidationError("Document not found.")
    _assert_direct_loan_readable(loan)
    entities_services = _entities_services()
    try:
        document_file = entities_services.read_investor_visible_borrower_document(
            borrower_id=str(loan_ref.borrower_id),
            document_id=str(document_id),
        )
    except entities_services.BorrowerValidationError as exc:
        raise MarketplacePrimaryValidationError(str(exc)) from exc
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(audit_actor or actor),
            action="marketplace.borrower_document_downloaded",
            target_type="BorrowerDocument",
            target_id=document_file.document_id,
            metadata={
                "loan_id": str(loan_ref.pk),
                "investor_user_id": str(actor.pk),
                "content_sha256": document_file.checksum_sha256,
            },
        )
    )
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", document_file.filename).strip("-") or "document"
    return {
        "document_id": document_file.document_id,
        "display_name": document_file.display_name,
        "filename": filename[:120],
        "content_type": document_file.content_type,
        "content_encoding": "base64",
        "content": base64.b64encode(document_file.content).decode("ascii"),
        "content_sha256": document_file.checksum_sha256,
    }


def allocated_primary_order_total_minor(*, loan_id: str) -> int:
    aggregate = PrimaryInvestmentOrder.objects.filter(
        loan_id=loan_id,
        status__in=[
            PrimaryInvestmentOrderStatus.BALANCE_ALLOCATED,
            PrimaryInvestmentOrderStatus.PARTIALLY_ALLOCATED,
        ],
    ).aggregate(total=Sum("allocated_amount_minor"))
    return int(aggregate["total"] or 0)


# U33-DEC-17: Coming soon and the opening alert.


def _is_coming_soon(loan: Model) -> bool:
    loan_ref = cast(Any, loan)
    return (
        str(loan_ref.status) == "draft"
        and str(loan_ref.product_type) in {"direct", "originator_claim"}
        and loan_ref.coming_soon_at is not None
    )


def _coming_soon_payload(loan: Model, *, viewer_user_id: str, full: bool = False) -> dict[str, Any]:
    if str(cast(Any, loan).product_type) == "originator_claim":
        # Q17: a Coming soon Loan Originator offer uses the originator projection (no capacity).
        originator = _originator_services()
        try:
            payload = cast(
                dict[str, Any],
                originator.originator_coming_soon_payload(
                    loan_id=str(cast(Any, loan).id), include_detail=full
                ),
            )
        except originator.OriginatorClaimsError as exc:
            raise MarketplacePrimaryValidationError(str(exc)) from exc
    else:
        payload = (
            full_marketplace_listing_payload(loan, viewer_user_id=viewer_user_id)
            if full
            else public_marketplace_listing_payload(loan, viewer_user_id=viewer_user_id)
        )
    loan_ref = cast(Any, loan)
    return {
        **payload,
        "opportunity_status": "coming_soon",
        "planned_opening_date": loan_ref.planned_opening_date,
        "opening_alert_requested": LoanOpeningAlert.objects.filter(
            loan_id=loan_ref.id, investor_user_id=viewer_user_id
        ).exists(),
    }


def list_coming_soon_marketplace_loans(*, actor: Model) -> list[dict[str, Any]]:
    """Drafts shown as Coming soon, by planned opening date. Not open: no orders."""
    _require_investor_financial_access(actor)
    return coming_soon_marketplace_payloads(viewer_user_id=str(actor.pk))


def coming_soon_marketplace_payloads(*, viewer_user_id: str) -> list[dict[str, Any]]:
    """The Coming soon list for one investor (also Smart Invest's Coming soon matches)."""
    loan_model = _model("loans", "Loan")
    loans = (
        loan_model.objects.filter(
            status="draft",
            product_type__in=["direct", "originator_claim"],
            coming_soon_at__isnull=False,
        )
        .select_related("borrower")
        .order_by("planned_opening_date", "id")
    )
    return [
        _coming_soon_payload(cast(Model, loan), viewer_user_id=viewer_user_id) for loan in loans
    ]


def opening_alert_counts(loan_ids: list[str]) -> dict[str, int]:
    """Admin: how many investors wait for the opening email of each loan (not yet sent)."""
    rows = (
        LoanOpeningAlert.objects.filter(loan_id__in=loan_ids, notified_at__isnull=True)
        .values("loan_id")
        .annotate(count=Count("id"))
    )
    return {str(row["loan_id"]): int(row["count"]) for row in rows}


def set_loan_opening_alert(*, actor: Model, loan_id: str, wanted: bool) -> dict[str, Any]:
    """Ask for (or cancel) the email at the real opening of a Coming soon loan."""
    _require_investor_financial_access(actor)
    loan = _loan_for_read(loan_id)
    if not _is_coming_soon(loan):
        raise MarketplacePrimaryValidationError("This opportunity is not coming soon.")
    if wanted:
        LoanOpeningAlert.objects.get_or_create(
            loan_id=cast(Any, loan).id, investor_user_id=actor.pk
        )
    else:
        LoanOpeningAlert.objects.filter(
            loan_id=cast(Any, loan).id, investor_user_id=actor.pk, notified_at__isnull=True
        ).delete()
    return _coming_soon_payload(loan, viewer_user_id=str(actor.pk), full=True)


def stop_loan_opening_alert(*, investor_user_id: str, loan_id: str) -> bool:
    """Q14: "Stop these alerts" in an opening email cancels the request for that project."""
    deleted, _ = LoanOpeningAlert.objects.filter(
        loan_id=loan_id, investor_user_id=investor_user_id, notified_at__isnull=True
    ).delete()
    if deleted:
        record_audit_event(
            AuditCommand(
                actor=ActorRef("investor", str(investor_user_id)),
                action="marketplace.opening_alert_stopped",
                target_type="Loan",
                target_id=str(loan_id),
                metadata={"decision": "Q14", "source": "email_stop_link"},
            )
        )
    return bool(deleted)


def send_loan_opening_alerts(*, loan_id: str) -> list[str]:
    """At publication: one email per investor who asked, listed in their notifications.

    Returns the investors told, so Smart Invest does not alert them again for this loan.
    """
    loan_model = _model("loans", "Loan")
    loan = loan_model.objects.filter(id=loan_id).first()
    if loan is None or str(loan.status) != "published":
        return []
    user_model = _model("accounts_auth", "User")
    notified: list[str] = []
    now = now_utc()
    action_url = f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/marketplace/{loan.id}"
    pending = LoanOpeningAlert.objects.select_for_update().filter(
        loan_id=loan.id, notified_at__isnull=True
    )
    for alert in pending:
        user = user_model.objects.filter(pk=alert.investor_user_id, is_active=True).first()
        if user is None:
            continue
        message = enqueue_outbox_message(
            OutboxCommand(
                idempotency_key=f"loan-opening-alert:{alert.id}",
                topic="email.loan_opening_alert",
                payload={
                    "user_id": str(user.pk),
                    "email": str(user.email),
                    "subject": f"Now open: {loan.title}",
                    "notice_label": "Opportunity open",
                    "headline": "The opportunity you followed is open",
                    "status_label": "Open",
                    "status_tone": "info",
                    "body_text": (
                        f"{loan.title} is now open for investment. You asked us to tell you "
                        "when it opens. Nothing was reserved for you: review the opportunity "
                        "and confirm your investment if you want to invest."
                    ),
                    "buttons": [{"label": "Review opportunity", "url": action_url}],
                    "loan_id": str(loan.id),
                    # Q14: the email carries a one-click "Stop these alerts" link.
                    "stop_alerts": {"kind": "opening_alert", "loan_id": str(loan.id)},
                    "template_key": "marketplace.opening_alert.v1",
                    "fine_print": "Capital is at risk. Opening does not guarantee a place.",
                },
            )
        )
        LoanOpeningAlert.objects.filter(pk=alert.pk).update(notified_at=now, outbox_message=message)
        notified.append(str(user.pk))
    return notified
