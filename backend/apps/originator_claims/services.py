from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model, Q
from django.utils import timezone

from backend.apps.originator_claims.domain.imports import (
    OriginatorImportValidationError,
    ParsedOriginatorImport,
    parse_originator_import_csv,
)
from backend.apps.originator_claims.domain.pricing import (
    PricingValidationError,
    price_assigned_principal,
    quote_cash_consideration,
)
from backend.apps.originator_claims.models import (
    InvestorOriginatorRepaymentDistributionLine,
    LoanOriginator,
    LoanOriginatorStatus,
    OriginatorBorrowerRepayment,
    OriginatorClaimEntitlement,
    OriginatorClaimEvent,
    OriginatorClaimEventType,
    OriginatorClaimPurchase,
    OriginatorClaimQuote,
    OriginatorDistributionModel,
    OriginatorFundingRoundClose,
    OriginatorLoanImport,
    OriginatorLoanPaymentRow,
    OriginatorLoanProfile,
    OriginatorLoanScheduleRow,
    OriginatorOpportunityStatus,
    OriginatorSettlement,
    OriginatorSettlementPurchase,
    OriginatorSettlementRepayment,
    OriginatorSubscriptionActivation,
    OriginatorSubscriptionCancellation,
)
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
    user_can_access_financial_features,
)
from backend.apps.platform_core.domain.iban import IbanValidationError, normalize_and_validate_iban
from backend.apps.platform_core.domain.money import (
    Money,
    allocate_by_weights,
    format_amount_minor,
)
from backend.apps.platform_core.domain.payment_waterfall import (
    PAYMENT_WATERFALL_ORDER,
    PAYMENT_WATERFALL_VERSION,
    PaymentWaterfallAllocation,
    PaymentWaterfallError,
    PaymentWaterfallObligations,
    allocate_payment_waterfall,
)
from backend.apps.platform_core.domain.time import business_date, business_timezone, now_utc
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


class OriginatorClaimsError(ValueError):
    pass


class OriginatorClaimsAuthorizationError(OriginatorClaimsError):
    pass


class OriginatorClaimsValidationError(OriginatorClaimsError):
    pass


@dataclass(frozen=True, slots=True)
class CreateLoanOriginatorCommand:
    actor: Model
    legal_name: str
    public_name: str
    registration_number: str
    jurisdiction: str
    registered_address: str
    settlement_account_name: str
    settlement_iban: str
    kyb_evidence_reference: str
    contact_info: str = ""
    settlement_bic: str = ""
    kyb_aml_observations: str = ""
    risk_observations: str = ""
    status: str = LoanOriginatorStatus.INACTIVE
    default_premium_fee_bps: int = 5000


@dataclass(frozen=True, slots=True)
class UpdateLoanOriginatorCommand:
    actor: Model
    originator_id: str
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CreateOriginatorLoanCommand:
    actor: Model
    originator_id: str
    title: str
    investor_summary: str
    purpose: str
    purpose_description: str
    currency: str
    original_principal_minor: int
    interest_rate_bps: int
    minimum_investment_minor: int
    repayment_type: str
    interest_only_months: int
    collateral_type: str
    collateral_value_minor: int
    collateral_description: str
    risk_rating: str
    csv_content: str
    source_filename: str
    as_of_date: date
    borrower_snapshot: dict[str, Any]
    premium_fee_bps: int | None = None
    skin_in_the_game_bps: int = 0
    target_yield_bps: int | None = None
    funding_deadline: date | None = None
    entitlement_start_date: date | None = None
    activation_outstanding_principal_minor: int | None = None
    investor_interest_participation_bps: int | None = None
    investor_penalty_participation_bps: int | None = None
    distribution_model: str = OriginatorDistributionModel.PAR_COMPONENT_V2


@dataclass(frozen=True, slots=True)
class PublishOriginatorLoanCommand:
    actor: Model
    loan_id: str
    as_of_date: date


@dataclass(frozen=True, slots=True)
class HoldOriginatorLoanCommand:
    actor: Model
    loan_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class CloseOriginatorSubscriptionRoundCommand:
    actor: Model
    loan_id: str
    as_of_date: date
    close_reason: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ActivateOriginatorSubscriptionCommand:
    actor: Model
    loan_id: str
    csv_content: str
    source_filename: str
    as_of_date: date
    boundary_payment_reference: str
    boundary_payment_date: date
    notes: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CancelOriginatorSubscriptionCommand:
    actor: Model
    loan_id: str
    reason: str
    investor_message: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CreateOriginatorClaimQuoteCommand:
    actor: Model
    loan_id: str
    requested_cash_minor: int


@dataclass(frozen=True, slots=True)
class PurchaseOriginatorClaimCommand:
    actor: Model
    quote_id: str
    document_acceptance_id: str
    sensitive_action_code_id: str
    sensitive_action_code: str
    idempotency_key: str
    ip_address: str | None = None
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class PurchaseOriginatorClaimInVerifiedBatchCommand:
    """Internal service-boundary command for a batch that already consumed MFA."""

    actor: Model
    quote_id: str
    document_acceptance_id: str
    idempotency_key: str
    ip_address: str | None = None
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class FinalizeOriginatorSettlementCommand:
    actor: Model
    originator_id: str
    currency: str
    purchase_ids: list[str]
    repayment_ids: list[str]
    booking_date: date
    value_date: date
    collection_account_identifier: str
    bank_reference: str
    payment_reference: str
    evidence_reference: str
    notes: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RecordOriginatorBorrowerRepaymentCommand:
    actor: Model
    loan_id: str
    csv_content: str
    source_filename: str
    as_of_date: date
    payment_reference: str
    booking_date: date
    value_date: date
    collection_account_identifier: str
    payer_name: str
    payer_account_identifier: str = ""
    bank_reference: str = ""
    bank_payment_reference: str = ""
    evidence_reference: str = ""
    notes: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class OriginatorRepaymentPlanLine:
    holding: Any
    investor_user_id: str
    principal_minor: int
    interest_minor: int
    penalty_minor: int
    amount_minor: int
    principal_before_minor: int
    principal_after_minor: int


@dataclass(frozen=True, slots=True)
class OriginatorLoanCreationResult:
    loan: Any
    profile: OriginatorLoanProfile
    loan_import: OriginatorLoanImport


ORIGINATOR_MUTABLE_FIELDS = frozenset(
    {
        "legal_name",
        "public_name",
        "registration_number",
        "jurisdiction",
        "registered_address",
        "contact_info",
        "settlement_account_name",
        "settlement_iban",
        "settlement_bic",
        "kyb_evidence_reference",
        "kyb_aml_observations",
        "risk_observations",
        "status",
        "default_premium_fee_bps",
    }
)


def _require_admin(actor: Model) -> None:
    if not is_admin_actor(actor):
        raise OriginatorClaimsAuthorizationError(
            "Only an active admin can manage Loan Originators."
        )


def _investor_email_for_user_id(investor_user_id: str) -> str:
    user_model = apps.get_model("accounts_auth", "User")
    user = user_model.objects.filter(id=investor_user_id).only("email").first()
    return str(getattr(user, "email", "")).strip().lower() if user is not None else ""


def _enqueue_investor_email(
    *,
    investor_user_id: str,
    topic: str,
    subject: str,
    body_text: str,
    template_key: str,
    idempotency_key: str,
    metadata: dict[str, Any],
) -> None:
    email = _investor_email_for_user_id(investor_user_id)
    if not email:
        return
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=idempotency_key,
            topic=topic,
            payload={
                "user_id": investor_user_id,
                "email": email,
                "subject": subject,
                "body_text": body_text,
                "template_key": template_key,
                "metadata": metadata,
            },
        )
    )


def _enqueue_operations_email(
    *,
    topic: str,
    subject: str,
    body_text: str,
    template_key: str,
    idempotency_key: str,
    metadata: dict[str, Any],
) -> None:
    email = str(getattr(settings, "OPERATIONS_ALERT_EMAIL", "") or "hq@banxum.com").strip()
    enqueue_outbox_message(
        OutboxCommand(
            idempotency_key=idempotency_key,
            topic=topic,
            payload={
                "email": email,
                "subject": subject,
                "body_text": body_text,
                "template_key": template_key,
                "metadata": metadata,
            },
        )
    )


def _operations_admin_actor(triggering_actor: Model) -> Model:
    if is_admin_actor(triggering_actor):
        return triggering_actor
    user_app, user_model_name = str(settings.AUTH_USER_MODEL).split(".", 1)
    user_model = apps.get_model(user_app, user_model_name)
    queryset = user_model.objects.filter(is_active=True, is_staff=True).order_by(
        "-is_superuser",
        "email",
    )
    configured_email = str(getattr(settings, "SCHEDULED_JOBS_ACTOR_EMAIL", "")).strip()
    if configured_email:
        configured_actor = queryset.filter(email__iexact=configured_email).first()
        if configured_actor is not None and is_admin_actor(configured_actor):
            return cast(Model, configured_actor)
    if str(getattr(settings, "ENVIRONMENT", "local")) in {"local", "test"}:
        fallback = next((candidate for candidate in queryset if is_admin_actor(candidate)), None)
        if fallback is not None:
            return cast(Model, fallback)
    raise OriginatorClaimsValidationError(
        "An active SCHEDULED_JOBS_ACTOR_EMAIL admin is required to record this close failure."
    )


def _required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise OriginatorClaimsValidationError(f"{label} is required.")
    return cleaned


def _fee_bps(value: Any, label: str) -> int:
    if type(value) is not int or value < 0 or value > 10_000:
        raise OriginatorClaimsValidationError(f"{label} must be between 0 and 10000 bps.")
    return value


def _locked_originator(originator_id: str) -> LoanOriginator:
    originator = LoanOriginator.objects.select_for_update().filter(id=originator_id).first()
    if originator is None:
        raise OriginatorClaimsValidationError("Loan Originator does not exist.")
    return originator


def _enabled_currency(currency_code: str) -> Any:
    currency_model = apps.get_model("platform_core", "Currency")
    currency = currency_model.objects.filter(
        code=currency_code.strip().upper(),
        is_enabled=True,
    ).first()
    if currency is None:
        raise OriginatorClaimsValidationError("Currency is not enabled.")
    return currency


def _locked_profile_for_loan(
    loan_id: str,
    *related_fields: str,
) -> OriginatorLoanProfile:
    queryset = OriginatorLoanProfile.objects.select_for_update(of=("self",))
    if related_fields:
        queryset = queryset.select_related(*related_fields)
    profile = queryset.filter(loan_id=loan_id).first()
    if profile is None:
        raise OriginatorClaimsValidationError("Originator claim loan does not exist.")
    return profile


def _operation_uuid(scope: str, idempotency_key: str) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://banxum.com/idempotency/{scope}/{idempotency_key}",
    )


def _request_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _skin_bps(value: Any) -> int:
    if type(value) is not int:
        raise OriginatorClaimsValidationError(
            "Skin in the game must be a whole number of basis points."
        )
    parsed = value
    if parsed < 0 or parsed >= 10_000:
        raise OriginatorClaimsValidationError("Skin in the game must be between 0% and 99.99%.")
    return parsed


def _participation_bps(value: Any, label: str) -> int:
    if type(value) is not int or value < 0 or value > 10_000:
        raise OriginatorClaimsValidationError(
            f"{label} must be a whole number between 0 and 10,000 basis points."
        )
    return value


def _is_par_subscription(profile: OriginatorLoanProfile) -> bool:
    return profile.distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2


def _display_yield_bps(*, coupon_bps: int, interest_participation_bps: int) -> int:
    return int(
        (Decimal(coupon_bps) * Decimal(interest_participation_bps) / Decimal(10_000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def _subscription_principal_minor(profile: OriginatorLoanProfile) -> int:
    if _is_par_subscription(profile):
        value = profile.activation_outstanding_principal_minor
        if value is None or value <= 0:
            raise OriginatorClaimsValidationError(
                "Originator subscription starting principal is unavailable."
            )
        return int(value)
    return int(profile.current_outstanding_principal_minor)


def _future_entitlement_rows(profile: OriginatorLoanProfile) -> list[OriginatorLoanScheduleRow]:
    loan_import = profile.current_import
    if loan_import is None:
        return []
    cutoff = (
        profile.entitlement_start_date if _is_par_subscription(profile) else loan_import.as_of_date
    )
    if cutoff is None:
        cutoff = loan_import.as_of_date
    return list(
        loan_import.schedule_rows.filter(due_date__gt=cutoff).order_by(
            "due_date", "installment_number", "id"
        )
    )


def originator_retained_principal_minor(profile: OriginatorLoanProfile) -> int:
    """Outstanding principal the originator must keep (skin in the game floor)."""
    skin_bps = _skin_bps(cast(Any, profile.loan).skin_in_the_game_bps)
    if skin_bps <= 0:
        return 0
    outstanding = int(profile.current_outstanding_principal_minor)
    return -(-outstanding * skin_bps // 10_000)


def originator_sellable_principal_minor(profile: OriginatorLoanProfile) -> int:
    """Unsold principal that may still be assigned to investors."""
    retained_principal = originator_retained_principal_minor(profile)
    unsold_principal = int(profile.unsold_principal_minor)
    if unsold_principal < retained_principal:
        raise OriginatorClaimsValidationError(
            "Originator-owned principal is below the declared skin-in-the-game floor."
        )
    return unsold_principal - retained_principal


def originator_subscription_available_minor(profile: OriginatorLoanProfile) -> int:
    available = originator_sellable_principal_minor(profile)
    if _is_par_subscription(profile):
        available -= int(cast(Any, profile.loan).committed_principal_minor)
    if available < 0:
        raise OriginatorClaimsValidationError(
            "Originator subscription commitments exceed the sellable principal."
        )
    return available


def _allocate_principal_with_retention(
    *,
    holding_principals: list[int],
    originator_principal_minor: int,
    skin_in_the_game_bps: int,
    principal_minor: int,
    currency: str,
) -> tuple[list[Money], int]:
    """Allocate principal while preserving the originator's post-payment floor."""
    parsed_skin_bps = _skin_bps(skin_in_the_game_bps)
    if any(value < 0 for value in holding_principals) or originator_principal_minor < 0:
        raise OriginatorClaimsValidationError("Principal ownership cannot be negative.")
    principal_weights = [*holding_principals, originator_principal_minor]
    principal_before_minor = sum(principal_weights)
    if principal_before_minor <= 0:
        raise OriginatorClaimsValidationError(
            "Originator loan has no principal ownership to distribute."
        )
    retained_before_minor = -(-(principal_before_minor * parsed_skin_bps) // 10_000)
    if originator_principal_minor < retained_before_minor:
        raise OriginatorClaimsValidationError(
            "Originator-owned principal is below the declared skin-in-the-game floor."
        )
    principal_after_minor = principal_before_minor - principal_minor
    if principal_minor < 0 or principal_after_minor < 0:
        raise OriginatorClaimsValidationError(
            "Repayment principal exceeds the current outstanding principal."
        )
    retained_after_minor = -(-(principal_after_minor * parsed_skin_bps) // 10_000)
    proportional_parts = allocate_by_weights(Money(principal_minor, currency), principal_weights)
    max_originator_principal_minor = originator_principal_minor - retained_after_minor
    originator_principal_part_minor = min(
        proportional_parts[-1].amount_minor,
        max_originator_principal_minor,
    )
    investor_principal_minor = principal_minor - originator_principal_part_minor
    if holding_principals:
        investor_principal_parts = allocate_by_weights(
            Money(investor_principal_minor, currency), holding_principals
        )
    elif investor_principal_minor == 0:
        investor_principal_parts = []
    else:
        raise OriginatorClaimsValidationError(
            "Repayment principal cannot be allocated without investor holdings."
        )
    if any(
        part.amount_minor > owned_minor
        for part, owned_minor in zip(investor_principal_parts, holding_principals, strict=True)
    ):
        raise OriginatorClaimsValidationError(
            "Repayment principal allocation exceeds an investor holding."
        )
    principal_parts = [
        *investor_principal_parts,
        Money(originator_principal_part_minor, currency),
    ]
    if sum(part.amount_minor for part in principal_parts) != principal_minor:
        raise OriginatorClaimsValidationError("Repayment principal allocation does not reconcile.")
    return principal_parts, retained_after_minor


def _positive_minor(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise OriginatorClaimsValidationError(
            f"{label} must be a positive integer minor-unit amount."
        )
    return value


def _record_event(
    *,
    actor: Model,
    event_type: OriginatorClaimEventType,
    originator: LoanOriginator | None = None,
    loan_id: Any = None,
    purchase_id: Any = None,
    note: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    OriginatorClaimEvent.objects.create(
        event_type=event_type,
        originator=originator,
        loan_id=loan_id,
        purchase_id=purchase_id,
        actor_user_id=actor.pk,
        actor_account_type=str(getattr(actor, "account_type", "")),
        note=note.strip(),
        metadata=metadata or {},
    )
    aggregate_id = str(purchase_id or loan_id or (originator.id if originator else "platform"))
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action=f"originator_claims.{event_type.value}",
            target_type="Loan" if loan_id else "LoanOriginator",
            target_id=aggregate_id,
            metadata=metadata or {},
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type=f"originator_claims.{event_type.value}",
            aggregate_type="originator_claim",
            aggregate_id=aggregate_id,
            payload=metadata or {},
        )
    )


@transaction.atomic
def create_loan_originator(command: CreateLoanOriginatorCommand) -> LoanOriginator:
    _require_admin(command.actor)
    try:
        settlement_iban = normalize_and_validate_iban(command.settlement_iban)
    except IbanValidationError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc
    status_values = {choice for choice, _label in LoanOriginatorStatus.choices}
    if command.status not in status_values:
        raise OriginatorClaimsValidationError("Invalid Loan Originator status.")
    originator = LoanOriginator.objects.create(
        legal_name=_required(command.legal_name, "Legal name"),
        public_name=_required(command.public_name, "Public name"),
        registration_number=_required(command.registration_number, "Registration number"),
        jurisdiction=_required(command.jurisdiction, "Jurisdiction"),
        registered_address=_required(command.registered_address, "Registered address"),
        contact_info=command.contact_info.strip(),
        settlement_account_name=_required(
            command.settlement_account_name, "Settlement account name"
        ),
        settlement_iban=settlement_iban,
        settlement_bic=command.settlement_bic.strip().upper(),
        kyb_evidence_reference=_required(command.kyb_evidence_reference, "KYB evidence reference"),
        kyb_aml_observations=command.kyb_aml_observations.strip(),
        risk_observations=command.risk_observations.strip(),
        status=command.status,
        default_premium_fee_bps=_fee_bps(command.default_premium_fee_bps, "Default premium fee"),
        created_by_admin_id=command.actor.pk,
    )
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.ORIGINATOR_CREATED,
        originator=originator,
        metadata={"status": originator.status, "public_name": originator.public_name},
    )
    return originator


@transaction.atomic
def update_loan_originator(command: UpdateLoanOriginatorCommand) -> LoanOriginator:
    _require_admin(command.actor)
    unknown = set(command.changes) - ORIGINATOR_MUTABLE_FIELDS
    if unknown:
        raise OriginatorClaimsValidationError(
            "Unsupported Loan Originator fields: " + ", ".join(sorted(unknown))
        )
    originator = _locked_originator(command.originator_id)
    changes = dict(command.changes)
    if "settlement_iban" in changes:
        try:
            changes["settlement_iban"] = normalize_and_validate_iban(
                str(changes["settlement_iban"])
            )
        except IbanValidationError as exc:
            raise OriginatorClaimsValidationError(str(exc)) from exc
    if "default_premium_fee_bps" in changes:
        changes["default_premium_fee_bps"] = _fee_bps(
            changes["default_premium_fee_bps"], "Default premium fee"
        )
    if "status" in changes and changes["status"] not in {
        choice for choice, _label in LoanOriginatorStatus.choices
    }:
        raise OriginatorClaimsValidationError("Invalid Loan Originator status.")
    for field_name, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(originator, field_name, value)
    originator.updated_by_admin_id = command.actor.pk
    originator.save(update_fields=[*changes, "updated_by_admin_id", "updated_at"])
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.ORIGINATOR_UPDATED,
        originator=originator,
        metadata={"changed_fields": sorted(changes)},
    )
    return originator


def _parse_import(command: CreateOriginatorLoanCommand) -> ParsedOriginatorImport:
    try:
        return parse_originator_import_csv(
            csv_content=command.csv_content,
            original_principal_minor=command.original_principal_minor,
            as_of_date=command.as_of_date,
            repayment_type=command.repayment_type,
            interest_only_months=command.interest_only_months,
        )
    except OriginatorImportValidationError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc


def _snapshot_value(snapshot: dict[str, Any], key: str, default: Any = "") -> Any:
    value = snapshot.get(key, default)
    return default if value is None else value


def _private_borrower_snapshot(profile: OriginatorLoanProfile) -> dict[str, Any]:
    return {
        "borrower_legal_name": profile.borrower_legal_name,
        "borrower_display_name": profile.borrower_display_name,
        "year_founded": profile.borrower_year_founded,
        "entity_type": profile.borrower_entity_type,
        "country": profile.borrower_country,
        "registration_number": profile.borrower_registration_number,
        "business_classification": profile.business_classification,
        "business_classification_public": profile.business_classification_public,
        "registered_address": profile.registered_address,
        "registered_address_public": profile.registered_address_public,
        "operating_address": profile.operating_address,
        "contact_info": profile.contact_info,
        "contact_info_public": profile.contact_info_public,
        "industry_activity": profile.industry_activity,
        "ownership_structure": profile.ownership_structure,
        "beneficial_owners": profile.beneficial_owners,
        "directors_officers": profile.directors_officers,
        "authorized_signatories": profile.authorized_signatories,
        "bank_account_details": profile.bank_account_details,
        "kyb_aml_observations": profile.kyb_aml_observations,
        "financial_risk": profile.financial_risk,
        "financials_currency": profile.financials_currency,
        "assets_minor": profile.assets_minor,
        "liabilities_minor": profile.liabilities_minor,
        "revenue_last_year_minor": profile.revenue_last_year_minor,
        "profit_last_year_minor": profile.profit_last_year_minor,
    }


def _apply_borrower_snapshot(
    profile: OriginatorLoanProfile,
    snapshot: dict[str, Any],
) -> None:
    profile.borrower_legal_name = _required(
        str(_snapshot_value(snapshot, "borrower_legal_name")),
        "Borrower legal name",
    )
    profile.borrower_display_name = _required(
        str(_snapshot_value(snapshot, "borrower_display_name")),
        "Anonymized borrower display name",
    )
    profile.borrower_year_founded = _snapshot_value(snapshot, "year_founded", None)
    profile.borrower_entity_type = str(_snapshot_value(snapshot, "entity_type"))
    profile.borrower_country = str(_snapshot_value(snapshot, "country"))
    profile.borrower_registration_number = str(_snapshot_value(snapshot, "registration_number"))
    profile.business_classification = str(_snapshot_value(snapshot, "business_classification"))
    profile.business_classification_public = bool(
        _snapshot_value(snapshot, "business_classification_public", False)
    )
    profile.registered_address = str(_snapshot_value(snapshot, "registered_address"))
    profile.registered_address_public = bool(
        _snapshot_value(snapshot, "registered_address_public", False)
    )
    profile.operating_address = str(_snapshot_value(snapshot, "operating_address"))
    profile.contact_info = str(_snapshot_value(snapshot, "contact_info"))
    profile.contact_info_public = bool(_snapshot_value(snapshot, "contact_info_public", False))
    profile.industry_activity = str(_snapshot_value(snapshot, "industry_activity"))
    profile.ownership_structure = str(_snapshot_value(snapshot, "ownership_structure"))
    profile.beneficial_owners = _snapshot_value(snapshot, "beneficial_owners", [])
    profile.directors_officers = _snapshot_value(snapshot, "directors_officers", [])
    profile.authorized_signatories = _snapshot_value(snapshot, "authorized_signatories", [])
    profile.bank_account_details = _snapshot_value(snapshot, "bank_account_details", {})
    profile.kyb_aml_observations = str(_snapshot_value(snapshot, "kyb_aml_observations"))
    profile.financial_risk = str(_snapshot_value(snapshot, "financial_risk"))
    profile.financials_currency = str(_snapshot_value(snapshot, "financials_currency"))
    profile.assets_minor = _snapshot_value(snapshot, "assets_minor", None)
    profile.liabilities_minor = _snapshot_value(snapshot, "liabilities_minor", None)
    profile.revenue_last_year_minor = _snapshot_value(snapshot, "revenue_last_year_minor", None)
    profile.profit_last_year_minor = _snapshot_value(snapshot, "profit_last_year_minor", None)


def _validate_borrower_snapshot(snapshot: dict[str, Any]) -> None:
    _required(
        str(_snapshot_value(snapshot, "borrower_legal_name")),
        "Borrower legal name",
    )
    _required(
        str(_snapshot_value(snapshot, "borrower_display_name")),
        "Anonymized borrower display name",
    )
    year_founded = _snapshot_value(snapshot, "year_founded", None)
    if year_founded is not None and (
        type(year_founded) is not int
        or year_founded < 1800
        or year_founded > business_date(now_utc()).year
    ):
        raise OriginatorClaimsValidationError(
            "Borrower year founded must be between 1800 and the current year."
        )
    for field_name in (
        "beneficial_owners",
        "directors_officers",
        "authorized_signatories",
    ):
        if not isinstance(_snapshot_value(snapshot, field_name, []), list):
            raise OriginatorClaimsValidationError(
                f"Borrower {field_name.replace('_', ' ')} must be a JSON list."
            )
    if not isinstance(_snapshot_value(snapshot, "bank_account_details", {}), dict):
        raise OriginatorClaimsValidationError(
            "Borrower bank account details must be a JSON object."
        )
    financials_currency = str(_snapshot_value(snapshot, "financials_currency")).strip().upper()
    if financials_currency and len(financials_currency) != 3:
        raise OriginatorClaimsValidationError(
            "Borrower financials currency must be a three-letter ISO code."
        )
    for field_name in (
        "assets_minor",
        "liabilities_minor",
        "revenue_last_year_minor",
    ):
        value = _snapshot_value(snapshot, field_name, None)
        if value is not None and (type(value) is not int or value < 0):
            raise OriginatorClaimsValidationError(
                f"Borrower {field_name.replace('_', ' ')} must be a non-negative integer."
            )
    profit = _snapshot_value(snapshot, "profit_last_year_minor", None)
    if profit is not None and type(profit) is not int:
        raise OriginatorClaimsValidationError("Borrower profit last year minor must be an integer.")


def _persist_import_revision(
    *,
    actor: Model,
    loan: Model,
    revision: int,
    parsed: ParsedOriginatorImport,
    as_of_date: date,
    source_filename: str,
    csv_content: str,
    validation_summary: dict[str, Any],
) -> OriginatorLoanImport:
    loan_import = OriginatorLoanImport.objects.create(
        loan=loan,
        revision=revision,
        as_of_date=as_of_date,
        original_principal_minor=int(cast(Any, loan).original_principal_minor),
        current_outstanding_principal_minor=(parsed.current_outstanding_principal_minor),
        currency_code=str(cast(Any, loan).currency_id),
        source_filename=_required(source_filename, "Source filename"),
        source_csv=csv_content,
        source_sha256=hashlib.sha256(csv_content.encode("utf-8")).hexdigest(),
        schedule_row_count=len(parsed.schedule_rows),
        payment_row_count=len(parsed.payment_rows),
        imported_by_admin_id=actor.pk,
        imported_at=now_utc(),
        validation_summary=validation_summary,
    )
    OriginatorLoanScheduleRow.objects.bulk_create(
        [
            OriginatorLoanScheduleRow(
                loan_import=loan_import,
                installment_number=row.installment_number,
                accrual_start_date=row.accrual_start_date,
                due_date=row.due_date,
                opening_principal_minor=row.opening_principal_minor,
                principal_minor=row.principal_minor,
                interest_minor=row.interest_minor,
                penalty_minor=row.penalty_minor,
                fee_minor=row.fee_minor,
                total_minor=row.total_minor,
                closing_principal_minor=row.closing_principal_minor,
            )
            for row in parsed.schedule_rows
        ]
    )
    OriginatorLoanPaymentRow.objects.bulk_create(
        [
            OriginatorLoanPaymentRow(
                loan_import=loan_import,
                reference=row.reference,
                value_date=row.value_date,
                payment_type=row.payment_type,
                principal_minor=row.principal_minor,
                interest_minor=row.interest_minor,
                penalty_minor=row.penalty_minor,
                fee_minor=row.fee_minor,
                total_minor=row.total_minor,
                resulting_principal_minor=row.resulting_principal_minor,
            )
            for row in parsed.payment_rows
        ]
    )
    return cast(OriginatorLoanImport, loan_import)


def _validate_par_subscription_terms(
    command: CreateOriginatorLoanCommand,
    *,
    parsed: ParsedOriginatorImport,
) -> tuple[Any, list[Any]]:
    if (
        command.funding_deadline is None
        or command.entitlement_start_date is None
        or command.activation_outstanding_principal_minor is None
        or command.investor_interest_participation_bps is None
        or command.investor_penalty_participation_bps is None
    ):
        raise OriginatorClaimsValidationError(
            "Funding deadline, boundary installment, post-boundary principal, and investor "
            "component participation are required."
        )
    if command.funding_deadline < command.as_of_date:
        raise OriginatorClaimsValidationError("Funding deadline cannot be in the past.")
    if command.funding_deadline > command.as_of_date + timedelta(days=29):
        raise OriginatorClaimsValidationError(
            "Funding deadline cannot be later than 29 days after the publication date."
        )
    if command.funding_deadline >= command.entitlement_start_date:
        raise OriginatorClaimsValidationError(
            "Funding must close before the boundary installment payment date."
        )
    boundary_rows = [
        row for row in parsed.schedule_rows if row.due_date == command.entitlement_start_date
    ]
    if len(boundary_rows) != 1:
        raise OriginatorClaimsValidationError(
            "The entitlement start date must match exactly one imported installment due date."
        )
    boundary_row = boundary_rows[0]
    installments_after_funding = sorted(
        (row for row in parsed.schedule_rows if row.due_date > command.funding_deadline),
        key=lambda row: (row.due_date, row.installment_number),
    )
    if (
        not installments_after_funding
        or installments_after_funding[0].due_date != command.entitlement_start_date
    ):
        raise OriginatorClaimsValidationError(
            "The boundary installment must be the first installment due after the funding deadline."
        )
    activation_principal = _positive_minor(
        command.activation_outstanding_principal_minor,
        "Post-boundary outstanding principal",
    )
    if boundary_row.closing_principal_minor != activation_principal:
        raise OriginatorClaimsValidationError(
            "Post-boundary outstanding principal must equal the boundary installment's "
            "closing principal."
        )
    future_rows = [
        row for row in parsed.schedule_rows if row.due_date > command.entitlement_start_date
    ]
    if not future_rows:
        raise OriginatorClaimsValidationError(
            "At least one installment must remain after the boundary installment."
        )
    if sum(row.principal_minor for row in future_rows) != activation_principal:
        raise OriginatorClaimsValidationError(
            "Post-boundary schedule principal must equal the declared starting principal."
        )
    if parsed.maturity_date <= command.entitlement_start_date + timedelta(days=30):
        raise OriginatorClaimsValidationError(
            "At least 30 calendar days must remain after the entitlement start date."
        )
    return boundary_row, future_rows


@transaction.atomic
def create_originator_loan(command: CreateOriginatorLoanCommand) -> OriginatorLoanCreationResult:
    _require_admin(command.actor)
    _validate_borrower_snapshot(command.borrower_snapshot)
    parsed = _parse_import(command)
    originator = _locked_originator(command.originator_id)
    if originator.status != LoanOriginatorStatus.ACTIVE:
        raise OriginatorClaimsValidationError(
            "Loan Originator must be active before a loan can be created."
        )
    loan_model = apps.get_model("loans", "Loan")
    currency = _enabled_currency(command.currency)
    try:
        distribution_model = OriginatorDistributionModel(command.distribution_model)
    except ValueError as exc:
        raise OriginatorClaimsValidationError("Unsupported originator distribution model.") from exc
    if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2:
        _boundary_row, future_rows = _validate_par_subscription_terms(command, parsed=parsed)
        interest_participation_bps = _participation_bps(
            command.investor_interest_participation_bps,
            "Investor interest participation",
        )
        penalty_participation_bps = _participation_bps(
            command.investor_penalty_participation_bps,
            "Investor penalty participation",
        )
        display_yield_bps = _display_yield_bps(
            coupon_bps=command.interest_rate_bps,
            interest_participation_bps=interest_participation_bps,
        )
        profile_principal_minor = cast(int, command.activation_outstanding_principal_minor)
        loan_principal_minor = profile_principal_minor
        loan_start_date = cast(date, command.entitlement_start_date)
        funding_deadline = cast(date, command.funding_deadline)
        first_payment_date = future_rows[0].due_date
        term_months = len(future_rows)
        premium_fee_bps = 0
    else:
        future_rows = [row for row in parsed.schedule_rows if row.due_date > command.as_of_date]
        first_future = future_rows[0] if future_rows else parsed.schedule_rows[-1]
        if command.target_yield_bps is None:
            raise OriginatorClaimsValidationError("Legacy target yield is required.")
        display_yield_bps = _positive_minor(command.target_yield_bps, "Target yield")
        interest_participation_bps = 10_000
        penalty_participation_bps = 10_000
        profile_principal_minor = parsed.current_outstanding_principal_minor
        loan_principal_minor = _positive_minor(
            command.original_principal_minor, "Original principal"
        )
        loan_start_date = parsed.schedule_rows[0].accrual_start_date
        funding_deadline = None
        first_payment_date = first_future.due_date
        term_months = max(1, len(parsed.schedule_rows))
        premium_fee_bps = (
            originator.default_premium_fee_bps
            if command.premium_fee_bps is None
            else _fee_bps(command.premium_fee_bps, "Premium fee")
        )
    borrower_display_name = _required(
        str(_snapshot_value(command.borrower_snapshot, "borrower_display_name")),
        "Anonymized borrower display name",
    )
    borrower_legal_name = _required(
        str(_snapshot_value(command.borrower_snapshot, "borrower_legal_name")),
        "Borrower legal name",
    )
    loan = loan_model.objects.create(
        borrower=None,
        product_type="originator_claim",
        status="draft",
        title=_required(command.title, "Title"),
        investor_summary=_required(command.investor_summary, "Investor summary"),
        purpose=_required(command.purpose, "Purpose"),
        purpose_description=command.purpose_description.strip(),
        is_refinancing=False,
        original_principal_minor=_positive_minor(
            command.original_principal_minor, "Original principal"
        ),
        principal_minor=loan_principal_minor,
        currency=currency,
        interest_rate_bps=_positive_minor(command.interest_rate_bps, "Interest rate"),
        term_months=term_months,
        repayment_type=command.repayment_type,
        interest_only_months=command.interest_only_months,
        loan_start_date=loan_start_date,
        funding_deadline=funding_deadline,
        first_payment_date=first_payment_date,
        pre_publication_paid_installments=[],
        collateral_type=command.collateral_type,
        collateral_value_minor=command.collateral_value_minor,
        collateral_description=command.collateral_description.strip(),
        risk_rating=command.risk_rating,
        skin_in_the_game_bps=_skin_bps(command.skin_in_the_game_bps),
        borrower_success_fee_bps=0,
        lender_payment_fee_minor=0,
        minimum_subscription_bps=0,
        schedule_version=1,
        total_scheduled_principal_minor=sum(row.principal_minor for row in future_rows),
        total_scheduled_interest_minor=sum(row.interest_minor for row in future_rows),
        committed_principal_minor=0,
        created_by_admin_id=command.actor.pk,
    )
    snapshot = command.borrower_snapshot
    profile = OriginatorLoanProfile.objects.create(
        loan=loan,
        originator=originator,
        distribution_model=distribution_model,
        target_yield_bps=display_yield_bps,
        minimum_investment_minor=_positive_minor(
            command.minimum_investment_minor, "Minimum investment"
        ),
        premium_fee_bps=premium_fee_bps,
        funding_deadline=funding_deadline,
        entitlement_start_date=(
            command.entitlement_start_date
            if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2
            else None
        ),
        activation_outstanding_principal_minor=(
            profile_principal_minor
            if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2
            else None
        ),
        investor_interest_participation_bps=interest_participation_bps,
        investor_penalty_participation_bps=penalty_participation_bps,
        current_outstanding_principal_minor=profile_principal_minor,
        unsold_principal_minor=profile_principal_minor,
        maturity_date=parsed.maturity_date,
        borrower_legal_name=borrower_legal_name,
        borrower_display_name=borrower_display_name,
        borrower_year_founded=_snapshot_value(snapshot, "year_founded", None),
        borrower_entity_type=str(_snapshot_value(snapshot, "entity_type")),
        borrower_country=str(_snapshot_value(snapshot, "country")),
        borrower_registration_number=str(_snapshot_value(snapshot, "registration_number")),
        business_classification=str(_snapshot_value(snapshot, "business_classification")),
        business_classification_public=bool(
            _snapshot_value(snapshot, "business_classification_public", False)
        ),
        registered_address=str(_snapshot_value(snapshot, "registered_address")),
        registered_address_public=bool(
            _snapshot_value(snapshot, "registered_address_public", False)
        ),
        operating_address=str(_snapshot_value(snapshot, "operating_address")),
        contact_info=str(_snapshot_value(snapshot, "contact_info")),
        contact_info_public=bool(_snapshot_value(snapshot, "contact_info_public", False)),
        industry_activity=str(_snapshot_value(snapshot, "industry_activity")),
        ownership_structure=str(_snapshot_value(snapshot, "ownership_structure")),
        beneficial_owners=_snapshot_value(snapshot, "beneficial_owners", []),
        directors_officers=_snapshot_value(snapshot, "directors_officers", []),
        authorized_signatories=_snapshot_value(snapshot, "authorized_signatories", []),
        bank_account_details=_snapshot_value(snapshot, "bank_account_details", {}),
        kyb_aml_observations=str(_snapshot_value(snapshot, "kyb_aml_observations")),
        financial_risk=str(_snapshot_value(snapshot, "financial_risk")),
        financials_currency=str(_snapshot_value(snapshot, "financials_currency")),
        assets_minor=_snapshot_value(snapshot, "assets_minor", None),
        liabilities_minor=_snapshot_value(snapshot, "liabilities_minor", None),
        revenue_last_year_minor=_snapshot_value(snapshot, "revenue_last_year_minor", None),
        profit_last_year_minor=_snapshot_value(snapshot, "profit_last_year_minor", None),
    )
    loan_import = OriginatorLoanImport.objects.create(
        loan=loan,
        revision=1,
        as_of_date=command.as_of_date,
        original_principal_minor=command.original_principal_minor,
        current_outstanding_principal_minor=parsed.current_outstanding_principal_minor,
        currency_code=currency.code,
        source_filename=_required(command.source_filename, "Source filename"),
        source_csv=command.csv_content,
        source_sha256=hashlib.sha256(command.csv_content.encode("utf-8")).hexdigest(),
        schedule_row_count=len(parsed.schedule_rows),
        payment_row_count=len(parsed.payment_rows),
        imported_by_admin_id=command.actor.pk,
        imported_at=timezone.now(),
        validation_summary={
            "maturity_date": parsed.maturity_date.isoformat(),
            "future_schedule_rows": len(future_rows),
            "distribution_model": distribution_model,
            "funding_deadline": funding_deadline.isoformat() if funding_deadline else None,
            "entitlement_start_date": (
                command.entitlement_start_date.isoformat()
                if command.entitlement_start_date
                else None
            ),
            "activation_outstanding_principal_minor": (
                profile_principal_minor
                if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2
                else None
            ),
        },
    )
    OriginatorLoanScheduleRow.objects.bulk_create(
        [
            OriginatorLoanScheduleRow(
                loan_import=loan_import,
                installment_number=row.installment_number,
                accrual_start_date=row.accrual_start_date,
                due_date=row.due_date,
                opening_principal_minor=row.opening_principal_minor,
                principal_minor=row.principal_minor,
                interest_minor=row.interest_minor,
                penalty_minor=row.penalty_minor,
                fee_minor=row.fee_minor,
                total_minor=row.total_minor,
                closing_principal_minor=row.closing_principal_minor,
            )
            for row in parsed.schedule_rows
        ]
    )
    OriginatorLoanPaymentRow.objects.bulk_create(
        [
            OriginatorLoanPaymentRow(
                loan_import=loan_import,
                reference=row.reference,
                value_date=row.value_date,
                payment_type=row.payment_type,
                principal_minor=row.principal_minor,
                interest_minor=row.interest_minor,
                penalty_minor=row.penalty_minor,
                fee_minor=row.fee_minor,
                total_minor=row.total_minor,
                resulting_principal_minor=row.resulting_principal_minor,
            )
            for row in parsed.payment_rows
        ]
    )
    profile.current_import = loan_import
    profile.save(update_fields=["current_import", "updated_at"])
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.LOAN_CREATED,
        originator=originator,
        loan_id=loan.id,
        metadata={
            "current_outstanding_principal_minor": profile_principal_minor,
            "target_yield_bps": profile.target_yield_bps,
            "distribution_model": profile.distribution_model,
            "investor_interest_participation_bps": interest_participation_bps,
            "investor_penalty_participation_bps": penalty_participation_bps,
            "skin_in_the_game_bps": int(loan.skin_in_the_game_bps),
            "schedule_revision": 1,
        },
    )
    return OriginatorLoanCreationResult(loan=loan, profile=profile, loan_import=loan_import)


def get_originator_admin_loan_payload(*, actor: Model, loan_id: str) -> dict[str, Any]:
    _require_admin(actor)
    profile = (
        OriginatorLoanProfile.objects.select_related(
            "loan__currency", "originator", "current_import"
        )
        .filter(loan_id=loan_id)
        .first()
    )
    if profile is None or profile.current_import is None:
        raise OriginatorClaimsValidationError("Originator claim loan does not exist.")
    loan = cast(Any, profile.loan)
    loan_import = profile.current_import
    return {
        "loan_id": str(profile.loan_id),
        "originator_id": str(profile.originator_id),
        "originator_name": profile.originator.public_name,
        "title": str(loan.title),
        "investor_summary": str(loan.investor_summary),
        "purpose": str(loan.purpose),
        "purpose_description": str(loan.purpose_description),
        "status": str(loan.status),
        "opportunity_status": profile.opportunity_status,
        "currency": str(loan.currency_id),
        "original_principal_minor": int(loan.original_principal_minor),
        "current_outstanding_principal_minor": int(profile.current_outstanding_principal_minor),
        "unsold_principal_minor": int(profile.unsold_principal_minor),
        "retained_principal_minor": originator_retained_principal_minor(profile),
        "sellable_principal_minor": originator_sellable_principal_minor(profile),
        "interest_rate_bps": int(loan.interest_rate_bps),
        "target_yield_bps": int(profile.target_yield_bps),
        "distribution_model": str(profile.distribution_model),
        "minimum_investment_minor": int(profile.minimum_investment_minor),
        "premium_fee_bps": int(profile.premium_fee_bps),
        "funding_deadline": profile.funding_deadline,
        "entitlement_start_date": profile.entitlement_start_date,
        "activation_outstanding_principal_minor": (
            int(profile.activation_outstanding_principal_minor)
            if profile.activation_outstanding_principal_minor is not None
            else None
        ),
        "investor_interest_participation_bps": int(profile.investor_interest_participation_bps),
        "investor_penalty_participation_bps": int(profile.investor_penalty_participation_bps),
        "skin_in_the_game_bps": int(loan.skin_in_the_game_bps),
        "repayment_type": str(loan.repayment_type),
        "interest_only_months": int(loan.interest_only_months),
        "collateral_type": str(loan.collateral_type),
        "collateral_value_minor": int(loan.collateral_value_minor),
        "collateral_description": str(loan.collateral_description),
        "risk_rating": str(loan.risk_rating),
        "maturity_date": profile.maturity_date,
        "schedule_revision": int(profile.schedule_revision),
        "borrower_snapshot": _private_borrower_snapshot(profile),
        "current_import_id": str(loan_import.id),
        "import_as_of_date": loan_import.as_of_date,
        "source_filename": loan_import.source_filename,
        "source_sha256": loan_import.source_sha256,
        "schedule": [
            {
                "installment_number": int(row.installment_number),
                "accrual_start_date": row.accrual_start_date,
                "due_date": row.due_date,
                "opening_principal_minor": int(row.opening_principal_minor),
                "principal_minor": int(row.principal_minor),
                "interest_minor": int(row.interest_minor),
                "penalty_minor": int(row.penalty_minor),
                "fee_minor": int(row.fee_minor),
                "total_minor": int(row.total_minor),
                "closing_principal_minor": int(row.closing_principal_minor),
            }
            for row in loan_import.schedule_rows.all()
        ],
        "payment_history": [
            {
                "reference": row.reference,
                "value_date": row.value_date,
                "payment_type": row.payment_type,
                "principal_minor": int(row.principal_minor),
                "interest_minor": int(row.interest_minor),
                "penalty_minor": int(row.penalty_minor),
                "fee_minor": int(row.fee_minor),
                "total_minor": int(row.total_minor),
                "resulting_principal_minor": int(row.resulting_principal_minor),
            }
            for row in loan_import.payment_rows.all()
        ],
        "is_on_hold": profile.is_on_hold,
        "hold_reason": profile.hold_reason,
    }


@transaction.atomic
def replace_originator_loan_draft(
    *,
    loan_id: str,
    command: CreateOriginatorLoanCommand,
) -> OriginatorLoanCreationResult:
    _require_admin(command.actor)
    _validate_borrower_snapshot(command.borrower_snapshot)
    parsed = _parse_import(command)
    profile = (
        OriginatorLoanProfile.objects.select_for_update(of=("self",))
        .select_related("loan__currency", "originator", "current_import")
        .filter(loan_id=loan_id)
        .first()
    )
    if profile is None:
        raise OriginatorClaimsValidationError("Originator claim loan does not exist.")
    loan = cast(Any, profile.loan)
    if loan.status != "draft" or profile.opportunity_status != OriginatorOpportunityStatus.DRAFT:
        raise OriginatorClaimsValidationError(
            "Only an unpublished originator claim draft can be replaced."
        )
    if profile.quotes.exists() or profile.purchases.exists():
        raise OriginatorClaimsValidationError(
            "A draft with quote or purchase evidence cannot be replaced."
        )
    originator = _locked_originator(command.originator_id)
    if originator.status != LoanOriginatorStatus.ACTIVE:
        raise OriginatorClaimsValidationError(
            "Loan Originator must be active before a draft can be updated."
        )
    currency = _enabled_currency(command.currency)
    try:
        distribution_model = OriginatorDistributionModel(command.distribution_model)
    except ValueError as exc:
        raise OriginatorClaimsValidationError("Unsupported originator distribution model.") from exc
    if distribution_model != profile.distribution_model:
        raise OriginatorClaimsValidationError(
            "A draft cannot change its originator distribution model."
        )
    if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2:
        _boundary_row, future_rows = _validate_par_subscription_terms(command, parsed=parsed)
        interest_participation_bps = _participation_bps(
            command.investor_interest_participation_bps,
            "Investor interest participation",
        )
        penalty_participation_bps = _participation_bps(
            command.investor_penalty_participation_bps,
            "Investor penalty participation",
        )
        display_yield_bps = _display_yield_bps(
            coupon_bps=command.interest_rate_bps,
            interest_participation_bps=interest_participation_bps,
        )
        profile_principal_minor = cast(int, command.activation_outstanding_principal_minor)
        loan_principal_minor = profile_principal_minor
        loan_start_date = cast(date, command.entitlement_start_date)
        funding_deadline = cast(date, command.funding_deadline)
        first_payment_date = future_rows[0].due_date
        term_months = len(future_rows)
        premium_fee_bps = 0
    else:
        future_rows = [row for row in parsed.schedule_rows if row.due_date > command.as_of_date]
        first_future = future_rows[0] if future_rows else parsed.schedule_rows[-1]
        if command.target_yield_bps is None:
            raise OriginatorClaimsValidationError("Legacy target yield is required.")
        display_yield_bps = _positive_minor(command.target_yield_bps, "Target yield")
        interest_participation_bps = 10_000
        penalty_participation_bps = 10_000
        profile_principal_minor = parsed.current_outstanding_principal_minor
        loan_principal_minor = _positive_minor(
            command.original_principal_minor, "Original principal"
        )
        loan_start_date = parsed.schedule_rows[0].accrual_start_date
        funding_deadline = None
        first_payment_date = first_future.due_date
        term_months = max(1, len(parsed.schedule_rows))
        premium_fee_bps = (
            originator.default_premium_fee_bps
            if command.premium_fee_bps is None
            else _fee_bps(command.premium_fee_bps, "Premium fee")
        )

    loan.title = _required(command.title, "Title")
    loan.investor_summary = _required(command.investor_summary, "Investor summary")
    loan.purpose = _required(command.purpose, "Purpose")
    loan.purpose_description = command.purpose_description.strip()
    loan.original_principal_minor = _positive_minor(
        command.original_principal_minor, "Original principal"
    )
    loan.principal_minor = loan_principal_minor
    loan.currency = currency
    loan.interest_rate_bps = _positive_minor(command.interest_rate_bps, "Interest rate")
    loan.term_months = term_months
    loan.repayment_type = command.repayment_type
    loan.interest_only_months = command.interest_only_months
    loan.loan_start_date = loan_start_date
    loan.funding_deadline = funding_deadline
    loan.first_payment_date = first_payment_date
    loan.collateral_type = command.collateral_type
    loan.collateral_value_minor = command.collateral_value_minor
    loan.collateral_description = command.collateral_description.strip()
    loan.risk_rating = command.risk_rating
    loan.skin_in_the_game_bps = _skin_bps(command.skin_in_the_game_bps)
    loan.minimum_subscription_bps = 0
    loan.total_scheduled_principal_minor = sum(row.principal_minor for row in future_rows)
    loan.total_scheduled_interest_minor = sum(row.interest_minor for row in future_rows)
    revision = int(profile.schedule_revision) + 1
    loan.schedule_version = revision
    loan.updated_by_admin_id = command.actor.pk
    loan.save()

    profile.originator = originator
    profile.distribution_model = distribution_model
    profile.target_yield_bps = display_yield_bps
    profile.minimum_investment_minor = _positive_minor(
        command.minimum_investment_minor, "Minimum investment"
    )
    profile.premium_fee_bps = premium_fee_bps
    profile.funding_deadline = funding_deadline
    profile.entitlement_start_date = (
        command.entitlement_start_date
        if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2
        else None
    )
    profile.activation_outstanding_principal_minor = (
        profile_principal_minor
        if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2
        else None
    )
    profile.investor_interest_participation_bps = interest_participation_bps
    profile.investor_penalty_participation_bps = penalty_participation_bps
    profile.current_outstanding_principal_minor = profile_principal_minor
    profile.unsold_principal_minor = profile_principal_minor
    profile.maturity_date = parsed.maturity_date
    _apply_borrower_snapshot(profile, command.borrower_snapshot)
    loan_import = _persist_import_revision(
        actor=command.actor,
        loan=loan,
        revision=revision,
        parsed=parsed,
        as_of_date=command.as_of_date,
        source_filename=command.source_filename,
        csv_content=command.csv_content,
        validation_summary={
            "maturity_date": parsed.maturity_date.isoformat(),
            "future_schedule_rows": len(future_rows),
            "distribution_model": distribution_model,
            "funding_deadline": funding_deadline.isoformat() if funding_deadline else None,
            "entitlement_start_date": (
                command.entitlement_start_date.isoformat()
                if command.entitlement_start_date
                else None
            ),
            "activation_outstanding_principal_minor": (
                profile_principal_minor
                if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2
                else None
            ),
            "action": "draft_replaced",
            "previous_revision": int(profile.schedule_revision),
        },
    )
    profile.schedule_revision = revision
    profile.current_import = loan_import
    profile.save()
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.IMPORT_VALIDATED,
        originator=originator,
        loan_id=loan.id,
        metadata={
            "action": "draft_replaced",
            "schedule_revision": revision,
            "current_outstanding_principal_minor": (parsed.current_outstanding_principal_minor),
            "skin_in_the_game_bps": int(loan.skin_in_the_game_bps),
            "source_sha256": loan_import.source_sha256,
        },
    )
    return OriginatorLoanCreationResult(
        loan=loan,
        profile=profile,
        loan_import=loan_import,
    )


@transaction.atomic
def publish_originator_loan(command: PublishOriginatorLoanCommand) -> OriginatorLoanProfile:
    _require_admin(command.actor)
    profile = _locked_profile_for_loan(
        command.loan_id,
        "loan",
        "originator",
        "current_import",
    )
    loan = profile.loan
    if loan.status != "draft" or profile.opportunity_status != OriginatorOpportunityStatus.DRAFT:
        raise OriginatorClaimsValidationError(
            "Only a draft originator opportunity can be published."
        )
    if profile.originator.status != LoanOriginatorStatus.ACTIVE:
        raise OriginatorClaimsValidationError("Loan Originator is not active.")
    if profile.current_import_id is None:
        raise OriginatorClaimsValidationError("A validated schedule/payment import is required.")
    if profile.current_outstanding_principal_minor <= 0:
        raise OriginatorClaimsValidationError("A repaid loan cannot be published.")
    if originator_sellable_principal_minor(profile) <= 0:
        raise OriginatorClaimsValidationError(
            "The declared skin in the game leaves no principal available to investors."
        )
    if profile.is_on_hold:
        raise OriginatorClaimsValidationError("A held originator loan cannot be published.")
    if profile.maturity_date <= command.as_of_date + timedelta(days=30):
        raise OriginatorClaimsValidationError(
            "Originator opportunities require more than 30 calendar days to maturity."
        )
    if _is_par_subscription(profile):
        if profile.funding_deadline is None or profile.entitlement_start_date is None:
            raise OriginatorClaimsValidationError(
                "Funding and entitlement dates are required for this subscription."
            )
        if profile.funding_deadline < command.as_of_date:
            raise OriginatorClaimsValidationError("Funding deadline cannot be in the past.")
        if profile.funding_deadline > command.as_of_date + timedelta(days=29):
            raise OriginatorClaimsValidationError(
                "Originator subscription funding periods cannot exceed 29 calendar days."
            )
        if profile.funding_deadline >= profile.entitlement_start_date:
            raise OriginatorClaimsValidationError(
                "Funding must close before the boundary installment payment date."
            )
    now = timezone.now()
    # New claims reserve investor money in escrow while the round is open.
    # Legacy claims remain immediately assignable for historical compatibility.
    loan.status = "published" if _is_par_subscription(profile) else "active"
    loan.published_at = now
    loan.updated_by_admin_id = command.actor.pk
    loan.save(update_fields=["status", "published_at", "updated_by_admin_id", "updated_at"])
    profile.opportunity_status = OriginatorOpportunityStatus.OPEN
    profile.published_at = now
    profile.save(update_fields=["opportunity_status", "published_at", "updated_at"])
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.OPPORTUNITY_PUBLISHED,
        originator=profile.originator,
        loan_id=loan.id,
        metadata={
            "maturity_date": profile.maturity_date.isoformat(),
            "funding_deadline": (
                profile.funding_deadline.isoformat() if profile.funding_deadline else None
            ),
            "entitlement_start_date": (
                profile.entitlement_start_date.isoformat()
                if profile.entitlement_start_date
                else None
            ),
            "distribution_model": profile.distribution_model,
            "skin_in_the_game_bps": int(loan.skin_in_the_game_bps),
            "retained_principal_minor": originator_retained_principal_minor(profile),
            "sellable_principal_minor": originator_sellable_principal_minor(profile),
        },
    )
    import_module(
        "backend.apps.smart_invest.services"
    ).notify_smart_invest_matches_for_published_loan(
        loan_id=str(loan.id),
        product_type="originator_claim",
    )
    return profile


def _primary_order_event(
    *,
    order: Any,
    actor: Model,
    event_type: str,
    previous_status: str,
    new_status: str,
    note: str,
    metadata: dict[str, Any],
) -> None:
    event_model = apps.get_model("marketplace_primary", "PrimaryInvestmentOrderEvent")
    event_model.objects.create(
        order=order,
        loan_id=order.loan_id,
        event_type=event_type,
        actor_user_id=actor.pk,
        actor_account_type=str(getattr(actor, "account_type", "")),
        previous_status=previous_status,
        new_status=new_status,
        note=note,
        metadata=metadata,
    )


def _loan_status_event(
    *,
    loan: Any,
    actor: Model,
    event_type: str,
    previous_status: str,
    new_status: str,
    note: str,
    metadata: dict[str, Any],
) -> Model:
    event_model = apps.get_model("loans", "LoanEvent")
    return cast(
        Model,
        event_model.objects.create(
            loan=loan,
            event_type=event_type,
            actor_user_id=actor.pk,
            actor_account_type=str(getattr(actor, "account_type", "")),
            previous_status=previous_status,
            new_status=new_status,
            note=note,
            metadata=metadata,
        ),
    )


@transaction.atomic
def mark_originator_funding_close_failed(
    *,
    triggering_actor: Model,
    loan_id: str,
    as_of_date: date,
    resolution_action: str,
    error: Exception,
) -> dict[str, str]:
    """Hide a failed v2 close while preserving every investor reservation."""

    operations_actor = _operations_admin_actor(triggering_actor)
    loan_model = apps.get_model("loans", "Loan")
    loan = loan_model.objects.select_for_update().filter(id=loan_id).first()
    if loan is None:
        raise OriginatorClaimsValidationError("Originator claim loan does not exist.")
    profile = _locked_profile_for_loan(loan_id, "originator")
    if not _is_par_subscription(profile):
        raise OriginatorClaimsValidationError(
            "Legacy originator opportunities do not use subscription close-failure handling."
        )
    if OriginatorFundingRoundClose.objects.filter(loan_profile=profile).exists():
        return {"loan_id": loan_id, "reason": "funding_round_already_closed"}
    if str(loan.status) not in {"published", "funding_close_failed"}:
        return {"loan_id": loan_id, "reason": f"loan_status_{loan.status}"}

    error_message = str(error).strip() or error.__class__.__name__
    previous_loan_status = str(loan.status)
    failed_at = now_utc()
    loan.status = "funding_close_failed"
    loan.updated_by_admin_id = operations_actor.pk
    loan.save(update_fields=["status", "updated_by_admin_id", "updated_at"])
    profile.is_on_hold = True
    profile.hold_reason = f"Automatic funding close failed: {error_message}"[:255]
    profile.held_at = failed_at
    profile.held_by_admin_id = operations_actor.pk
    profile.save(
        update_fields=[
            "is_on_hold",
            "hold_reason",
            "held_at",
            "held_by_admin_id",
            "updated_at",
        ]
    )
    metadata = {
        "loan_id": loan_id,
        "as_of_date": as_of_date.isoformat(),
        "resolution_action": resolution_action,
        "failure_type": error.__class__.__name__,
        "failure_reason": error_message,
        "currency": str(loan.currency_id),
        "subscribed_principal_minor": int(loan.committed_principal_minor),
        "sellable_principal_minor": originator_sellable_principal_minor(profile),
        "reservations_preserved": True,
        "triggering_user_id": str(triggering_actor.pk),
        "triggering_account_type": str(getattr(triggering_actor, "account_type", "")),
    }
    loan_event = _loan_status_event(
        loan=loan,
        actor=operations_actor,
        event_type="funding_close_failed",
        previous_status=previous_loan_status,
        new_status=str(loan.status),
        note=error_message,
        metadata=metadata,
    )
    _record_event(
        actor=operations_actor,
        event_type=OriginatorClaimEventType.FUNDING_ROUND_CLOSE_FAILED,
        originator=profile.originator,
        loan_id=loan.id,
        note=error_message,
        metadata={**metadata, "loan_event_id": str(loan_event.pk)},
    )
    admin_ops = import_module("backend.apps.admin_ops.services")
    task = admin_ops.ensure_loan_funding_close_failure_task(
        admin_ops.EnsureLoanFundingCloseFailureTaskCommand(
            actor=operations_actor,
            loan_id=loan_id,
            loan_title=str(loan.title),
            currency=str(loan.currency_id),
            committed_principal_minor=int(loan.committed_principal_minor),
            target_principal_minor=originator_sellable_principal_minor(profile),
            minimum_subscription_bps=0,
            failure_reason=error_message,
            failure_event_id=str(loan_event.pk),
        )
    )
    _enqueue_operations_email(
        topic="email.originator_funding_close_failed",
        subject=f"BANXUM Loan Originator funding close failed: {loan.title}",
        body_text=(
            f"The automatic {resolution_action} failed for {loan.title} ({loan.id}).\n\n"
            f"Reason: {error_message}\n\n"
            "The opportunity is no longer public. Investor reservations remain locked and "
            "unchanged. Resolve the cause and retry the close, or cancel and refund the round."
        ),
        template_key="originator_subscription.close_failed.v1",
        idempotency_key=f"originator-round-close-failed:{loan_event.pk}",
        metadata={
            **metadata,
            "loan_event_id": str(loan_event.pk),
            "admin_task_id": str(task.id),
        },
    )
    return {
        "loan_id": loan_id,
        "reason": "funding_close_failed",
        "failure_reason": error_message,
        "task_id": str(task.id),
    }


def _subscription_orders_for_update(loan_id: str) -> tuple[list[Any], list[Any]]:
    order_model = apps.get_model("marketplace_primary", "PrimaryInvestmentOrder")
    allocated = list(
        order_model.objects.select_for_update()
        .filter(
            loan_id=loan_id,
            status__in=["balance_allocated", "partially_allocated"],
        )
        .order_by("allocated_at", "created_at", "id")
    )
    pending = list(
        order_model.objects.select_for_update()
        .filter(loan_id=loan_id, status="pending")
        .order_by("created_at", "id")
    )
    return allocated, pending


def _existing_round_close(
    *,
    idempotency_key: str,
    fingerprint: str,
) -> OriginatorFundingRoundClose | None:
    existing = OriginatorFundingRoundClose.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if existing.request_fingerprint != fingerprint:
        raise OriginatorClaimsValidationError(
            "Idempotency key was already used for a different funding-round close."
        )
    return cast(OriginatorFundingRoundClose, existing)


@transaction.atomic
def close_originator_subscription_round(
    command: CloseOriginatorSubscriptionRoundCommand,
) -> OriginatorFundingRoundClose:
    idempotency_key = _required(command.idempotency_key, "Idempotency key")
    if len(idempotency_key) > 160:
        raise OriginatorClaimsValidationError("Idempotency key cannot exceed 160 characters.")
    close_reason = _required(command.close_reason, "Close reason")
    fingerprint = _request_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "as_of_date": command.as_of_date.isoformat(),
            "close_reason": close_reason,
            "idempotency_key": idempotency_key,
        }
    )
    existing = _existing_round_close(
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if existing is not None:
        return existing

    loan_model = apps.get_model("loans", "Loan")
    loan = loan_model.objects.select_for_update().filter(id=command.loan_id).first()
    if loan is None:
        raise OriginatorClaimsValidationError("Originator claim loan does not exist.")
    profile = _locked_profile_for_loan(
        command.loan_id,
        "originator",
        "current_import",
    )
    if not _is_par_subscription(profile):
        raise OriginatorClaimsValidationError(
            "Legacy originator opportunities do not use subscription rounds."
        )
    existing_for_profile = OriginatorFundingRoundClose.objects.filter(loan_profile=profile).first()
    if existing_for_profile is not None:
        if existing_for_profile.idempotency_key == idempotency_key:
            return cast(OriginatorFundingRoundClose, existing_for_profile)
        raise OriginatorClaimsValidationError("Originator funding round is already closed.")
    retrying_failed_close = str(loan.status) == "funding_close_failed"
    if profile.opportunity_status != OriginatorOpportunityStatus.OPEN or str(loan.status) not in {
        "published",
        "funding_close_failed",
    }:
        raise OriginatorClaimsValidationError("Originator funding round is not open.")
    if retrying_failed_close and not is_admin_actor(command.actor):
        raise OriginatorClaimsAuthorizationError(
            "Only an admin can retry a failed originator funding close."
        )
    if profile.is_on_hold and not retrying_failed_close:
        raise OriginatorClaimsValidationError(
            "A held originator funding round cannot close; cancel it or resolve the hold first."
        )
    if profile.funding_deadline is None:
        raise OriginatorClaimsValidationError("Originator funding deadline is unavailable.")

    allocated_orders, pending_orders = _subscription_orders_for_update(str(loan.id))
    subscribed_principal = sum(int(order.allocated_amount_minor) for order in allocated_orders)
    if subscribed_principal <= 0:
        raise OriginatorClaimsValidationError(
            "A funding round without subscriptions must be cancelled, not activated."
        )
    if subscribed_principal != int(loan.committed_principal_minor):
        raise OriginatorClaimsValidationError(
            "Allocated subscriptions do not match the loan committed principal."
        )
    sellable_principal = originator_sellable_principal_minor(profile)
    if subscribed_principal > sellable_principal:
        raise OriginatorClaimsValidationError(
            "Subscribed principal exceeds the Loan Originator claim available for sale."
        )
    fully_subscribed = subscribed_principal == sellable_principal
    deadline_passed = command.as_of_date > profile.funding_deadline
    if not fully_subscribed and not deadline_passed:
        raise OriginatorClaimsValidationError(
            "A partially subscribed originator round can close only after its funding deadline."
        )
    if not is_admin_actor(command.actor) and not (
        fully_subscribed and user_can_access_financial_features(command.actor)
    ):
        raise OriginatorClaimsAuthorizationError(
            "Only an admin can close a partially subscribed originator round."
        )

    closed_at = now_utc()
    pending_ids: list[str] = []
    for order in pending_orders:
        previous_status = str(order.status)
        order.status = "closed_not_invested"
        order.closed_at = closed_at
        order.closed_by_admin_id = command.actor.pk if is_admin_actor(command.actor) else None
        order.admin_notes = close_reason if is_admin_actor(command.actor) else ""
        order.metadata = {
            **cast(dict[str, Any], order.metadata),
            "closed_reason": "Originator subscription round closed before allocation.",
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
        pending_ids.append(str(order.id))
        _primary_order_event(
            order=order,
            actor=command.actor,
            event_type="closed_not_invested",
            previous_status=previous_status,
            new_status=str(order.status),
            note=close_reason,
            metadata={"reason": "originator_subscription_round_closed"},
        )

    metadata = {
        "loan_id": str(loan.id),
        "subscribed_principal_minor": subscribed_principal,
        "sellable_principal_minor": sellable_principal,
        "fully_subscribed": fully_subscribed,
        "allocated_order_ids": [str(order.id) for order in allocated_orders],
        "pending_order_ids_closed_not_invested": pending_ids,
    }
    try:
        with transaction.atomic():
            close = cast(
                OriginatorFundingRoundClose,
                OriginatorFundingRoundClose.objects.create(
                    loan_profile=profile,
                    subscribed_principal_minor=subscribed_principal,
                    allocated_order_count=len(allocated_orders),
                    funding_deadline=profile.funding_deadline,
                    close_reason=close_reason,
                    triggered_by_user_id=command.actor.pk,
                    closed_at=closed_at,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    metadata=metadata,
                ),
            )
    except IntegrityError:
        existing_after_race = _existing_round_close(
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    previous_loan_status = str(loan.status)
    loan.status = "funded"
    loan_update_fields = ["status", "updated_at"]
    if is_admin_actor(command.actor):
        loan.updated_by_admin_id = command.actor.pk
        loan_update_fields.append("updated_by_admin_id")
    loan.save(update_fields=loan_update_fields)
    profile.opportunity_status = OriginatorOpportunityStatus.AWAITING_ACTIVATION
    profile.closed_at = closed_at
    profile.close_reason = close_reason
    profile_update_fields = ["opportunity_status", "closed_at", "close_reason", "updated_at"]
    if retrying_failed_close:
        profile.is_on_hold = False
        profile.hold_reason = ""
        profile.held_at = None
        profile.held_by_admin_id = None
        profile_update_fields.extend(
            ["is_on_hold", "hold_reason", "held_at", "held_by_admin_id"]
        )
    profile.save(update_fields=profile_update_fields)
    _loan_status_event(
        loan=loan,
        actor=command.actor,
        event_type="funding_closed",
        previous_status=previous_loan_status,
        new_status=str(loan.status),
        note=close_reason,
        metadata={**metadata, "originator_funding_round_close_id": str(close.id)},
    )
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.FUNDING_ROUND_CLOSED,
        originator=profile.originator,
        loan_id=loan.id,
        note=close_reason,
        metadata={**metadata, "funding_round_close_id": str(close.id)},
    )
    admin_ops = import_module("backend.apps.admin_ops.services")
    operations_actor = _operations_admin_actor(command.actor)
    admin_ops.ensure_originator_subscription_activation_task(
        admin_ops.EnsureOriginatorActivationTaskCommand(
            requested_by=operations_actor,
            loan_id=str(loan.id),
            loan_title=str(loan.title),
            originator_name=str(profile.originator.public_name),
            currency=str(loan.currency_id),
            subscribed_principal_minor=subscribed_principal,
            funding_round_close_id=str(close.id),
            entitlement_start_date=cast(date, profile.entitlement_start_date),
        )
    )
    if retrying_failed_close:
        admin_ops.resolve_loan_funding_close_failure_task(
            actor=operations_actor,
            loan_id=str(loan.id),
            completion_note=f"Originator funding round closed successfully as {close.id}.",
        )
    _enqueue_operations_email(
        topic="email.originator_subscription_awaiting_activation",
        subject=f"BANXUM originator subscription ready for activation: {loan.title}",
        body_text=(
            f"The funding round for {loan.title} closed with "
            f"{format_amount_minor(subscribed_principal, str(loan.currency_id))} subscribed. "
            "Verify and import the boundary installment before activating investor claims."
        ),
        template_key="originator_subscription.awaiting_activation.v1",
        idempotency_key=f"originator-round-close-alert:{close.id}",
        metadata={**metadata, "funding_round_close_id": str(close.id)},
    )
    return close


def _payment_row_evidence(row: Any) -> tuple[Any, ...]:
    return (
        str(row.reference),
        row.value_date,
        str(row.payment_type),
        int(row.principal_minor),
        int(row.interest_minor),
        int(row.penalty_minor),
        int(row.fee_minor),
        int(row.total_minor),
        int(row.resulting_principal_minor),
    )


def _component_pool_minor(
    *,
    component_minor: int,
    investor_principal_minor: int,
    total_principal_minor: int,
    participation_bps: int,
) -> int:
    if component_minor <= 0 or investor_principal_minor <= 0 or participation_bps <= 0:
        return 0
    return int(
        (
            Decimal(component_minor)
            * Decimal(investor_principal_minor)
            * Decimal(participation_bps)
            / Decimal(total_principal_minor)
            / Decimal(10_000)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def _subscription_entitlement_flows(
    *,
    profile: OriginatorLoanProfile,
    order_principals: list[int],
    retained_principal_minor: int,
    schedule_rows: list[OriginatorLoanScheduleRow],
) -> list[list[dict[str, Any]]]:
    currency = str(profile.loan.currency_id)
    holding_balances = list(order_principals)
    originator_balance = retained_principal_minor
    flows: list[list[dict[str, Any]]] = [[] for _item in order_principals]
    for row in schedule_rows:
        total_before = sum(holding_balances) + originator_balance
        investor_before = sum(holding_balances)
        if total_before != int(row.opening_principal_minor):
            raise OriginatorClaimsValidationError(
                "Post-boundary schedule opening principal does not match claim ownership."
            )
        interest_pool = _component_pool_minor(
            component_minor=int(row.interest_minor),
            investor_principal_minor=investor_before,
            total_principal_minor=total_before,
            participation_bps=int(profile.investor_interest_participation_bps),
        )
        penalty_pool = _component_pool_minor(
            component_minor=int(row.penalty_minor),
            investor_principal_minor=investor_before,
            total_principal_minor=total_before,
            participation_bps=int(profile.investor_penalty_participation_bps),
        )
        interest_parts = (
            allocate_by_weights(Money(interest_pool, currency), holding_balances)
            if interest_pool and investor_before
            else [Money(0, currency) for _value in holding_balances]
        )
        penalty_parts = (
            allocate_by_weights(Money(penalty_pool, currency), holding_balances)
            if penalty_pool and investor_before
            else [Money(0, currency) for _value in holding_balances]
        )
        principal_parts, _retained_after = _allocate_principal_with_retention(
            holding_principals=holding_balances,
            originator_principal_minor=originator_balance,
            skin_in_the_game_bps=int(profile.loan.skin_in_the_game_bps),
            principal_minor=int(row.principal_minor),
            currency=currency,
        )
        for index, principal_part in enumerate(principal_parts[:-1]):
            principal_minor = principal_part.amount_minor
            interest_minor = interest_parts[index].amount_minor
            penalty_minor = penalty_parts[index].amount_minor
            flows[index].append(
                {
                    "installment_number": int(row.installment_number),
                    "accrual_start_date": row.accrual_start_date.isoformat(),
                    "due_date": row.due_date.isoformat(),
                    "principal_minor": principal_minor,
                    "interest_minor": interest_minor,
                    "penalty_minor": penalty_minor,
                    "total_minor": principal_minor + interest_minor + penalty_minor,
                }
            )
            holding_balances[index] -= principal_minor
        originator_balance -= principal_parts[-1].amount_minor
    if any(holding_balances) or originator_balance:
        raise OriginatorClaimsValidationError(
            "Post-boundary entitlement schedule does not amortize ownership to zero."
        )
    return flows


def _existing_subscription_activation(
    *,
    idempotency_key: str,
    fingerprint: str,
) -> OriginatorSubscriptionActivation | None:
    existing = OriginatorSubscriptionActivation.objects.filter(
        idempotency_key=idempotency_key
    ).first()
    if existing is None:
        return None
    if existing.request_fingerprint != fingerprint:
        raise OriginatorClaimsValidationError(
            "Idempotency key was already used for a different subscription activation."
        )
    return cast(OriginatorSubscriptionActivation, existing)


@transaction.atomic
def activate_originator_subscription(
    command: ActivateOriginatorSubscriptionCommand,
) -> OriginatorSubscriptionActivation:
    _require_admin(command.actor)
    idempotency_key = _required(command.idempotency_key, "Idempotency key")
    if len(idempotency_key) > 160:
        raise OriginatorClaimsValidationError("Idempotency key cannot exceed 160 characters.")
    reference = _required(command.boundary_payment_reference, "Boundary payment reference")
    notes = _required(command.notes, "Activation notes")
    fingerprint = _request_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "source_sha256": hashlib.sha256(command.csv_content.encode("utf-8")).hexdigest(),
            "source_filename": command.source_filename.strip(),
            "as_of_date": command.as_of_date.isoformat(),
            "boundary_payment_reference": reference,
            "boundary_payment_date": command.boundary_payment_date.isoformat(),
            "notes": notes,
            "idempotency_key": idempotency_key,
        }
    )
    existing = _existing_subscription_activation(
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if existing is not None:
        return existing

    loan_model = apps.get_model("loans", "Loan")
    loan = loan_model.objects.select_for_update().filter(id=command.loan_id).first()
    if loan is None:
        raise OriginatorClaimsValidationError("Originator claim loan does not exist.")
    profile = _locked_profile_for_loan(
        command.loan_id,
        "originator",
        "current_import",
        "loan__currency",
    )
    existing = _existing_subscription_activation(
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if existing is not None:
        return existing
    if not _is_par_subscription(profile):
        raise OriginatorClaimsValidationError(
            "Legacy originator opportunities do not use subscription activation."
        )
    if profile.opportunity_status != OriginatorOpportunityStatus.AWAITING_ACTIVATION:
        raise OriginatorClaimsValidationError("Originator subscription is not awaiting activation.")
    if profile.is_on_hold:
        raise OriginatorClaimsValidationError(
            "A held originator subscription cannot be activated; cancel it or resolve the "
            "hold first."
        )
    if loan.status != "funded":
        raise OriginatorClaimsValidationError("Originator subscription loan is not funded.")
    round_close = (
        OriginatorFundingRoundClose.objects.select_for_update().filter(loan_profile=profile).first()
    )
    if round_close is None:
        raise OriginatorClaimsValidationError("Funding-round close evidence is unavailable.")
    if OriginatorSubscriptionCancellation.objects.filter(loan_profile=profile).exists():
        raise OriginatorClaimsValidationError("Cancelled subscriptions cannot be activated.")
    if command.boundary_payment_date != cast(date, profile.entitlement_start_date):
        raise OriginatorClaimsValidationError(
            "Boundary payment must be received on the declared installment due date. "
            "A delayed or changed payment requires subscription cancellation and refund."
        )
    if command.boundary_payment_date > command.as_of_date:
        raise OriginatorClaimsValidationError("Boundary payment cannot be after the import date.")
    current_import = profile.current_import
    if current_import is None:
        raise OriginatorClaimsValidationError("Current schedule evidence is unavailable.")
    next_entitled_installment = (
        current_import.schedule_rows.filter(due_date__gt=cast(date, profile.entitlement_start_date))
        .order_by("due_date", "installment_number", "id")
        .first()
    )
    if (
        next_entitled_installment is not None
        and command.boundary_payment_date >= next_entitled_installment.due_date
    ):
        raise OriginatorClaimsValidationError(
            "The boundary payment arrived on or after the next installment due date. "
            "Cancel and refund the subscription rather than granting retroactive entitlement."
        )
    try:
        parsed = parse_originator_import_csv(
            csv_content=command.csv_content,
            original_principal_minor=int(loan.original_principal_minor),
            as_of_date=command.as_of_date,
            repayment_type=str(loan.repayment_type),
            interest_only_months=int(loan.interest_only_months),
        )
    except OriginatorImportValidationError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc
    previous_payments = {_payment_row_evidence(row) for row in current_import.payment_rows.all()}
    imported_payments = {_payment_row_evidence(row) for row in parsed.payment_rows}
    if not previous_payments.issubset(imported_payments):
        raise OriginatorClaimsValidationError(
            "Activation import must preserve every previously imported payment unchanged."
        )
    new_payments = [
        row for row in parsed.payment_rows if _payment_row_evidence(row) not in previous_payments
    ]
    if len(new_payments) != 1:
        raise OriginatorClaimsValidationError(
            "Activation import must add exactly one boundary installment payment."
        )
    boundary_payment = new_payments[0]
    if boundary_payment.reference != reference:
        raise OriginatorClaimsValidationError(
            "Boundary payment reference does not match the new imported payment."
        )
    if boundary_payment.value_date != command.boundary_payment_date:
        raise OriginatorClaimsValidationError(
            "Boundary payment date does not match the new imported payment."
        )
    if profile.activation_outstanding_principal_minor is None:
        raise OriginatorClaimsValidationError(
            "Originator subscription starting principal is unavailable."
        )
    expected_starting_principal = int(profile.activation_outstanding_principal_minor)
    if parsed.current_outstanding_principal_minor != expected_starting_principal:
        raise OriginatorClaimsValidationError(
            "Boundary payment must leave the declared activation outstanding principal."
        )
    if boundary_payment.resulting_principal_minor != expected_starting_principal:
        raise OriginatorClaimsValidationError(
            "Boundary payment resulting principal does not match activation principal."
        )
    if (
        int(current_import.current_outstanding_principal_minor)
        - int(boundary_payment.principal_minor)
        != expected_starting_principal
    ):
        raise OriginatorClaimsValidationError(
            "Boundary payment principal does not reconcile from the previous import."
        )

    allocated_orders, pending_orders = _subscription_orders_for_update(str(loan.id))
    if pending_orders:
        raise OriginatorClaimsValidationError(
            "Pending orders must be closed before activating the subscription."
        )
    assigned_principal = sum(int(order.allocated_amount_minor) for order in allocated_orders)
    if assigned_principal != int(round_close.subscribed_principal_minor):
        raise OriginatorClaimsValidationError(
            "Allocated subscriptions do not match funding-round close evidence."
        )
    if assigned_principal != int(loan.committed_principal_minor):
        raise OriginatorClaimsValidationError(
            "Allocated subscriptions do not match loan committed principal."
        )
    retained_principal = expected_starting_principal - assigned_principal
    if retained_principal < originator_retained_principal_minor(profile):
        raise OriginatorClaimsValidationError(
            "Activation would breach the Loan Originator skin-in-the-game floor."
        )

    revision = int(profile.schedule_revision) + 1
    loan_import = _persist_import_revision(
        actor=command.actor,
        loan=loan,
        revision=revision,
        parsed=parsed,
        as_of_date=command.as_of_date,
        source_filename=command.source_filename,
        csv_content=command.csv_content,
        validation_summary={
            "action": "subscription_activation",
            "boundary_payment_reference": reference,
            "boundary_payment_date": command.boundary_payment_date.isoformat(),
            "starting_outstanding_principal_minor": expected_starting_principal,
        },
    )
    schedule_rows = list(
        loan_import.schedule_rows.filter(
            due_date__gt=cast(date, profile.entitlement_start_date)
        ).order_by("installment_number", "id")
    )
    if sum(int(row.principal_minor) for row in schedule_rows) != expected_starting_principal:
        raise OriginatorClaimsValidationError(
            "Post-boundary schedule principal does not match activation principal."
        )
    order_principals = [int(order.allocated_amount_minor) for order in allocated_orders]
    entitlement_flows = _subscription_entitlement_flows(
        profile=profile,
        order_principals=order_principals,
        retained_principal_minor=retained_principal,
        schedule_rows=schedule_rows,
    )
    activated_at = now_utc()
    entitlement_start_at = datetime.combine(
        command.boundary_payment_date,
        time.min,
        tzinfo=business_timezone(),
    ).astimezone(UTC)
    activation_id = _operation_uuid("originator-subscription-activation", idempotency_key)
    ledger = import_module("backend.apps.ledger.services")
    try:
        ledger_result = ledger.activate_originator_subscription_ledger(
            ledger.ActivateOriginatorSubscriptionLedgerCommand(
                actor=command.actor,
                activation_id=str(activation_id),
                loan_id=str(loan.id),
                originator_id=str(profile.originator_id),
                currency=str(loan.currency_id),
                assigned_principal_minor=assigned_principal,
                source_type="originator_subscription_activation",
                source_id=str(activation_id),
                idempotency_key=f"originator-activation-ledger:{idempotency_key}",
                as_of=activated_at,
                metadata={"funding_round_close_id": str(round_close.id)},
            )
        )
    except ledger.LedgerError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc

    holdings = import_module("backend.apps.holdings.services")
    purchases: list[OriginatorClaimPurchase] = []
    holding_ids: list[str] = []
    rows_by_number = {int(row.installment_number): row for row in schedule_rows}
    for order, flows in zip(allocated_orders, entitlement_flows, strict=True):
        if order.document_acceptance_id is None:
            raise OriginatorClaimsValidationError(
                "Every activated subscription must retain its document acceptance evidence."
            )
        quote_id = _operation_uuid("originator-subscription-quote", str(order.id))
        purchase_id = _operation_uuid("originator-subscription-purchase", str(order.id))
        share_ppm = min(
            1_000_000,
            max(
                1,
                int(
                    (
                        Decimal(order.allocated_amount_minor)
                        * Decimal(1_000_000)
                        / Decimal(expected_starting_principal)
                    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                ),
            ),
        )
        quote = OriginatorClaimQuote.objects.create(
            id=quote_id,
            loan_profile=profile,
            investor_user_id=order.investor_user_id,
            currency=loan.currency,
            requested_cash_minor=order.allocated_amount_minor,
            executable_cash_minor=order.allocated_amount_minor,
            assigned_principal_minor=order.allocated_amount_minor,
            outstanding_principal_at_pricing_minor=expected_starting_principal,
            share_ppm=share_ppm,
            target_yield_bps=profile.target_yield_bps,
            premium_discount_minor=0,
            platform_fee_minor=0,
            originator_payable_minor=order.allocated_amount_minor,
            rounding_remainder_minor=0,
            schedule_revision=revision,
            entitlement_start_at=entitlement_start_at,
            expires_at=activated_at,
            cash_flows=flows,
            calculation_fingerprint=_request_fingerprint(
                {
                    "order_id": str(order.id),
                    "activation_id": str(activation_id),
                    "cash_flows": flows,
                }
            ),
        )
        try:
            holding = holdings.create_originator_claim_holding(
                holdings.CreateOriginatorClaimHoldingCommand(
                    actor=command.actor,
                    investor_user_id=str(order.investor_user_id),
                    loan_id=str(loan.id),
                    purchase_id=str(purchase_id),
                    principal_minor=order.allocated_amount_minor,
                    current_loan_principal_minor=expected_starting_principal,
                    currency=str(loan.currency_id),
                    assignment_effective_at=entitlement_start_at,
                    idempotency_key=f"originator-activation-holding:{order.id}",
                    loan_share_ppm=share_ppm,
                    metadata={
                        "originator_subscription_activation_id": str(activation_id),
                        "primary_order_id": str(order.id),
                        "distribution_model": profile.distribution_model,
                    },
                )
            )
        except holdings.HoldingsError as exc:
            raise OriginatorClaimsValidationError(str(exc)) from exc
        purchase = OriginatorClaimPurchase.objects.create(
            id=purchase_id,
            loan_profile=profile,
            quote=quote,
            investor_user_id=order.investor_user_id,
            currency=loan.currency,
            cash_consideration_minor=order.allocated_amount_minor,
            assigned_principal_minor=order.allocated_amount_minor,
            outstanding_principal_at_pricing_minor=expected_starting_principal,
            share_ppm=share_ppm,
            target_yield_bps=profile.target_yield_bps,
            premium_discount_minor=0,
            platform_fee_minor=0,
            originator_payable_minor=order.allocated_amount_minor,
            schedule_revision=revision,
            entitlement_start_at=entitlement_start_at,
            document_acceptance=order.document_acceptance,
            journal_entry=ledger_result.journal_entry,
            holding=holding,
            lot_allocations=list(cast(list[dict[str, Any]], order.lot_allocations)),
            purchased_at=activated_at,
            idempotency_key=f"originator-activation-purchase:{order.id}",
            request_fingerprint=_request_fingerprint(
                {
                    "order_id": str(order.id),
                    "activation_id": str(activation_id),
                    "holding_id": str(holding.id),
                }
            ),
        )
        OriginatorClaimEntitlement.objects.bulk_create(
            [
                OriginatorClaimEntitlement(
                    purchase=purchase,
                    schedule_row=rows_by_number[int(flow["installment_number"])],
                    accrual_start_date=date.fromisoformat(str(flow["accrual_start_date"])),
                    due_date=date.fromisoformat(str(flow["due_date"])),
                    expected_principal_minor=int(flow["principal_minor"]),
                    expected_interest_minor=int(flow["interest_minor"]),
                    expected_penalty_minor=int(flow["penalty_minor"]),
                    expected_total_minor=int(flow["total_minor"]),
                )
                for flow in flows
            ]
        )
        previous_status = str(order.status)
        order.status = "closed_invested"
        order.closed_at = activated_at
        order.closed_by_admin_id = command.actor.pk
        order.admin_notes = notes
        order.metadata = {
            **cast(dict[str, Any], order.metadata),
            "originator_subscription_activation_id": str(activation_id),
            "originator_claim_purchase_id": str(purchase.id),
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
        _primary_order_event(
            order=order,
            actor=command.actor,
            event_type="closed_invested",
            previous_status=previous_status,
            new_status=str(order.status),
            note=notes,
            metadata={
                "originator_subscription_activation_id": str(activation_id),
                "purchase_id": str(purchase.id),
                "holding_id": str(holding.id),
            },
        )
        purchases.append(purchase)
        holding_ids.append(str(holding.id))

    profile.current_import = loan_import
    profile.schedule_revision = revision
    profile.current_outstanding_principal_minor = expected_starting_principal
    profile.unsold_principal_minor = retained_principal
    profile.opportunity_status = OriginatorOpportunityStatus.ACTIVE
    profile.save(
        update_fields=[
            "current_import",
            "schedule_revision",
            "current_outstanding_principal_minor",
            "unsold_principal_minor",
            "opportunity_status",
            "updated_at",
        ]
    )
    previous_loan_status = str(loan.status)
    loan.status = "active"
    loan.schedule_version = revision
    loan.total_scheduled_principal_minor = sum(int(row.principal_minor) for row in schedule_rows)
    loan.total_scheduled_interest_minor = sum(int(row.interest_minor) for row in schedule_rows)
    loan.updated_by_admin_id = command.actor.pk
    loan.save(
        update_fields=[
            "status",
            "schedule_version",
            "total_scheduled_principal_minor",
            "total_scheduled_interest_minor",
            "updated_by_admin_id",
            "updated_at",
        ]
    )
    activation_metadata = {
        "loan_id": str(loan.id),
        "funding_round_close_id": str(round_close.id),
        "boundary_payment_reference": reference,
        "boundary_payment_date": command.boundary_payment_date.isoformat(),
        "starting_outstanding_principal_minor": expected_starting_principal,
        "assigned_principal_minor": assigned_principal,
        "originator_retained_principal_minor": retained_principal,
        "purchase_ids": [str(purchase.id) for purchase in purchases],
        "holding_ids": holding_ids,
        "loan_import_id": str(loan_import.id),
        "activation_journal_entry_id": str(ledger_result.journal_entry.id),
    }
    try:
        with transaction.atomic():
            activation = cast(
                OriginatorSubscriptionActivation,
                OriginatorSubscriptionActivation.objects.create(
                    id=activation_id,
                    loan_profile=profile,
                    funding_round_close=round_close,
                    boundary_payment_reference=reference,
                    boundary_payment_date=command.boundary_payment_date,
                    starting_outstanding_principal_minor=expected_starting_principal,
                    assigned_principal_minor=assigned_principal,
                    originator_retained_principal_minor=retained_principal,
                    activation_journal_entry=ledger_result.journal_entry,
                    activated_by_admin_id=command.actor.pk,
                    activated_at=activated_at,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    metadata=activation_metadata,
                ),
            )
    except IntegrityError:
        existing_after_race = _existing_subscription_activation(
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    _loan_status_event(
        loan=loan,
        actor=command.actor,
        event_type="originator_subscription_activated",
        previous_status=previous_loan_status,
        new_status=str(loan.status),
        note=notes,
        metadata=activation_metadata,
    )
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.SUBSCRIPTION_ACTIVATED,
        originator=profile.originator,
        loan_id=loan.id,
        note=notes,
        metadata={**activation_metadata, "activation_id": str(activation.id)},
    )
    import_module(
        "backend.apps.admin_ops.services"
    ).resolve_originator_subscription_activation_task(
        actor=command.actor,
        loan_id=str(loan.id),
        completion_note=f"Subscription activated as {activation.id}.",
    )
    for order in allocated_orders:
        _enqueue_investor_email(
            investor_user_id=str(order.investor_user_id),
            topic="email.originator_subscription_activated",
            subject=f"BANXUM investment activated: {loan.title}",
            body_text=(
                "Your "
                f"{format_amount_minor(int(order.allocated_amount_minor), str(loan.currency_id))} "
                f"subscription in {loan.title} is now active. Your entitlement begins after "
                "the boundary installment dated "
                f"{cast(date, profile.entitlement_start_date).isoformat()}."
            ),
            template_key="originator_subscription.activated.v1",
            idempotency_key=f"originator-activation-email:{activation.id}:{order.investor_user_id}",
            metadata={
                "loan_id": str(loan.id),
                "activation_id": str(activation.id),
                "order_id": str(order.id),
            },
        )
    return activation


def _existing_subscription_cancellation(
    *,
    idempotency_key: str,
    fingerprint: str,
) -> OriginatorSubscriptionCancellation | None:
    existing = OriginatorSubscriptionCancellation.objects.filter(
        idempotency_key=idempotency_key
    ).first()
    if existing is None:
        return None
    if existing.request_fingerprint != fingerprint:
        raise OriginatorClaimsValidationError(
            "Idempotency key was already used for a different subscription cancellation."
        )
    return cast(OriginatorSubscriptionCancellation, existing)


@transaction.atomic
def cancel_originator_subscription(
    command: CancelOriginatorSubscriptionCommand,
) -> OriginatorSubscriptionCancellation:
    _require_admin(command.actor)
    idempotency_key = _required(command.idempotency_key, "Idempotency key")
    if len(idempotency_key) > 160:
        raise OriginatorClaimsValidationError("Idempotency key cannot exceed 160 characters.")
    reason = _required(command.reason, "Cancellation reason")
    investor_message = _required(command.investor_message, "Investor message")
    fingerprint = _request_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "reason": reason,
            "investor_message": investor_message,
            "idempotency_key": idempotency_key,
        }
    )
    existing = _existing_subscription_cancellation(
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if existing is not None:
        return existing
    loan_model = apps.get_model("loans", "Loan")
    loan = loan_model.objects.select_for_update().filter(id=command.loan_id).first()
    if loan is None:
        raise OriginatorClaimsValidationError("Originator claim loan does not exist.")
    profile = _locked_profile_for_loan(command.loan_id, "originator")
    existing = _existing_subscription_cancellation(
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
    )
    if existing is not None:
        return existing
    if not _is_par_subscription(profile):
        raise OriginatorClaimsValidationError(
            "Legacy originator opportunities do not use subscription cancellation."
        )
    if profile.opportunity_status not in {
        OriginatorOpportunityStatus.OPEN,
        OriginatorOpportunityStatus.AWAITING_ACTIVATION,
    } or loan.status not in {"published", "funded", "funding_close_failed"}:
        raise OriginatorClaimsValidationError("Originator subscription cannot be cancelled now.")
    if OriginatorSubscriptionActivation.objects.filter(loan_profile=profile).exists():
        raise OriginatorClaimsValidationError("Activated subscriptions cannot be cancelled.")
    allocated_orders, pending_orders = _subscription_orders_for_update(str(loan.id))
    marketplace = import_module("backend.apps.marketplace_primary.services")
    released_principal = 0
    released_ids: list[str] = []
    investor_ids: set[str] = set()
    for order in allocated_orders:
        investor_ids.add(str(order.investor_user_id))
        try:
            released = marketplace.release_primary_order_balance(
                marketplace.ReleasePrimaryInvestmentOrderCommand(
                    actor=command.actor,
                    order_id=str(order.id),
                    reason=reason,
                    idempotency_key=f"originator-subscription-cancel:{idempotency_key}:{order.id}",
                )
            )
        except marketplace.MarketplacePrimaryError as exc:
            raise OriginatorClaimsValidationError(str(exc)) from exc
        released_principal += int(released.allocated_amount_minor)
        released_ids.append(str(released.id))
    closed_pending_ids: list[str] = []
    cancelled_at = now_utc()
    for order in pending_orders:
        investor_ids.add(str(order.investor_user_id))
        previous_status = str(order.status)
        order.status = "closed_not_invested"
        order.closed_at = cancelled_at
        order.closed_by_admin_id = command.actor.pk
        order.admin_notes = reason
        order.metadata = {
            **cast(dict[str, Any], order.metadata),
            "closed_reason": "Originator subscription cancelled before activation.",
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
        closed_pending_ids.append(str(order.id))
        _primary_order_event(
            order=order,
            actor=command.actor,
            event_type="closed_not_invested",
            previous_status=previous_status,
            new_status=str(order.status),
            note=reason,
            metadata={"reason": "originator_subscription_cancelled"},
        )
    loan.refresh_from_db()
    if int(loan.committed_principal_minor) != 0:
        raise OriginatorClaimsValidationError(
            "Originator subscription committed principal must be zero after cancellation."
        )
    cancellation_metadata = {
        "loan_id": str(loan.id),
        "released_principal_minor": released_principal,
        "released_order_ids": released_ids,
        "closed_not_invested_order_ids": closed_pending_ids,
        "investor_message": investor_message,
        "previous_hold": {
            "is_on_hold": bool(profile.is_on_hold),
            "reason": str(profile.hold_reason),
            "held_at": profile.held_at.isoformat() if profile.held_at else None,
            "held_by_admin_id": (
                str(profile.held_by_admin_id) if profile.held_by_admin_id else None
            ),
        },
    }
    try:
        with transaction.atomic():
            cancellation = cast(
                OriginatorSubscriptionCancellation,
                OriginatorSubscriptionCancellation.objects.create(
                    loan_profile=profile,
                    released_principal_minor=released_principal,
                    released_order_count=len(released_ids),
                    closed_not_invested_order_count=len(closed_pending_ids),
                    reason=reason,
                    cancelled_by_admin_id=command.actor.pk,
                    cancelled_at=cancelled_at,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    metadata=cancellation_metadata,
                ),
            )
    except IntegrityError:
        existing_after_race = _existing_subscription_cancellation(
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    previous_loan_status = str(loan.status)
    loan.status = "cancelled"
    loan.updated_by_admin_id = command.actor.pk
    loan.save(update_fields=["status", "updated_by_admin_id", "updated_at"])
    profile.opportunity_status = OriginatorOpportunityStatus.CANCELLED
    profile.closed_at = cancelled_at
    profile.close_reason = reason[:128]
    profile.is_on_hold = False
    profile.hold_reason = ""
    profile.held_at = None
    profile.held_by_admin_id = None
    profile.save(
        update_fields=[
            "opportunity_status",
            "closed_at",
            "close_reason",
            "is_on_hold",
            "hold_reason",
            "held_at",
            "held_by_admin_id",
            "updated_at",
        ]
    )
    _loan_status_event(
        loan=loan,
        actor=command.actor,
        event_type="funding_cancelled",
        previous_status=previous_loan_status,
        new_status=str(loan.status),
        note=reason,
        metadata={**cancellation_metadata, "cancellation_id": str(cancellation.id)},
    )
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.SUBSCRIPTION_CANCELLED,
        originator=profile.originator,
        loan_id=loan.id,
        note=reason,
        metadata={**cancellation_metadata, "cancellation_id": str(cancellation.id)},
    )
    admin_ops = import_module("backend.apps.admin_ops.services")
    admin_ops.resolve_originator_subscription_activation_task(
        actor=command.actor,
        loan_id=str(loan.id),
        completion_note=f"Subscription cancelled and reservations released as {cancellation.id}.",
    )
    admin_ops.resolve_loan_funding_close_failure_task(
        actor=command.actor,
        loan_id=str(loan.id),
        completion_note=(
            f"Failed funding round cancelled and reservations released as {cancellation.id}."
        ),
    )
    for investor_id in investor_ids:
        _enqueue_investor_email(
            investor_user_id=investor_id,
            topic="email.originator_subscription_cancelled",
            subject=f"BANXUM subscription cancelled: {loan.title}",
            body_text=investor_message,
            template_key="originator_subscription.cancelled.v1",
            idempotency_key=f"originator-cancel-email:{cancellation.id}:{investor_id}",
            metadata={"loan_id": str(loan.id), "cancellation_id": str(cancellation.id)},
        )
    return cancellation


@transaction.atomic
def place_originator_loan_on_hold(command: HoldOriginatorLoanCommand) -> OriginatorLoanProfile:
    _require_admin(command.actor)
    reason = _required(command.reason, "Hold reason")
    profile = _locked_profile_for_loan(
        command.loan_id,
        "loan",
        "originator",
    )
    if profile.is_on_hold:
        return profile
    now = now_utc()
    profile.is_on_hold = True
    profile.hold_reason = reason
    profile.held_at = now
    profile.held_by_admin_id = command.actor.pk
    update_fields = [
        "is_on_hold",
        "hold_reason",
        "held_at",
        "held_by_admin_id",
        "updated_at",
    ]
    is_subscription = _is_par_subscription(profile)
    if profile.opportunity_status == OriginatorOpportunityStatus.OPEN and not is_subscription:
        profile.opportunity_status = OriginatorOpportunityStatus.CLOSED
        profile.closed_at = now
        profile.close_reason = "administrative_hold"
        update_fields.extend(["opportunity_status", "closed_at", "close_reason"])
    profile.save(update_fields=update_fields)
    _record_event(
        actor=command.actor,
        event_type=(
            OriginatorClaimEventType.OPPORTUNITY_HELD
            if is_subscription
            else OriginatorClaimEventType.OPPORTUNITY_CLOSED
        ),
        originator=profile.originator,
        loan_id=profile.loan_id,
        note=reason,
        metadata={"close_reason": "administrative_hold"},
    )
    return profile


def list_loan_originators(*, actor: Model, query: str = "") -> Any:
    _require_admin(actor)
    queryset = LoanOriginator.objects.all()
    cleaned = query.strip()
    if cleaned:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(legal_name__icontains=cleaned)
            | Q(public_name__icontains=cleaned)
            | Q(registration_number__icontains=cleaned)
        )
    return queryset


def _public_borrower_snapshot(profile: OriginatorLoanProfile) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "legal_name": profile.borrower_display_name,
        "display_name": profile.borrower_display_name,
    }
    optional = {
        "year_founded": profile.borrower_year_founded,
        "entity_type": profile.borrower_entity_type,
        "country": profile.borrower_country,
        "industry_activity": profile.industry_activity,
        "financials_currency": profile.financials_currency,
        "assets_minor": profile.assets_minor,
        "liabilities_minor": profile.liabilities_minor,
        "revenue_last_year_minor": profile.revenue_last_year_minor,
        "profit_last_year_minor": profile.profit_last_year_minor,
    }
    for key, value in optional.items():
        if value not in {"", None}:
            payload[key] = value
    if profile.business_classification_public and profile.business_classification:
        payload["business_classification"] = profile.business_classification
    if profile.registered_address_public and profile.registered_address:
        payload["registered_address"] = profile.registered_address
    if profile.contact_info_public and profile.contact_info:
        payload["contact_info"] = profile.contact_info
    return payload


def _originator_schedule_payload(profile: OriginatorLoanProfile) -> list[dict[str, Any]]:
    loan_import = profile.current_import
    if loan_import is None:
        return []
    return [
        {
            "installment_number": int(row.installment_number),
            "accrual_start_date": row.accrual_start_date,
            "due_date": row.due_date,
            "opening_principal_minor": int(row.opening_principal_minor),
            "principal_minor": int(row.principal_minor),
            "interest_minor": int(row.interest_minor),
            "penalty_minor": int(row.penalty_minor),
            "fee_minor": int(row.fee_minor),
            "total_minor": int(row.total_minor),
            "outstanding_after_minor": int(row.closing_principal_minor),
        }
        for row in loan_import.schedule_rows.order_by("installment_number", "id")
    ]


def _originator_payment_history_payload(
    profile: OriginatorLoanProfile,
) -> list[dict[str, Any]]:
    loan_import = profile.current_import
    if loan_import is None:
        return []
    return [
        {
            "reference": row.reference,
            "value_date": row.value_date,
            "payment_type": row.payment_type,
            "principal_minor": int(row.principal_minor),
            "interest_minor": int(row.interest_minor),
            "penalty_minor": int(row.penalty_minor),
            "fee_minor": int(row.fee_minor),
            "total_minor": int(row.total_minor),
            "resulting_principal_minor": int(row.resulting_principal_minor),
        }
        for row in loan_import.payment_rows.order_by("value_date", "reference", "id")
    ]


def _originator_days_past_due(
    profile: OriginatorLoanProfile,
    *,
    as_of_date: date,
) -> int:
    loan_import = profile.current_import
    if loan_import is None:
        return 0
    first_outstanding = (
        loan_import.schedule_rows.filter(due_date__gt=loan_import.as_of_date)
        .order_by("due_date", "installment_number", "id")
        .first()
    )
    if first_outstanding is None:
        return 0
    return max(0, (as_of_date - first_outstanding.due_date).days)


def originator_portfolio_schedule_payload(
    profile: OriginatorLoanProfile,
    *,
    as_of_date: date,
) -> list[dict[str, Any]]:
    """Return the imported contractual schedule plus immutable payment evidence."""
    loan_import = profile.current_import
    if loan_import is None:
        return []
    rows: list[dict[str, Any]] = []
    for payment in loan_import.payment_rows.order_by("value_date", "reference", "id"):
        rows.append(
            {
                "id": str(payment.id),
                "schedule_version": int(profile.schedule_revision),
                "installment_number": 0,
                "due_date": payment.value_date,
                "principal_minor": int(payment.principal_minor),
                "interest_minor": int(payment.interest_minor),
                "penalty_minor": int(payment.penalty_minor),
                "fee_minor": int(payment.fee_minor),
                "total_minor": int(payment.total_minor),
                "paid_principal_minor": int(payment.principal_minor),
                "paid_interest_minor": int(payment.interest_minor),
                "outstanding_principal_minor": 0,
                "outstanding_interest_minor": 0,
                "outstanding_total_minor": 0,
                "is_paid": True,
                "days_past_due": 0,
                "status": (
                    "paid_in_advance" if payment.payment_type == "repayment_in_advance" else "paid"
                ),
                "row_type": "repayment_event",
                "label": (
                    "Repayment in advance"
                    if payment.payment_type == "repayment_in_advance"
                    else "Recorded borrower payment"
                ),
                "payment_date": payment.value_date,
                "payment_reference": payment.reference,
            }
        )
    for schedule_row in loan_import.schedule_rows.order_by("due_date", "installment_number", "id"):
        # The import's as-of date, not the viewer's current date, separates
        # immutable historical rows from the still-outstanding schedule. This
        # preserves overdue rows when the portfolio is viewed after their due date.
        is_outstanding = schedule_row.due_date > loan_import.as_of_date
        days_past_due = max(0, (as_of_date - schedule_row.due_date).days) if is_outstanding else 0
        rows.append(
            {
                "id": str(schedule_row.id),
                "schedule_version": int(profile.schedule_revision),
                "installment_number": int(schedule_row.installment_number),
                "due_date": schedule_row.due_date,
                "principal_minor": int(schedule_row.principal_minor),
                "interest_minor": int(schedule_row.interest_minor),
                "penalty_minor": int(schedule_row.penalty_minor),
                "fee_minor": int(schedule_row.fee_minor),
                "total_minor": int(schedule_row.total_minor),
                "paid_principal_minor": 0,
                "paid_interest_minor": 0,
                "outstanding_principal_minor": (
                    int(schedule_row.principal_minor) if is_outstanding else 0
                ),
                "outstanding_interest_minor": (
                    int(schedule_row.interest_minor) if is_outstanding else 0
                ),
                "outstanding_total_minor": (int(schedule_row.total_minor) if is_outstanding else 0),
                "is_paid": not is_outstanding,
                "days_past_due": days_past_due,
                "status": (
                    "due"
                    if schedule_row.due_date == as_of_date
                    else (
                        "overdue"
                        if is_outstanding and schedule_row.due_date < as_of_date
                        else ("upcoming" if is_outstanding else "historical")
                    )
                ),
                "row_type": "originator_schedule",
                "label": f"Installment {schedule_row.installment_number}",
                "payment_date": None,
                "accrual_start_date": schedule_row.accrual_start_date,
                "opening_principal_minor": int(schedule_row.opening_principal_minor),
                "closing_principal_minor": int(schedule_row.closing_principal_minor),
            }
        )
    rows.sort(
        key=lambda row: (
            row["payment_date"] or row["due_date"],
            0 if row["row_type"] == "repayment_event" else 1,
            row["installment_number"],
            row["id"],
        )
    )
    return rows


def get_originator_holding_schedule_payloads(
    *,
    holdings: list[Model],
    as_of_date: date,
) -> dict[str, list[dict[str, Any]]]:
    """Project exact current investor cash flows from the latest LO schedule."""
    target_ids = {str(cast(Any, holding).pk) for holding in holdings}
    payloads: dict[str, list[dict[str, Any]]] = {holding_id: [] for holding_id in target_ids}
    loan_ids = {str(cast(Any, holding).loan_id) for holding in holdings}
    if not loan_ids:
        return payloads
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    all_holdings = list(
        holding_model.objects.filter(
            loan_id__in=loan_ids,
            status="active",
            current_principal_minor__gt=0,
        ).order_by("loan_id", "economic_entitlement_start_at", "created_at", "id")
    )
    holdings_by_loan: dict[str, list[Any]] = {loan_id: [] for loan_id in loan_ids}
    for holding in all_holdings:
        holdings_by_loan[str(cast(Any, holding).loan_id)].append(holding)
    profiles = {
        str(profile.loan_id): profile
        for profile in OriginatorLoanProfile.objects.filter(loan_id__in=loan_ids)
        .select_related("loan__currency", "current_import")
        .prefetch_related("current_import__schedule_rows")
    }
    for loan_id in loan_ids:
        profile = profiles.get(loan_id)
        if profile is None:
            continue
        loan_import = profile.current_import
        if loan_import is None:
            continue
        loan_holdings = holdings_by_loan.get(loan_id, [])
        remaining = {
            str(cast(Any, holding).pk): int(cast(Any, holding).current_principal_minor)
            for holding in loan_holdings
        }
        originator_remaining = int(profile.unsold_principal_minor)
        if sum(remaining.values()) + originator_remaining != int(
            profile.current_outstanding_principal_minor
        ):
            raise OriginatorClaimsValidationError(
                "Originator claim holdings do not reconcile to current loan principal."
            )
        schedule_rows = list(
            loan_import.schedule_rows.filter(due_date__gt=loan_import.as_of_date).order_by(
                "due_date", "installment_number", "id"
            )
        )
        for row in schedule_rows:
            ordered_holdings = [
                holding for holding in loan_holdings if remaining[str(cast(Any, holding).pk)] > 0
            ]
            holding_weights = [
                remaining[str(cast(Any, holding).pk)] for holding in ordered_holdings
            ]
            weights = [*holding_weights, originator_remaining]
            if sum(weights) != int(row.opening_principal_minor):
                raise OriginatorClaimsValidationError(
                    "Imported originator schedule does not reconcile to current claim ownership."
                )
            currency = str(profile.loan.currency_id)
            principal_parts, retained_after_minor = _allocate_principal_with_retention(
                holding_principals=holding_weights,
                originator_principal_minor=originator_remaining,
                skin_in_the_game_bps=int(profile.loan.skin_in_the_game_bps),
                principal_minor=int(row.principal_minor),
                currency=currency,
            )
            if _is_par_subscription(profile):
                investor_principal = sum(holding_weights)
                interest_pool = _component_pool_minor(
                    component_minor=int(row.interest_minor),
                    investor_principal_minor=investor_principal,
                    total_principal_minor=sum(weights),
                    participation_bps=int(profile.investor_interest_participation_bps),
                )
                penalty_pool = _component_pool_minor(
                    component_minor=int(row.penalty_minor),
                    investor_principal_minor=investor_principal,
                    total_principal_minor=sum(weights),
                    participation_bps=int(profile.investor_penalty_participation_bps),
                )
                interest_parts = (
                    [
                        part.amount_minor
                        for part in allocate_by_weights(
                            Money(interest_pool, currency),
                            holding_weights,
                        )
                    ]
                    if interest_pool > 0 and investor_principal > 0
                    else [0 for _holding in ordered_holdings]
                )
                penalty_parts = (
                    [
                        part.amount_minor
                        for part in allocate_by_weights(
                            Money(penalty_pool, currency),
                            holding_weights,
                        )
                    ]
                    if penalty_pool > 0 and investor_principal > 0
                    else [0 for _holding in ordered_holdings]
                )
            else:
                all_penalty_parts = allocate_by_weights(
                    Money(int(row.penalty_minor), currency),
                    weights,
                )
                penalty_parts = [part.amount_minor for part in all_penalty_parts[:-1]]
                full_period_days = max(0, (row.due_date - row.accrual_start_date).days)
                numerators: list[int] = []
                for holding, principal_weight in zip(
                    ordered_holdings,
                    holding_weights,
                    strict=True,
                ):
                    entitlement_at = (
                        cast(Any, holding).economic_entitlement_start_at
                        or cast(Any, holding).assignment_effective_at
                    )
                    entitlement_date = business_date(cast(datetime, entitlement_at))
                    eligible_days = max(
                        0,
                        (row.due_date - max(row.accrual_start_date, entitlement_date)).days,
                    )
                    numerators.append(principal_weight * eligible_days)
                denominator = int(row.opening_principal_minor) * full_period_days
                if full_period_days == 0:
                    numerators = holding_weights
                    denominator = int(row.opening_principal_minor)
                interest_parts = _allocate_proportional_entitlement(
                    total_minor=int(row.interest_minor),
                    numerators=numerators,
                    denominator=denominator,
                )
            for index, holding in enumerate(ordered_holdings):
                holding_id = str(cast(Any, holding).pk)
                principal_minor = principal_parts[index].amount_minor
                interest_minor = interest_parts[index]
                penalty_minor = penalty_parts[index]
                remaining[holding_id] -= principal_minor
                if remaining[holding_id] < 0:
                    raise OriginatorClaimsValidationError(
                        "Projected repayment exceeds an originator claim holding."
                    )
                if holding_id not in target_ids:
                    continue
                payloads[holding_id].append(
                    {
                        "loan_installment_id": str(row.id),
                        "schedule_version": int(profile.schedule_revision),
                        "installment_number": int(row.installment_number),
                        "due_date": row.due_date,
                        "projected_principal_minor": principal_minor,
                        "projected_interest_minor": interest_minor,
                        "projected_penalty_minor": penalty_minor,
                        "projected_fee_minor": 0,
                        "projected_total_minor": (principal_minor + interest_minor + penalty_minor),
                        "days_past_due": max(0, (as_of_date - row.due_date).days),
                        "status": (
                            "overdue"
                            if row.due_date < as_of_date
                            else ("due" if row.due_date == as_of_date else "upcoming")
                        ),
                        "accrual_start_date": row.accrual_start_date,
                    }
                )
            originator_remaining -= principal_parts[-1].amount_minor
            if originator_remaining < retained_after_minor:
                raise OriginatorClaimsValidationError(
                    "Projected repayment breaches the originator retention floor."
                )
        if any(remaining.values()) or originator_remaining:
            raise OriginatorClaimsValidationError(
                "Originator claim schedule does not fully amortize current ownership."
            )
    return payloads


def originator_portfolio_loan_payload(
    profile: OriginatorLoanProfile,
    *,
    as_of_date: date,
) -> dict[str, Any]:
    profile = OriginatorLoanProfile.objects.select_related(
        "loan__currency", "originator", "current_import"
    ).get(id=profile.id)
    loan = profile.loan
    collateral_value = int(loan.collateral_value_minor)
    ltv_bps = (
        (2 * int(profile.current_outstanding_principal_minor) * 10_000 + collateral_value)
        // (2 * collateral_value)
        if collateral_value > 0
        else None
    )
    remaining_days = max(0, (profile.maturity_date - as_of_date).days)
    loan_import = profile.current_import
    future_rows = []
    if loan_import is not None:
        future_rows = list(
            loan_import.schedule_rows.filter(due_date__gt=loan_import.as_of_date).order_by(
                "due_date", "installment_number", "id"
            )
        )
    days_past_due = max(
        [(as_of_date - row.due_date).days for row in future_rows if row.due_date < as_of_date],
        default=0,
    )
    return {
        "loan_id": str(loan.id),
        "product_type": "originator_claim",
        "loan_title": str(loan.title),
        "loan_status": str(loan.status),
        "borrower_id": None,
        "borrower_name": str(profile.borrower_display_name),
        "borrower_country": str(profile.borrower_country),
        "originator_id": str(profile.originator_id),
        "originator_name": str(profile.originator.public_name),
        "purpose": str(loan.purpose),
        "collateral_type": str(loan.collateral_type),
        "collateral_value_minor": int(loan.collateral_value_minor),
        "collateral_description": str(loan.collateral_description),
        "risk_rating": str(loan.risk_rating),
        "skin_in_the_game_bps": int(loan.skin_in_the_game_bps),
        "interest_rate_bps": int(profile.target_yield_bps),
        "yield_bps": int(profile.target_yield_bps),
        "underlying_interest_rate_bps": int(loan.interest_rate_bps),
        "default_penalty_interest_bps": int(loan.default_penalty_interest_bps),
        "term_months": max(1, (remaining_days + 29) // 30),
        "remaining_term_days": remaining_days,
        "maturity_date": profile.maturity_date,
        "repayment_type": str(loan.repayment_type),
        "currency": str(loan.currency_id),
        "is_refinancing": False,
        "original_principal_minor": int(loan.original_principal_minor),
        "original_repayment_type": str(loan.repayment_type),
        "original_interest_only_months": int(loan.interest_only_months),
        "principal_minor": int(profile.current_outstanding_principal_minor),
        "funding_deadline": profile.funding_deadline,
        "loan_start_date": loan.loan_start_date,
        "first_payment_date": future_rows[0].due_date if future_rows else None,
        "ltv_bps": ltv_bps,
        "days_past_due": days_past_due,
        "schedule_version": int(profile.schedule_revision),
        "schedule": originator_portfolio_schedule_payload(profile, as_of_date=as_of_date),
    }


def originator_marketplace_payload(
    profile: OriginatorLoanProfile,
    *,
    include_detail: bool,
    pricing_date: date | None = None,
) -> dict[str, Any]:
    profile = OriginatorLoanProfile.objects.select_related(
        "loan__currency", "originator", "current_import"
    ).get(id=profile.id)
    is_par_subscription = _is_par_subscription(profile)
    expected_loan_status = "published" if is_par_subscription else "active"
    if (
        profile.opportunity_status != OriginatorOpportunityStatus.OPEN
        or profile.loan.status != expected_loan_status
        or profile.originator.status != LoanOriginatorStatus.ACTIVE
        or originator_sellable_principal_minor(profile) <= 0
        or profile.is_on_hold
    ):
        raise OriginatorClaimsValidationError("Originator claim opportunity is not open.")
    as_of_date = pricing_date or business_date(now_utc())
    if is_par_subscription and (
        profile.funding_deadline is None or as_of_date > profile.funding_deadline
    ):
        raise OriginatorClaimsValidationError("Originator subscription funding period has ended.")
    if profile.maturity_date <= as_of_date + timedelta(days=30):
        raise OriginatorClaimsValidationError(
            "Originator claim opportunity is within 30 days of maturity."
        )
    if _originator_days_past_due(profile, as_of_date=as_of_date) >= 5:
        raise OriginatorClaimsValidationError(
            "Originator claim opportunity is unavailable because the loan is late."
        )
    loan_import = profile.current_import
    if loan_import is None:
        raise OriginatorClaimsValidationError("Current schedule evidence is unavailable.")
    schedule_rows = list(loan_import.schedule_rows.order_by("installment_number", "id"))
    sellable_principal_minor = originator_sellable_principal_minor(profile)
    committed_principal_minor = (
        int(profile.loan.committed_principal_minor)
        if is_par_subscription
        else int(profile.current_outstanding_principal_minor - profile.unsold_principal_minor)
    )
    remaining_capacity_minor = (
        sellable_principal_minor - committed_principal_minor
        if is_par_subscription
        else sellable_principal_minor
    )
    if remaining_capacity_minor <= 0:
        raise OriginatorClaimsValidationError("Originator claim opportunity is fully subscribed.")
    if is_par_subscription:
        fillable_amount_minor = remaining_capacity_minor
    else:
        try:
            fillable_amount_minor, _fillable_cashflows = price_assigned_principal(
                schedule_rows=schedule_rows,
                current_outstanding_principal_minor=profile.current_outstanding_principal_minor,
                assigned_principal_minor=sellable_principal_minor,
                target_yield_bps=profile.target_yield_bps,
                pricing_date=as_of_date,
                currency=profile.loan.currency_id,
            )
        except PricingValidationError as exc:
            raise OriginatorClaimsValidationError(str(exc)) from exc
    remaining_term_days = max(0, (profile.maturity_date - as_of_date).days)
    collateral_value = int(profile.loan.collateral_value_minor)
    ltv_bps = (
        (2 * profile.current_outstanding_principal_minor * 10_000 + collateral_value)
        // (2 * collateral_value)
        if collateral_value > 0
        else None
    )
    future_rows = [row for row in schedule_rows if row.due_date > as_of_date]
    payload: dict[str, Any] = {
        "loan_id": str(profile.loan_id),
        "product_type": "originator_claim",
        "investment_flow": (
            "primary_order" if is_par_subscription else "immediate_claim_assignment"
        ),
        "title": profile.loan.title,
        "purpose": profile.loan.purpose,
        "collateral_type": profile.loan.collateral_type,
        # Compatibility for older clients. New clients should display yield_bps.
        "interest_rate_bps": int(profile.target_yield_bps),
        "yield_bps": int(profile.target_yield_bps),
        "underlying_interest_rate_bps": int(profile.loan.interest_rate_bps),
        "term_months": max(1, (remaining_term_days + 29) // 30),
        "remaining_term_days": remaining_term_days,
        "risk_rating": profile.loan.risk_rating,
        "funding_deadline": profile.funding_deadline,
        "maturity_date": profile.maturity_date,
        "status": "published",
        "loan_status": profile.loan.status,
        "opportunity_status": profile.opportunity_status,
        "currency": profile.loan.currency_id,
        "principal_minor": int(profile.current_outstanding_principal_minor),
        "committed_principal_minor": committed_principal_minor,
        "remaining_capacity_minor": remaining_capacity_minor,
        "fillable_amount_minor": fillable_amount_minor,
        "skin_in_the_game_bps": int(cast(Any, profile.loan).skin_in_the_game_bps),
        "minimum_investment_minor": int(profile.minimum_investment_minor),
        "ltv_bps": ltv_bps,
        "is_refinancing": False,
        "originator_id": str(profile.originator_id),
        "originator_name": profile.originator.public_name,
        "borrower_display_name": profile.borrower_display_name,
        "distribution_model": profile.distribution_model,
        "entitlement_start_date": profile.entitlement_start_date,
        "investor_interest_participation_bps": int(profile.investor_interest_participation_bps),
        "investor_penalty_participation_bps": int(profile.investor_penalty_participation_bps),
    }
    if not include_detail:
        return payload
    payload.update(
        {
            "borrower_id": None,
            "borrower_disclosure": _public_borrower_snapshot(profile),
            "investor_summary": profile.loan.investor_summary,
            "purpose_description": profile.loan.purpose_description,
            "collateral_value_minor": collateral_value,
            "collateral_description": profile.loan.collateral_description,
            "default_penalty_interest_bps": int(profile.loan.default_penalty_interest_bps),
            "ltv_warnings": (
                ["Loan-to-value exceeds 100%."] if ltv_bps and ltv_bps > 10_000 else []
            ),
            "original_principal_minor": int(profile.loan.original_principal_minor),
            "original_interest_rate_bps": int(profile.loan.interest_rate_bps),
            "original_term_months": len(schedule_rows),
            "original_repayment_type": profile.loan.repayment_type,
            "original_interest_only_months": int(profile.loan.interest_only_months),
            "original_loan_start_date": profile.loan.loan_start_date,
            "repayment_type": profile.loan.repayment_type,
            "loan_start_date": profile.loan.loan_start_date,
            "first_payment_date": future_rows[0].due_date if future_rows else None,
            "schedule_version": int(profile.schedule_revision),
            "originator_schedule": _originator_schedule_payload(profile),
            "originator_payment_history": _originator_payment_history_payload(profile),
            "schedule_revision": int(profile.schedule_revision),
            "pricing_as_of_date": as_of_date,
        }
    )
    return payload


def list_open_originator_marketplace_payloads(*, limit: int = 100) -> list[dict[str, Any]]:
    profiles = (
        OriginatorLoanProfile.objects.filter(
            opportunity_status=OriginatorOpportunityStatus.OPEN,
            originator__status=LoanOriginatorStatus.ACTIVE,
            unsold_principal_minor__gt=0,
            is_on_hold=False,
        )
        .filter(
            Q(
                distribution_model=OriginatorDistributionModel.PAR_COMPONENT_V2,
                loan__status="published",
            )
            | Q(
                distribution_model=OriginatorDistributionModel.LEGACY_YIELD_V1,
                loan__status="active",
            )
        )
        .select_related("loan__currency", "originator", "current_import")
        .order_by("maturity_date", "id")[:limit]
    )
    payloads: list[dict[str, Any]] = []
    for profile in profiles:
        try:
            payloads.append(originator_marketplace_payload(profile, include_detail=False))
        except OriginatorClaimsValidationError:
            continue
    return payloads


def get_originator_marketplace_payload(*, actor: Model, loan_id: str) -> dict[str, Any]:
    if not user_can_access_financial_features(actor):
        raise OriginatorClaimsAuthorizationError(
            "Financial access, phone verification, and approved KYC are required."
        )
    profile = OriginatorLoanProfile.objects.filter(loan_id=loan_id).first()
    if profile is None:
        raise OriginatorClaimsValidationError("Originator claim opportunity does not exist.")
    return originator_marketplace_payload(profile, include_detail=True)


def _quote_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _cash_flow_payload(flow: Any) -> dict[str, Any]:
    return {
        "installment_number": flow.installment_number,
        "accrual_start_date": flow.accrual_start_date.isoformat(),
        "due_date": flow.due_date.isoformat(),
        "principal_minor": flow.principal_minor,
        "interest_minor": flow.interest_minor,
        "penalty_minor": flow.penalty_minor,
        "total_minor": flow.total_minor,
        "days_to_payment": flow.days_to_payment,
        "present_value_minor": flow.present_value_minor,
    }


@transaction.atomic
def _close_mature_originator_opportunity(*, loan_id: str, as_of_date: date) -> bool:
    profile = _locked_profile_for_loan(loan_id)
    if (
        profile.opportunity_status != OriginatorOpportunityStatus.OPEN
        or profile.maturity_date > as_of_date + timedelta(days=30)
    ):
        return False
    profile.opportunity_status = OriginatorOpportunityStatus.CLOSED
    profile.closed_at = now_utc()
    profile.close_reason = "maturity_within_30_days"
    profile.save(update_fields=["opportunity_status", "closed_at", "close_reason", "updated_at"])
    return True


def create_originator_claim_quote(
    command: CreateOriginatorClaimQuoteCommand,
) -> OriginatorClaimQuote:
    if not user_can_access_financial_features(command.actor):
        raise OriginatorClaimsAuthorizationError(
            "Financial access, phone verification, and approved KYC are required."
        )
    today = business_date(now_utc())
    profile = (
        OriginatorLoanProfile.objects.filter(loan_id=command.loan_id)
        .only("distribution_model")
        .first()
    )
    if profile is not None and _is_par_subscription(profile):
        raise OriginatorClaimsValidationError(
            "This Loan Originator opportunity uses a funding subscription, not an executable quote."
        )
    if _close_mature_originator_opportunity(
        loan_id=command.loan_id,
        as_of_date=today,
    ):
        raise OriginatorClaimsValidationError(
            "This opportunity is closed because 30 days or less remain to maturity."
        )
    return _create_originator_claim_quote_locked(command, today=today)


@transaction.atomic
def _create_originator_claim_quote_locked(
    command: CreateOriginatorClaimQuoteCommand,
    *,
    today: date,
) -> OriginatorClaimQuote:
    profile = _locked_profile_for_loan(
        command.loan_id,
        "loan",
        "originator",
        "current_import",
        "loan__currency",
    )
    if _is_par_subscription(profile):
        raise OriginatorClaimsValidationError(
            "This Loan Originator opportunity uses a funding subscription, not an executable quote."
        )
    if (
        profile.opportunity_status != OriginatorOpportunityStatus.OPEN
        or profile.loan.status != "active"
    ):
        raise OriginatorClaimsValidationError("Originator claim opportunity is not open.")
    if profile.originator.status != LoanOriginatorStatus.ACTIVE:
        raise OriginatorClaimsValidationError("Loan Originator is not active.")
    if profile.maturity_date <= today + timedelta(days=30):
        raise OriginatorClaimsValidationError(
            "This opportunity is closed because 30 days or less remain to maturity."
        )
    if _originator_days_past_due(profile, as_of_date=today) >= 5:
        raise OriginatorClaimsValidationError(
            "This opportunity is unavailable because the loan is late."
        )
    loan_import = profile.current_import
    if loan_import is None:
        raise OriginatorClaimsValidationError("Current schedule evidence is unavailable.")
    schedule_rows = list(loan_import.schedule_rows.order_by("installment_number"))
    try:
        priced = quote_cash_consideration(
            schedule_rows=schedule_rows,
            current_outstanding_principal_minor=profile.current_outstanding_principal_minor,
            unsold_principal_minor=originator_sellable_principal_minor(profile),
            requested_cash_minor=command.requested_cash_minor,
            minimum_investment_minor=profile.minimum_investment_minor,
            target_yield_bps=profile.target_yield_bps,
            premium_fee_bps=profile.premium_fee_bps,
            pricing_date=today,
            currency=profile.loan.currency.code,
        )
    except PricingValidationError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc
    now = timezone.now()
    cash_flows = [_cash_flow_payload(flow) for flow in priced.cash_flows]
    fingerprint_payload = {
        "loan_id": str(profile.loan_id),
        "investor_user_id": str(command.actor.pk),
        "requested_cash_minor": priced.requested_cash_minor,
        "executable_cash_minor": priced.executable_cash_minor,
        "assigned_principal_minor": priced.assigned_principal_minor,
        "outstanding_principal_at_pricing_minor": (profile.current_outstanding_principal_minor),
        "target_yield_bps": profile.target_yield_bps,
        "schedule_revision": profile.schedule_revision,
        "entitlement_start_at": now,
        "cash_flows": cash_flows,
    }
    quote = OriginatorClaimQuote.objects.create(
        loan_profile=profile,
        investor_user_id=command.actor.pk,
        currency=profile.loan.currency,
        requested_cash_minor=priced.requested_cash_minor,
        executable_cash_minor=priced.executable_cash_minor,
        assigned_principal_minor=priced.assigned_principal_minor,
        outstanding_principal_at_pricing_minor=(profile.current_outstanding_principal_minor),
        share_ppm=priced.share_ppm,
        target_yield_bps=profile.target_yield_bps,
        premium_discount_minor=priced.premium_discount_minor,
        platform_fee_minor=priced.platform_fee_minor,
        originator_payable_minor=priced.originator_payable_minor,
        rounding_remainder_minor=priced.rounding_remainder_minor,
        schedule_revision=profile.schedule_revision,
        entitlement_start_at=now,
        expires_at=now + timedelta(minutes=5),
        cash_flows=cash_flows,
        calculation_fingerprint=_quote_fingerprint(fingerprint_payload),
    )
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.QUOTE_CREATED,
        originator=profile.originator,
        loan_id=profile.loan_id,
        metadata={
            "quote_id": str(quote.id),
            "executable_cash_minor": quote.executable_cash_minor,
            "assigned_principal_minor": quote.assigned_principal_minor,
        },
    )
    return cast(OriginatorClaimQuote, quote)


def _purchase_request_fingerprint(command: PurchaseOriginatorClaimCommand) -> str:
    return _quote_fingerprint(
        {
            "investor_user_id": str(command.actor.pk),
            "quote_id": str(command.quote_id),
            "document_acceptance_id": str(command.document_acceptance_id),
            "idempotency_key": command.idempotency_key.strip(),
        }
    )


def _existing_purchase(
    *,
    idempotency_key: str,
    expected_fingerprint: str,
) -> OriginatorClaimPurchase | None:
    existing = OriginatorClaimPurchase.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if existing.request_fingerprint != expected_fingerprint:
        raise OriginatorClaimsValidationError(
            "Idempotency key was already used for a different originator claim purchase."
        )
    return cast(OriginatorClaimPurchase, existing)


def _validate_purchase_acceptance(
    *,
    acceptance_id: str,
    actor: Model,
    quote: OriginatorClaimQuote,
) -> Model:
    acceptance_model = apps.get_model("documents", "DocumentAcceptanceEvidence")
    acceptance = cast(
        Model | None,
        acceptance_model.objects.select_related("template", "template_version")
        .filter(id=acceptance_id, user_id=actor.pk)
        .first(),
    )
    if acceptance is None:
        raise OriginatorClaimsValidationError("Document acceptance does not exist.")
    acceptance_ref = cast(Any, acceptance)
    if str(acceptance_ref.category) != "primary_market_investment":
        raise OriginatorClaimsValidationError("Document acceptance category is not valid.")
    if str(acceptance_ref.context_type) != "originator_claim_quote":
        raise OriginatorClaimsValidationError("Document acceptance context is not valid.")
    if str(acceptance_ref.context_id) != str(quote.id):
        raise OriginatorClaimsValidationError("Document acceptance does not match this quote.")
    if str(acceptance_ref.template.current_published_version_id) != str(
        acceptance_ref.template_version_id
    ):
        raise OriginatorClaimsValidationError("Document acceptance is no longer current.")
    return acceptance


def purchase_originator_claim(
    command: PurchaseOriginatorClaimCommand,
) -> OriginatorClaimPurchase:
    if not user_can_access_financial_features(command.actor):
        raise OriginatorClaimsAuthorizationError(
            "Financial access, phone verification, and approved KYC are required."
        )
    idempotency_key = _required(command.idempotency_key, "Idempotency key")
    if len(idempotency_key) > 160:
        raise OriginatorClaimsValidationError("Idempotency key cannot exceed 160 characters.")
    request_fingerprint = _purchase_request_fingerprint(command)
    existing = _existing_purchase(
        idempotency_key=idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
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
        raise OriginatorClaimsValidationError(str(exc)) from exc
    return _purchase_originator_claim_after_sensitive_code(
        command,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )


def purchase_originator_claim_in_verified_batch(
    command: PurchaseOriginatorClaimInVerifiedBatchCommand,
) -> OriginatorClaimPurchase:
    """Purchase one quoted claim after the parent batch verified its single code.

    This is intentionally not exposed through an API view. The marketplace batch
    orchestrator owns the preceding sensitive-action verification and wraps all
    child purchases and direct allocations in one outer transaction.
    """

    if not user_can_access_financial_features(command.actor):
        raise OriginatorClaimsAuthorizationError(
            "Financial access, phone verification, and approved KYC are required."
        )
    purchase_command = PurchaseOriginatorClaimCommand(
        actor=command.actor,
        quote_id=command.quote_id,
        document_acceptance_id=command.document_acceptance_id,
        sensitive_action_code_id="",
        sensitive_action_code="",
        idempotency_key=command.idempotency_key,
        ip_address=command.ip_address,
        user_agent=command.user_agent,
    )
    idempotency_key = _required(command.idempotency_key, "Idempotency key")
    if len(idempotency_key) > 160:
        raise OriginatorClaimsValidationError("Idempotency key cannot exceed 160 characters.")
    request_fingerprint = _purchase_request_fingerprint(purchase_command)
    existing = _existing_purchase(
        idempotency_key=idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    return _purchase_originator_claim_after_sensitive_code(
        purchase_command,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )


@transaction.atomic
def _purchase_originator_claim_after_sensitive_code(
    command: PurchaseOriginatorClaimCommand,
    *,
    idempotency_key: str,
    request_fingerprint: str,
) -> OriginatorClaimPurchase:
    quote = (
        OriginatorClaimQuote.objects.select_for_update(of=("self",))
        .select_related(
            "loan_profile__loan__currency",
            "loan_profile__originator",
            "loan_profile__current_import",
        )
        .filter(id=command.quote_id, investor_user_id=command.actor.pk)
        .first()
    )
    if quote is None:
        raise OriginatorClaimsValidationError("Originator claim quote does not exist.")
    profile = (
        OriginatorLoanProfile.objects.select_for_update(of=("self",))
        .select_related("loan", "originator", "current_import", "loan__currency")
        .get(id=quote.loan_profile_id)
    )
    existing = _existing_purchase(
        idempotency_key=idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    quote_purchase = OriginatorClaimPurchase.objects.filter(quote=quote).first()
    if quote_purchase is not None:
        raise OriginatorClaimsValidationError("This quote has already been purchased.")
    now = now_utc()
    today = business_date(now)
    if quote.expires_at <= now:
        raise OriginatorClaimsValidationError("Originator claim quote has expired.")
    if profile.opportunity_status != OriginatorOpportunityStatus.OPEN:
        raise OriginatorClaimsValidationError("Originator claim opportunity is not open.")
    if profile.loan.status != "active" or profile.originator.status != LoanOriginatorStatus.ACTIVE:
        raise OriginatorClaimsValidationError("Originator claim opportunity is not executable.")
    if profile.maturity_date <= today + timedelta(days=30):
        raise OriginatorClaimsValidationError(
            "Originator claim opportunity is within 30 days of maturity."
        )
    if _originator_days_past_due(profile, as_of_date=today) >= 5:
        raise OriginatorClaimsValidationError(
            "Originator claim opportunity is unavailable because the loan is late."
        )
    loan_import = profile.current_import
    if loan_import is None or quote.schedule_revision != profile.schedule_revision:
        raise OriginatorClaimsValidationError(
            "The loan schedule changed after this quote was issued. Request a new quote."
        )
    if quote.assigned_principal_minor > originator_sellable_principal_minor(profile):
        raise OriginatorClaimsValidationError(
            "The remaining originator claim is smaller than this quote. Request a new quote."
        )
    acceptance = _validate_purchase_acceptance(
        acceptance_id=command.document_acceptance_id,
        actor=command.actor,
        quote=quote,
    )
    purchase_id = _operation_uuid(
        "originator-claim-purchase",
        f"{command.actor.pk}:{idempotency_key}",
    )
    ledger = import_module("backend.apps.ledger.services")
    holdings = import_module("backend.apps.holdings.services")
    try:
        ledger_result = ledger.settle_originator_claim_purchase_ledger(
            ledger.SettleOriginatorClaimPurchaseLedgerCommand(
                actor=command.actor,
                purchase_id=str(purchase_id),
                loan_id=str(profile.loan_id),
                originator_id=str(profile.originator_id),
                investor_user_id=str(command.actor.pk),
                currency=profile.loan.currency.code,
                cash_consideration_minor=quote.executable_cash_minor,
                assigned_principal_minor=quote.assigned_principal_minor,
                platform_fee_minor=quote.platform_fee_minor,
                originator_payable_minor=quote.originator_payable_minor,
                source_type="originator_claim_purchase",
                source_id=str(purchase_id),
                idempotency_key=f"originator-purchase-ledger:{idempotency_key}",
                as_of=now,
                metadata={"quote_id": str(quote.id)},
            )
        )
    except ledger.LedgerError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc
    try:
        holding = holdings.create_originator_claim_holding(
            holdings.CreateOriginatorClaimHoldingCommand(
                actor=command.actor,
                investor_user_id=str(command.actor.pk),
                loan_id=str(profile.loan_id),
                purchase_id=str(purchase_id),
                principal_minor=quote.assigned_principal_minor,
                current_loan_principal_minor=profile.current_outstanding_principal_minor,
                currency=profile.loan.currency.code,
                assignment_effective_at=now,
                idempotency_key=f"originator-purchase-holding:{idempotency_key}",
                loan_share_ppm=quote.share_ppm,
                metadata={
                    "quote_id": str(quote.id),
                    "target_yield_bps": quote.target_yield_bps,
                    "cash_consideration_minor": quote.executable_cash_minor,
                    "outstanding_principal_at_pricing_minor": (
                        quote.outstanding_principal_at_pricing_minor
                    ),
                },
            )
        )
    except holdings.HoldingsError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc
    try:
        with transaction.atomic():
            purchase = cast(
                OriginatorClaimPurchase,
                OriginatorClaimPurchase.objects.create(
                    id=purchase_id,
                    loan_profile=profile,
                    quote=quote,
                    investor_user_id=command.actor.pk,
                    currency=quote.currency,
                    cash_consideration_minor=quote.executable_cash_minor,
                    assigned_principal_minor=quote.assigned_principal_minor,
                    outstanding_principal_at_pricing_minor=(
                        quote.outstanding_principal_at_pricing_minor
                    ),
                    share_ppm=quote.share_ppm,
                    target_yield_bps=quote.target_yield_bps,
                    premium_discount_minor=quote.premium_discount_minor,
                    platform_fee_minor=quote.platform_fee_minor,
                    originator_payable_minor=quote.originator_payable_minor,
                    schedule_revision=quote.schedule_revision,
                    entitlement_start_at=now,
                    document_acceptance=acceptance,
                    journal_entry=ledger_result.journal_entry,
                    holding=holding,
                    lot_allocations=ledger_result.investor_lot_allocations,
                    purchased_at=now,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_fingerprint,
                ),
            )
    except IntegrityError:
        existing_after_race = _existing_purchase(
            idempotency_key=idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    rows_by_number = {
        row.installment_number: row for row in loan_import.schedule_rows.filter(due_date__gte=today)
    }
    entitlements: list[OriginatorClaimEntitlement] = []
    for flow in cast(list[dict[str, Any]], quote.cash_flows):
        installment_number = int(flow["installment_number"])
        schedule_row = rows_by_number.get(installment_number)
        if schedule_row is None:
            raise OriginatorClaimsValidationError(
                "Quoted entitlement references an unavailable schedule row."
            )
        entitlement_principal = int(flow["principal_minor"])
        entitlement_interest = int(flow["interest_minor"])
        entitlement_penalty = int(flow.get("penalty_minor", 0))
        entitlements.append(
            OriginatorClaimEntitlement(
                purchase=purchase,
                schedule_row=schedule_row,
                accrual_start_date=date.fromisoformat(str(flow["accrual_start_date"])),
                due_date=date.fromisoformat(str(flow["due_date"])),
                expected_principal_minor=entitlement_principal,
                expected_interest_minor=entitlement_interest,
                expected_penalty_minor=entitlement_penalty,
                expected_total_minor=(
                    entitlement_principal + entitlement_interest + entitlement_penalty
                ),
            )
        )
    OriginatorClaimEntitlement.objects.bulk_create(entitlements)
    profile.unsold_principal_minor -= quote.assigned_principal_minor
    update_fields = ["unsold_principal_minor", "updated_at"]
    if originator_sellable_principal_minor(profile) == 0:
        profile.opportunity_status = OriginatorOpportunityStatus.CLOSED
        profile.closed_at = now
        profile.close_reason = (
            "skin_in_the_game_floor_reached" if profile.unsold_principal_minor > 0 else "fully_sold"
        )
        update_fields.extend(["opportunity_status", "closed_at", "close_reason"])
    profile.save(update_fields=update_fields)
    profile.loan.committed_principal_minor += quote.assigned_principal_minor
    profile.loan.save(update_fields=["committed_principal_minor", "updated_at"])
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.CLAIM_PURCHASED,
        originator=profile.originator,
        loan_id=profile.loan_id,
        purchase_id=purchase.id,
        metadata={
            "quote_id": str(quote.id),
            "holding_id": str(holding.id),
            "journal_entry_id": str(ledger_result.journal_entry.id),
            "investor_user_id": str(command.actor.pk),
            "cash_consideration_minor": purchase.cash_consideration_minor,
            "assigned_principal_minor": purchase.assigned_principal_minor,
            "outstanding_principal_at_pricing_minor": (
                purchase.outstanding_principal_at_pricing_minor
            ),
            "share_ppm": purchase.share_ppm,
            "entitlement_count": len(entitlements),
        },
    )
    purchase_currency = str(purchase.currency_id)
    purchase_cash_display = format_amount_minor(
        purchase.cash_consideration_minor, purchase_currency
    )
    purchase_principal_display = format_amount_minor(
        purchase.assigned_principal_minor, purchase_currency
    )
    purchase_yield_display = (
        f"{purchase.target_yield_bps // 100}.{purchase.target_yield_bps % 100:02d}%"
    )
    _enqueue_investor_email(
        investor_user_id=str(command.actor.pk),
        topic="email.originator_claim_purchase_confirmation",
        subject="BANXUM loan claim purchase completed",
        body_text=(
            f"Your purchase of {profile.loan.title} completed.\n"
            "You now hold a legal assignment of part of the final-borrower claim.\n"
            f"Cash paid: {purchase_cash_display}.\n"
            f"Assigned principal: {purchase_principal_display}.\n"
            f"Target yield at purchase: {purchase_yield_display} p.a. effective, ACT/365.\n"
            f"Economic entitlement starts: {purchase.entitlement_start_at.isoformat()}.\n"
            "Yield is before credit losses and investor taxes and is not guaranteed."
        ),
        template_key="originator_claim.purchase_confirmation.v1",
        idempotency_key=f"originator-purchase-email:{purchase.id}",
        metadata={
            "purchase_id": str(purchase.id),
            "loan_id": str(profile.loan_id),
            "loan_title": str(profile.loan.title),
            "currency": str(purchase.currency_id),
            "cash_consideration_minor": purchase.cash_consideration_minor,
            "assigned_principal_minor": purchase.assigned_principal_minor,
            "target_yield_bps": purchase.target_yield_bps,
            "entitlement_start_at": purchase.entitlement_start_at.isoformat(),
        },
    )
    return purchase


def _payment_signature(payment: Any) -> tuple[Any, ...]:
    return (
        payment.reference,
        payment.value_date,
        payment.payment_type,
        payment.principal_minor,
        payment.interest_minor,
        payment.penalty_minor,
        payment.fee_minor,
        payment.total_minor,
        payment.resulting_principal_minor,
    )


def _repayment_request_fingerprint(
    command: RecordOriginatorBorrowerRepaymentCommand,
    *,
    source_sha256: str,
) -> str:
    return _quote_fingerprint(
        {
            "loan_id": str(command.loan_id),
            "source_sha256": source_sha256,
            "source_filename": command.source_filename.strip(),
            "as_of_date": command.as_of_date.isoformat(),
            "payment_reference": command.payment_reference.strip(),
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "payer_name": command.payer_name.strip(),
            "payer_account_identifier": command.payer_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "bank_payment_reference": command.bank_payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "notes": command.notes.strip(),
            "idempotency_key": command.idempotency_key.strip(),
        }
    )


def _existing_originator_repayment(
    *,
    idempotency_key: str,
    expected_fingerprint: str | None = None,
) -> OriginatorBorrowerRepayment | None:
    existing = OriginatorBorrowerRepayment.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if expected_fingerprint and existing.request_fingerprint != expected_fingerprint:
        raise OriginatorClaimsValidationError(
            "Idempotency key was already used for a different originator repayment."
        )
    return cast(OriginatorBorrowerRepayment, existing)


def _repayment_accrual_start(
    *,
    loan_import: OriginatorLoanImport,
    value_date: date,
) -> date:
    rows = list(loan_import.schedule_rows.order_by("accrual_start_date", "id"))
    ending_today = [row for row in rows if row.due_date == value_date]
    if ending_today:
        return ending_today[-1].accrual_start_date
    containing = [row for row in rows if row.accrual_start_date <= value_date < row.due_date]
    if containing:
        return containing[-1].accrual_start_date
    prior_starts = [row.accrual_start_date for row in rows if row.accrual_start_date <= value_date]
    if prior_starts:
        return max(prior_starts)
    return rows[0].accrual_start_date


def _originator_payment_waterfall(
    *,
    loan_import: OriginatorLoanImport,
    payment: Any,
    outstanding_principal_minor: int,
) -> PaymentWaterfallAllocation:
    rows = list(loan_import.schedule_rows.order_by("due_date", "installment_number", "id"))
    prior_payments = list(loan_import.payment_rows.order_by("value_date", "reference", "id"))
    due_rows = [row for row in rows if row.due_date <= payment.value_date]
    if payment.payment_type == "regular" and not any(
        row.due_date == payment.value_date for row in due_rows
    ):
        next_rows = [row for row in rows if row.due_date > payment.value_date]
        if next_rows and (next_rows[0].due_date - payment.value_date).days <= 1:
            due_rows.append(next_rows[0])

    prior_fee = sum(int(row.fee_minor) for row in prior_payments)
    prior_penalty = sum(int(row.penalty_minor) for row in prior_payments)
    prior_interest = sum(int(row.interest_minor) for row in prior_payments)
    prior_principal = sum(int(row.principal_minor) for row in prior_payments)
    fee_due = max(0, sum(int(row.fee_minor) for row in due_rows) - prior_fee)
    penalty_due = max(0, sum(int(row.penalty_minor) for row in due_rows) - prior_penalty)
    interest_due = max(0, sum(int(row.interest_minor) for row in due_rows) - prior_interest)

    if payment.payment_type == "repayment_in_advance":
        containing = [
            row for row in rows if row.accrual_start_date <= payment.value_date < row.due_date
        ]
        if containing:
            row = containing[-1]
            period_days = max(1, (row.due_date - row.accrual_start_date).days)
            elapsed_days = max(0, (payment.value_date - row.accrual_start_date).days)
            prorated_interest = int(
                (
                    Decimal(int(row.interest_minor)) * Decimal(elapsed_days) / Decimal(period_days)
                ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            interest_due = max(
                interest_due,
                max(
                    0,
                    sum(int(item.interest_minor) for item in due_rows)
                    + prorated_interest
                    - prior_interest,
                ),
            )
        principal_due = outstanding_principal_minor
    else:
        principal_due = max(
            0,
            sum(int(row.principal_minor) for row in due_rows) - prior_principal,
        )

    try:
        allocation = allocate_payment_waterfall(
            int(payment.total_minor),
            PaymentWaterfallObligations(
                costs_minor=fee_due,
                penalty_minor=penalty_due,
                interest_minor=interest_due,
                principal_minor=principal_due,
            ),
        )
    except PaymentWaterfallError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc
    actual = (
        int(payment.fee_minor),
        int(payment.penalty_minor),
        int(payment.interest_minor),
        int(payment.principal_minor),
    )
    expected = (
        allocation.costs_minor,
        allocation.penalty_minor,
        allocation.interest_minor,
        allocation.principal_minor,
    )
    if actual != expected:
        raise OriginatorClaimsValidationError(
            "Imported repayment split violates the universal payment waterfall. "
            "Apply Garanta legal costs/recovery fee first, then penalty, interest, "
            "and principal."
        )
    return allocation


def _originator_repayment_plan(
    *,
    holdings: list[Any],
    originator_principal_minor: int,
    skin_in_the_game_bps: int,
    principal_minor: int,
    interest_minor: int,
    penalty_minor: int,
    value_date: date,
    accrual_start_date: date,
    currency: str,
    distribution_model: str = OriginatorDistributionModel.LEGACY_YIELD_V1,
    investor_interest_participation_bps: int = 10_000,
    investor_penalty_participation_bps: int = 10_000,
) -> tuple[list[OriginatorRepaymentPlanLine], dict[str, int]]:
    holding_principals = [int(holding.current_principal_minor) for holding in holdings]
    principal_weights = [*holding_principals, originator_principal_minor]
    principal_parts, retained_after_minor = _allocate_principal_with_retention(
        holding_principals=holding_principals,
        originator_principal_minor=originator_principal_minor,
        skin_in_the_game_bps=skin_in_the_game_bps,
        principal_minor=principal_minor,
        currency=currency,
    )
    total_principal = sum(principal_weights)
    if distribution_model == OriginatorDistributionModel.PAR_COMPONENT_V2:
        investor_principal = sum(holding_principals)
        investor_interest_pool = _component_pool_minor(
            component_minor=interest_minor,
            investor_principal_minor=investor_principal,
            total_principal_minor=total_principal,
            participation_bps=_participation_bps(
                investor_interest_participation_bps,
                "Investor interest participation",
            ),
        )
        investor_penalty_pool = _component_pool_minor(
            component_minor=penalty_minor,
            investor_principal_minor=investor_principal,
            total_principal_minor=total_principal,
            participation_bps=_participation_bps(
                investor_penalty_participation_bps,
                "Investor penalty participation",
            ),
        )
        investor_interest_parts = (
            [
                part.amount_minor
                for part in allocate_by_weights(
                    Money(investor_interest_pool, currency),
                    holding_principals,
                )
            ]
            if investor_interest_pool > 0 and investor_principal > 0
            else [0 for _holding in holdings]
        )
        investor_penalty_parts = (
            [
                part.amount_minor
                for part in allocate_by_weights(
                    Money(investor_penalty_pool, currency),
                    holding_principals,
                )
            ]
            if investor_penalty_pool > 0 and investor_principal > 0
            else [0 for _holding in holdings]
        )
        originator_interest_minor = interest_minor - investor_interest_pool
        originator_penalty_minor = penalty_minor - investor_penalty_pool
    else:
        penalty_parts = allocate_by_weights(Money(penalty_minor, currency), principal_weights)
        investor_penalty_parts = [part.amount_minor for part in penalty_parts[:-1]]
        originator_penalty_minor = penalty_parts[-1].amount_minor
        full_period_days = max(0, (value_date - accrual_start_date).days)
        investor_interest_numerators: list[int] = []
        for holding, holding_principal in zip(holdings, holding_principals, strict=True):
            entitlement_start = (
                holding.economic_entitlement_start_at or holding.assignment_effective_at
            )
            assignment_date = business_date(cast(datetime, entitlement_start))
            eligible_days = max(
                0,
                (value_date - max(accrual_start_date, assignment_date)).days,
            )
            investor_interest_numerators.append(holding_principal * eligible_days)
        if full_period_days > 0:
            interest_denominator = total_principal * full_period_days
        else:
            interest_denominator = total_principal
            investor_interest_numerators = holding_principals
        investor_interest_parts = _allocate_proportional_entitlement(
            total_minor=interest_minor,
            numerators=investor_interest_numerators,
            denominator=interest_denominator,
        )
        originator_interest_minor = interest_minor - sum(investor_interest_parts)

    plan: list[OriginatorRepaymentPlanLine] = []
    for index, holding in enumerate(holdings):
        before = holding_principals[index]
        principal_part = principal_parts[index].amount_minor
        if principal_part > before:
            raise OriginatorClaimsValidationError(
                "Repayment principal allocation exceeds an investor holding."
            )
        interest_part = investor_interest_parts[index]
        penalty_part = investor_penalty_parts[index]
        amount = principal_part + interest_part + penalty_part
        if amount <= 0:
            continue
        plan.append(
            OriginatorRepaymentPlanLine(
                holding=holding,
                investor_user_id=str(holding.investor_user_id),
                principal_minor=principal_part,
                interest_minor=interest_part,
                penalty_minor=penalty_part,
                amount_minor=amount,
                principal_before_minor=before,
                principal_after_minor=before - principal_part,
            )
        )
    originator_components = {
        "principal_minor": principal_parts[-1].amount_minor,
        "interest_minor": originator_interest_minor,
        "penalty_minor": originator_penalty_minor,
        "fee_minor": 0,
    }
    if originator_principal_minor - originator_components["principal_minor"] < retained_after_minor:
        raise OriginatorClaimsValidationError(
            "Repayment would breach the declared skin-in-the-game floor."
        )
    if sum(line.amount_minor for line in plan) + sum(originator_components.values()) != (
        principal_minor + interest_minor + penalty_minor
    ):
        raise OriginatorClaimsValidationError(
            "Originator repayment distribution does not reconcile."
        )
    return plan, originator_components


def _allocate_proportional_entitlement(
    *,
    total_minor: int,
    numerators: list[int],
    denominator: int,
) -> list[int]:
    if total_minor <= 0:
        return [0 for _ in numerators]
    if denominator <= 0 or any(value < 0 for value in numerators):
        raise OriginatorClaimsValidationError("Interest entitlement weights are invalid.")
    numerator_total = sum(numerators)
    if numerator_total > denominator:
        raise OriginatorClaimsValidationError(
            "Investor interest entitlement exceeds the full accrual period."
        )
    raw = [total_minor * value for value in numerators]
    parts = [value // denominator for value in raw]
    target_total = (2 * total_minor * numerator_total + denominator) // (2 * denominator)
    remainder_count = target_total - sum(parts)
    ranked = sorted(
        range(len(numerators)),
        key=lambda index: (-(raw[index] % denominator), index),
    )
    for index in ranked[:remainder_count]:
        parts[index] += 1
    return parts


def _record_originator_holding_repayment(
    *,
    actor: Model,
    repayment_id: str,
    line: OriginatorRepaymentPlanLine,
) -> None:
    holding = cast(Any, line.holding)
    previous_status = str(holding.status)
    holding.current_principal_minor = line.principal_after_minor
    if line.principal_after_minor == 0:
        holding.status = "closed"
    holding.save(update_fields=["current_principal_minor", "status", "updated_at"])
    event_model = apps.get_model("holdings", "InvestorLoanHoldingEvent")
    event_model.objects.create(
        holding=holding,
        loan_id=holding.loan_id,
        investor_user_id=holding.investor_user_id,
        event_type=("closed" if line.principal_after_minor == 0 else "principal_updated"),
        actor_user_id=actor.pk,
        actor_account_type=str(getattr(actor, "account_type", "")),
        previous_status=previous_status,
        new_status=str(holding.status),
        note="Originator-loan borrower repayment distribution.",
        metadata={
            "originator_repayment_id": repayment_id,
            "principal_repaid_minor": line.principal_minor,
            "current_principal_before_minor": line.principal_before_minor,
            "current_principal_after_minor": line.principal_after_minor,
        },
    )


@transaction.atomic
def record_originator_borrower_repayment(
    command: RecordOriginatorBorrowerRepaymentCommand,
) -> OriginatorBorrowerRepayment:
    _require_admin(command.actor)
    idempotency_key = _required(command.idempotency_key, "Idempotency key")
    if len(idempotency_key) > 160:
        raise OriginatorClaimsValidationError("Idempotency key cannot exceed 160 characters.")
    source_sha256 = hashlib.sha256(command.csv_content.encode("utf-8")).hexdigest()
    fingerprint = _repayment_request_fingerprint(command, source_sha256=source_sha256)
    existing = _existing_originator_repayment(
        idempotency_key=idempotency_key,
        expected_fingerprint=fingerprint,
    )
    if existing is not None:
        return existing
    profile = _locked_profile_for_loan(
        command.loan_id,
        "loan__currency",
        "originator",
        "current_import",
    )
    existing_after_lock = _existing_originator_repayment(
        idempotency_key=idempotency_key,
        expected_fingerprint=fingerprint,
    )
    if existing_after_lock is not None:
        return existing_after_lock
    loan = cast(Any, profile.loan)
    if loan.status not in {"active", "late", "defaulted"}:
        raise OriginatorClaimsValidationError(
            "Only active, late, or defaulted originator loans accept repayments."
        )
    current_import = profile.current_import
    if current_import is None:
        raise OriginatorClaimsValidationError("Originator loan has no current import.")
    if command.value_date > command.as_of_date:
        raise OriginatorClaimsValidationError(
            "Replacement schedule as-of date cannot precede the repayment value date."
        )
    try:
        parsed = parse_originator_import_csv(
            csv_content=command.csv_content,
            original_principal_minor=int(loan.original_principal_minor),
            as_of_date=command.as_of_date,
            repayment_type=str(loan.repayment_type),
            interest_only_months=int(loan.interest_only_months),
        )
    except OriginatorImportValidationError as exc:
        raise OriginatorClaimsValidationError(str(exc)) from exc
    previous_payments = {
        row.reference: _payment_signature(row) for row in current_import.payment_rows.all()
    }
    parsed_payments = {row.reference: row for row in parsed.payment_rows}
    for reference, signature in previous_payments.items():
        replacement = parsed_payments.get(reference)
        if replacement is None or _payment_signature(replacement) != signature:
            raise OriginatorClaimsValidationError(
                "Replacement CSV must preserve every previously imported payment exactly."
            )
    added_references = sorted(set(parsed_payments) - set(previous_payments))
    payment_reference = _required(command.payment_reference, "Payment reference")
    if added_references != [payment_reference]:
        raise OriginatorClaimsValidationError(
            "Replacement CSV must add exactly the repayment reference being recorded."
        )
    payment = parsed_payments[payment_reference]
    if payment.value_date != command.value_date:
        raise OriginatorClaimsValidationError(
            "CSV payment value date must match the declared bank value date."
        )
    before_principal = int(profile.current_outstanding_principal_minor)
    waterfall = _originator_payment_waterfall(
        loan_import=current_import,
        payment=payment,
        outstanding_principal_minor=before_principal,
    )
    expected_after = before_principal - payment.principal_minor
    if expected_after < 0 or parsed.current_outstanding_principal_minor != expected_after:
        raise OriginatorClaimsValidationError(
            "Replacement CSV outstanding principal does not reconcile to this repayment."
        )
    holding_model = apps.get_model("holdings", "InvestorLoanHolding")
    holdings = list(
        holding_model.objects.select_for_update()
        .filter(loan_id=loan.id, status="active", current_principal_minor__gt=0)
        .order_by("assignment_effective_at", "created_at", "id")
    )
    holding_total = sum(int(holding.current_principal_minor) for holding in holdings)
    if holding_total + int(profile.unsold_principal_minor) != before_principal:
        raise OriginatorClaimsValidationError(
            "Investor holdings and originator principal do not reconcile to the loan."
        )
    accrual_start = _repayment_accrual_start(
        loan_import=current_import,
        value_date=command.value_date,
    )
    plan, originator_components = _originator_repayment_plan(
        holdings=holdings,
        originator_principal_minor=int(profile.unsold_principal_minor),
        skin_in_the_game_bps=int(loan.skin_in_the_game_bps),
        principal_minor=payment.principal_minor,
        interest_minor=payment.interest_minor,
        penalty_minor=payment.penalty_minor,
        value_date=command.value_date,
        accrual_start_date=accrual_start,
        currency=str(loan.currency_id),
        distribution_model=str(profile.distribution_model),
        investor_interest_participation_bps=int(profile.investor_interest_participation_bps),
        investor_penalty_participation_bps=int(profile.investor_penalty_participation_bps),
    )
    originator_principal_before = int(profile.unsold_principal_minor)
    originator_principal_after = (
        originator_principal_before - originator_components["principal_minor"]
    )
    if originator_principal_after < 0:
        raise OriginatorClaimsValidationError(
            "Repayment principal allocation exceeds the originator-owned portion."
        )
    originator_payable = sum(originator_components.values())
    platform_costs_minor = waterfall.costs_minor
    investor_distributed = sum(line.amount_minor for line in plan)
    repayment_id = _operation_uuid(
        "originator-borrower-repayment",
        f"{command.loan_id}:{idempotency_key}",
    )
    ledger = import_module("backend.apps.ledger.services")
    ledger_result = ledger.declare_originator_borrower_repayment_ledger(
        ledger.DeclareOriginatorBorrowerRepaymentLedgerCommand(
            actor=command.actor,
            repayment_id=str(repayment_id),
            loan_id=str(loan.id),
            originator_id=str(profile.originator_id),
            amount_minor=payment.total_minor,
            originator_payable_minor=originator_payable,
            platform_costs_minor=platform_costs_minor,
            currency=str(loan.currency_id),
            booking_date=command.booking_date,
            value_date=command.value_date,
            collection_account_identifier=command.collection_account_identifier,
            payer_name=command.payer_name,
            payer_account_identifier=command.payer_account_identifier,
            bank_reference=command.bank_reference,
            payment_reference=command.bank_payment_reference,
            evidence_reference=command.evidence_reference,
            notes=command.notes,
            source_type="originator_borrower_repayment",
            source_id=str(repayment_id),
            distribution_lines=[
                ledger.OriginatorRepaymentCreditLineCommand(
                    investor_user_id=line.investor_user_id,
                    holding_id=str(line.holding.pk),
                    amount_minor=line.amount_minor,
                    principal_minor=line.principal_minor,
                    interest_minor=line.interest_minor,
                    penalty_minor=line.penalty_minor,
                    metadata={"payment_reference": payment_reference},
                )
                for line in plan
            ],
            idempotency_key=f"originator-repayment-bank:{idempotency_key}",
        )
    )
    revision = profile.schedule_revision + 1
    loan_import = _persist_import_revision(
        actor=command.actor,
        loan=loan,
        revision=revision,
        parsed=parsed,
        as_of_date=command.as_of_date,
        source_filename=command.source_filename,
        csv_content=command.csv_content,
        validation_summary={
            "maturity_date": parsed.maturity_date.isoformat(),
            "recorded_payment_reference": payment_reference,
            "previous_revision": profile.schedule_revision,
        },
    )
    repayment = OriginatorBorrowerRepayment.objects.create(
        id=repayment_id,
        loan_profile=profile,
        loan_import=loan_import,
        payment_reference=payment.reference,
        payment_type=payment.payment_type,
        currency=loan.currency,
        principal_minor=payment.principal_minor,
        interest_minor=payment.interest_minor,
        penalty_minor=payment.penalty_minor,
        fee_minor=payment.fee_minor,
        amount_minor=payment.total_minor,
        investor_distributed_minor=investor_distributed,
        originator_payable_minor=originator_payable,
        platform_costs_minor=platform_costs_minor,
        principal_before_minor=before_principal,
        principal_after_minor=expected_after,
        originator_principal_before_minor=originator_principal_before,
        originator_principal_after_minor=originator_principal_after,
        booking_date=command.booking_date,
        value_date=command.value_date,
        bank_operation=ledger_result.bank_operation,
        journal_entry=ledger_result.journal_entry,
        created_by_admin_id=command.actor.pk,
        evidence_reference=command.evidence_reference.strip(),
        notes=command.notes.strip(),
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        metadata={
            "accrual_start_date": accrual_start.isoformat(),
            "schedule_revision": revision,
            "originator_components": originator_components,
            "payment_waterfall_version": PAYMENT_WATERFALL_VERSION,
            "payment_waterfall_order": list(PAYMENT_WATERFALL_ORDER),
            "platform_costs_minor": platform_costs_minor,
            "distribution_model": profile.distribution_model,
            "investor_interest_participation_bps": int(profile.investor_interest_participation_bps),
            "investor_penalty_participation_bps": int(profile.investor_penalty_participation_bps),
        },
    )
    credit_by_index = {credit.line_index: credit for credit in ledger_result.balance_credits}
    distribution_records: list[InvestorOriginatorRepaymentDistributionLine] = []
    for index, line in enumerate(plan):
        credit = credit_by_index[index]
        _record_originator_holding_repayment(
            actor=command.actor,
            repayment_id=str(repayment.id),
            line=line,
        )
        distribution_records.append(
            InvestorOriginatorRepaymentDistributionLine(
                repayment=repayment,
                holding=line.holding,
                investor_user_id=line.investor_user_id,
                currency=loan.currency,
                balance_lot=credit.balance_lot,
                amount_minor=line.amount_minor,
                principal_minor=line.principal_minor,
                interest_minor=line.interest_minor,
                penalty_minor=line.penalty_minor,
                current_principal_before_minor=line.principal_before_minor,
                current_principal_after_minor=line.principal_after_minor,
                metadata={"payment_reference": payment_reference},
            )
        )
    InvestorOriginatorRepaymentDistributionLine.objects.bulk_create(distribution_records)
    profile.current_import = loan_import
    profile.schedule_revision = revision
    profile.current_outstanding_principal_minor = expected_after
    profile.unsold_principal_minor = originator_principal_after
    profile.maturity_date = parsed.maturity_date
    profile_fields = [
        "current_import",
        "schedule_revision",
        "current_outstanding_principal_minor",
        "unsold_principal_minor",
        "maturity_date",
        "updated_at",
    ]
    previous_status = str(loan.status)
    if expected_after == 0:
        loan.status = "repaid"
        profile.opportunity_status = OriginatorOpportunityStatus.CLOSED
        profile.closed_at = now_utc()
        profile.close_reason = "repaid"
        profile_fields.extend(["opportunity_status", "closed_at", "close_reason"])
    elif parsed.maturity_date <= command.as_of_date + timedelta(days=30):
        profile.opportunity_status = OriginatorOpportunityStatus.CLOSED
        profile.closed_at = now_utc()
        profile.close_reason = "within_30_days_of_maturity"
        profile_fields.extend(["opportunity_status", "closed_at", "close_reason"])
    elif (
        profile.opportunity_status == OriginatorOpportunityStatus.OPEN
        and originator_sellable_principal_minor(profile) == 0
    ):
        profile.opportunity_status = OriginatorOpportunityStatus.CLOSED
        profile.closed_at = now_utc()
        profile.close_reason = "skin_in_the_game_floor_reached"
        profile_fields.extend(["opportunity_status", "closed_at", "close_reason"])
    profile.save(update_fields=profile_fields)
    investor_principal_repaid = sum(line.principal_minor for line in plan)
    loan.committed_principal_minor -= investor_principal_repaid
    if loan.committed_principal_minor < 0:
        raise OriginatorClaimsValidationError(
            "Repayment would underflow committed investor principal."
        )
    future_rows = [row for row in parsed.schedule_rows if row.due_date > command.as_of_date]
    loan.schedule_version = revision
    loan.total_scheduled_principal_minor = sum(row.principal_minor for row in future_rows)
    loan.total_scheduled_interest_minor = sum(row.interest_minor for row in future_rows)
    loan.save(
        update_fields=[
            "status",
            "committed_principal_minor",
            "schedule_version",
            "total_scheduled_principal_minor",
            "total_scheduled_interest_minor",
            "updated_at",
        ]
    )
    loan_event_model = apps.get_model("loans", "LoanEvent")
    loan_event_model.objects.create(
        loan=loan,
        event_type=("servicing_status_changed" if previous_status != loan.status else "updated"),
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        previous_status=previous_status,
        new_status=str(loan.status),
        note="Originator-loan borrower repayment recorded.",
        metadata={
            "originator_repayment_id": str(repayment.id),
            "payment_reference": payment_reference,
            "schedule_revision": revision,
        },
    )
    secondary = import_module("backend.apps.secondary_market.services")
    secondary.refresh_open_secondary_market_listings_for_loan(
        actor=command.actor,
        loan=loan,
        as_of_date=command.value_date,
        source_type="originator_borrower_repayment",
        source_id=str(repayment.id),
    )
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.REPAYMENT_RECORDED,
        originator=profile.originator,
        loan_id=loan.id,
        metadata={
            "repayment_id": str(repayment.id),
            "payment_reference": payment_reference,
            "amount_minor": payment.total_minor,
            "investor_distributed_minor": investor_distributed,
            "originator_payable_minor": originator_payable,
            "schedule_revision": revision,
        },
    )
    email_totals: dict[str, dict[str, int]] = {}
    for distribution in distribution_records:
        totals = email_totals.setdefault(
            str(distribution.investor_user_id),
            {"amount_minor": 0, "principal_minor": 0, "interest_minor": 0, "penalty_minor": 0},
        )
        totals["amount_minor"] += int(distribution.amount_minor)
        totals["principal_minor"] += int(distribution.principal_minor)
        totals["interest_minor"] += int(distribution.interest_minor)
        totals["penalty_minor"] += int(distribution.penalty_minor)
    for investor_user_id, totals in email_totals.items():
        repayment_currency = str(loan.currency_id)
        total_display = format_amount_minor(totals["amount_minor"], repayment_currency)
        principal_display = format_amount_minor(totals["principal_minor"], repayment_currency)
        interest_display = format_amount_minor(totals["interest_minor"], repayment_currency)
        penalty_display = format_amount_minor(totals["penalty_minor"], repayment_currency)
        _enqueue_investor_email(
            investor_user_id=investor_user_id,
            topic="email.originator_claim_repayment_credited",
            subject="BANXUM loan claim repayment credited",
            body_text=(
                f"A borrower repayment for {loan.title} was credited to your BANXUM balance.\n"
                f"Total credited: {total_display}.\n"
                f"Principal: {principal_display}.\n"
                f"Interest: {interest_display}.\n"
                f"Penalty: {penalty_display}.\n"
                f"Value date: {command.value_date.isoformat()}."
            ),
            template_key="originator_claim.repayment_credited.v1",
            idempotency_key=(f"originator-repayment-email:{repayment.id}:{investor_user_id}"),
            metadata={
                "repayment_id": str(repayment.id),
                "loan_id": str(loan.id),
                "loan_title": str(loan.title),
                "currency": str(loan.currency_id),
                **totals,
                "value_date": command.value_date.isoformat(),
            },
        )
    return cast(OriginatorBorrowerRepayment, repayment)


def list_outstanding_originator_settlements(*, actor: Model) -> list[dict[str, Any]]:
    _require_admin(actor)
    purchases = (
        OriginatorClaimPurchase.objects.filter(settlement_link__isnull=True)
        .select_related("loan_profile__originator", "currency")
        .order_by("purchased_at", "id")
    )
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for purchase in purchases:
        key = (str(purchase.loan_profile.originator_id), str(purchase.currency_id))
        row = grouped.setdefault(
            key,
            {
                "originator_id": key[0],
                "originator_name": purchase.loan_profile.originator.legal_name,
                "currency": key[1],
                "amount_minor": 0,
                "purchase_amount_minor": 0,
                "servicing_amount_minor": 0,
                "purchase_count": 0,
                "repayment_count": 0,
                "purchase_ids": [],
                "repayment_ids": [],
                "oldest_purchased_at": purchase.purchased_at,
                "settlement_due_at": purchase.purchased_at + timedelta(days=5),
                "task_due_at": purchase.purchased_at + timedelta(days=3),
            },
        )
        row["amount_minor"] += int(purchase.originator_payable_minor)
        row["purchase_amount_minor"] += int(purchase.originator_payable_minor)
        row["purchase_count"] += 1
        row["purchase_ids"].append(str(purchase.id))
    repayments = (
        OriginatorBorrowerRepayment.objects.filter(
            settlement_link__isnull=True,
            originator_payable_minor__gt=0,
        )
        .select_related("loan_profile__originator", "currency")
        .order_by("created_at", "id")
    )
    for repayment in repayments:
        key = (str(repayment.loan_profile.originator_id), str(repayment.currency_id))
        row = grouped.setdefault(
            key,
            {
                "originator_id": key[0],
                "originator_name": repayment.loan_profile.originator.legal_name,
                "currency": key[1],
                "amount_minor": 0,
                "purchase_amount_minor": 0,
                "servicing_amount_minor": 0,
                "purchase_count": 0,
                "repayment_count": 0,
                "purchase_ids": [],
                "repayment_ids": [],
                "oldest_purchased_at": repayment.created_at,
                "settlement_due_at": repayment.created_at + timedelta(days=5),
                "task_due_at": repayment.created_at + timedelta(days=3),
            },
        )
        row["amount_minor"] += int(repayment.originator_payable_minor)
        row["servicing_amount_minor"] += int(repayment.originator_payable_minor)
        row["repayment_count"] += 1
        row["repayment_ids"].append(str(repayment.id))
        if repayment.created_at < row["oldest_purchased_at"]:
            row["oldest_purchased_at"] = repayment.created_at
            row["settlement_due_at"] = repayment.created_at + timedelta(days=5)
            row["task_due_at"] = repayment.created_at + timedelta(days=3)
    return sorted(
        grouped.values(),
        key=lambda row: (row["oldest_purchased_at"], row["originator_name"]),
    )


def _settlement_request_fingerprint(
    command: FinalizeOriginatorSettlementCommand,
    *,
    purchase_ids: list[str],
    repayment_ids: list[str],
    amount_minor: int,
    purchase_amount_minor: int,
    servicing_amount_minor: int,
) -> str:
    return _quote_fingerprint(
        {
            "originator_id": str(command.originator_id),
            "currency": command.currency.strip().upper(),
            "purchase_ids": purchase_ids,
            "repayment_ids": repayment_ids,
            "amount_minor": amount_minor,
            "purchase_amount_minor": purchase_amount_minor,
            "servicing_amount_minor": servicing_amount_minor,
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "payment_reference": command.payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "notes": command.notes.strip(),
            "idempotency_key": command.idempotency_key.strip(),
        }
    )


def _existing_settlement(
    *,
    idempotency_key: str,
    expected_fingerprint: str | None = None,
) -> OriginatorSettlement | None:
    settlement = OriginatorSettlement.objects.filter(idempotency_key=idempotency_key).first()
    if settlement is None:
        return None
    if expected_fingerprint and settlement.request_fingerprint != expected_fingerprint:
        raise OriginatorClaimsValidationError(
            "Idempotency key was already used for a different originator settlement."
        )
    return cast(OriginatorSettlement, settlement)


@transaction.atomic
def finalize_originator_settlement(
    command: FinalizeOriginatorSettlementCommand,
) -> OriginatorSettlement:
    _require_admin(command.actor)
    idempotency_key = _required(command.idempotency_key, "Idempotency key")
    if len(idempotency_key) > 160:
        raise OriginatorClaimsValidationError("Idempotency key cannot exceed 160 characters.")
    existing = _existing_settlement(idempotency_key=idempotency_key)
    if existing is not None:
        return existing
    originator = LoanOriginator.objects.select_for_update().filter(id=command.originator_id).first()
    if originator is None:
        raise OriginatorClaimsValidationError("Loan Originator does not exist.")
    currency_code = command.currency.strip().upper()
    requested_ids = sorted(
        {str(item).strip() for item in command.purchase_ids if str(item).strip()}
    )
    requested_repayment_ids = sorted(
        {str(item).strip() for item in command.repayment_ids if str(item).strip()}
    )
    if not requested_ids and not requested_repayment_ids:
        raise OriginatorClaimsValidationError(
            "At least one purchase or servicing repayment must be settled."
        )
    purchases = list(
        OriginatorClaimPurchase.objects.select_for_update()
        .select_related("loan_profile", "currency")
        .filter(id__in=requested_ids)
        .order_by("purchased_at", "id")
    )
    if len(purchases) != len(requested_ids):
        raise OriginatorClaimsValidationError("One or more settlement purchases do not exist.")
    for purchase in purchases:
        if str(purchase.loan_profile.originator_id) != str(originator.id):
            raise OriginatorClaimsValidationError(
                "All settlement purchases must belong to the selected Loan Originator."
            )
        if str(purchase.currency_id) != currency_code:
            raise OriginatorClaimsValidationError(
                "All settlement purchases must use the selected currency."
            )
        if OriginatorSettlementPurchase.objects.filter(purchase=purchase).exists():
            raise OriginatorClaimsValidationError("A selected purchase is already settled.")
    repayments = list(
        OriginatorBorrowerRepayment.objects.select_for_update()
        .select_related("loan_profile", "currency")
        .filter(id__in=requested_repayment_ids)
        .order_by("created_at", "id")
    )
    if len(repayments) != len(requested_repayment_ids):
        raise OriginatorClaimsValidationError("One or more servicing repayments do not exist.")
    for repayment in repayments:
        if str(repayment.loan_profile.originator_id) != str(originator.id):
            raise OriginatorClaimsValidationError(
                "All servicing repayments must belong to the selected Loan Originator."
            )
        if str(repayment.currency_id) != currency_code:
            raise OriginatorClaimsValidationError(
                "All servicing repayments must use the selected currency."
            )
        if OriginatorSettlementRepayment.objects.filter(repayment=repayment).exists():
            raise OriginatorClaimsValidationError(
                "A selected servicing repayment is already settled."
            )
    purchase_amount_minor = sum(int(purchase.originator_payable_minor) for purchase in purchases)
    servicing_amount_minor = sum(
        int(repayment.originator_payable_minor) for repayment in repayments
    )
    amount_minor = purchase_amount_minor + servicing_amount_minor
    if amount_minor <= 0:
        raise OriginatorClaimsValidationError("Originator settlement amount must be positive.")
    fingerprint = _settlement_request_fingerprint(
        command,
        purchase_ids=requested_ids,
        repayment_ids=requested_repayment_ids,
        amount_minor=amount_minor,
        purchase_amount_minor=purchase_amount_minor,
        servicing_amount_minor=servicing_amount_minor,
    )
    existing = _existing_settlement(
        idempotency_key=idempotency_key,
        expected_fingerprint=fingerprint,
    )
    if existing is not None:
        return existing
    settlement_id = _operation_uuid(
        "originator-settlement",
        f"{originator.id}:{idempotency_key}",
    )
    ledger = import_module("backend.apps.ledger.services")
    ledger_result = ledger.finalize_originator_settlement_ledger(
        ledger.FinalizeOriginatorSettlementLedgerCommand(
            actor=command.actor,
            settlement_id=str(settlement_id),
            originator_id=str(originator.id),
            amount_minor=amount_minor,
            purchase_amount_minor=purchase_amount_minor,
            servicing_amount_minor=servicing_amount_minor,
            currency=currency_code,
            booking_date=command.booking_date,
            value_date=command.value_date,
            collection_account_identifier=command.collection_account_identifier,
            payee_name=originator.settlement_account_name,
            payee_account_identifier=originator.settlement_iban,
            purchase_ids=requested_ids,
            repayment_ids=requested_repayment_ids,
            bank_reference=command.bank_reference,
            payment_reference=command.payment_reference,
            evidence_reference=command.evidence_reference,
            notes=command.notes,
            idempotency_key=f"originator-settlement-bank:{idempotency_key}",
        )
    )
    now = now_utc()
    try:
        with transaction.atomic():
            settlement = cast(
                OriginatorSettlement,
                OriginatorSettlement.objects.create(
                    id=settlement_id,
                    originator=originator,
                    currency_id=currency_code,
                    amount_minor=amount_minor,
                    purchase_amount_minor=purchase_amount_minor,
                    servicing_amount_minor=servicing_amount_minor,
                    purchase_count=len(purchases),
                    repayment_count=len(repayments),
                    bank_operation=ledger_result.bank_operation,
                    journal_entry=ledger_result.journal_entry,
                    settled_by_admin_id=command.actor.pk,
                    settled_at=now,
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    metadata={
                        "purchase_ids": requested_ids,
                        "repayment_ids": requested_repayment_ids,
                        "oldest_source_at": min(
                            [purchase.purchased_at for purchase in purchases]
                            + [repayment.created_at for repayment in repayments]
                        ).isoformat(),
                    },
                ),
            )
    except IntegrityError:
        existing_after_race = _existing_settlement(
            idempotency_key=idempotency_key,
            expected_fingerprint=fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    OriginatorSettlementPurchase.objects.bulk_create(
        [
            OriginatorSettlementPurchase(
                settlement=settlement,
                purchase=purchase,
                amount_minor=purchase.originator_payable_minor,
            )
            for purchase in purchases
        ]
    )
    OriginatorSettlementRepayment.objects.bulk_create(
        [
            OriginatorSettlementRepayment(
                settlement=settlement,
                repayment=repayment,
                amount_minor=repayment.originator_payable_minor,
            )
            for repayment in repayments
        ]
    )
    _record_event(
        actor=command.actor,
        event_type=OriginatorClaimEventType.SETTLEMENT_RECORDED,
        originator=originator,
        metadata={
            "settlement_id": str(settlement.id),
            "currency": currency_code,
            "amount_minor": amount_minor,
            "purchase_amount_minor": purchase_amount_minor,
            "servicing_amount_minor": servicing_amount_minor,
            "purchase_count": len(purchases),
            "repayment_count": len(repayments),
            "bank_operation_id": str(ledger_result.bank_operation.id),
            "journal_entry_id": str(ledger_result.journal_entry.id),
        },
    )
    admin_ops = import_module("backend.apps.admin_ops.services")
    task = (
        apps.get_model("admin_ops", "AdminTask")
        .objects.filter(
            task_type="originator_settlement",
            related_object_type="LoanOriginatorSettlementQueue",
            related_object_id=f"{originator.id}:{currency_code}",
        )
        .first()
    )
    if task is not None and task.status not in {"resolved", "cancelled"}:
        admin_ops.update_admin_task(
            admin_ops.UpdateAdminTaskCommand(
                actor=command.actor,
                task_id=str(task.id),
                status="resolved",
                completion_note=f"Settled in batch {settlement.id}.",
            )
        )
    return settlement


def sync_originator_settlement_tasks(
    *,
    actor: Model,
    as_of: Any | None = None,
) -> list[Any]:
    _require_admin(actor)
    current = as_of or now_utc()
    admin_ops = import_module("backend.apps.admin_ops.services")
    task_model = apps.get_model("admin_ops", "AdminTask")
    tasks: list[Any] = []
    for row in list_outstanding_originator_settlements(actor=actor):
        if row["task_due_at"] > current:
            continue
        related_id = f"{row['originator_id']}:{row['currency']}"
        title = f"Settle {row['currency']} payable to {row['originator_name']}"
        notes = (
            f"{row['purchase_count']} unsettled claim purchases and "
            f"{row['repayment_count']} unsettled servicing receipts; "
            f"amount {row['amount_minor']} minor units. "
            f"Oldest unsettled source: {row['oldest_purchased_at'].isoformat()}. "
            "Settlement must occur no later than five calendar days after receipt."
        )
        task = task_model.objects.filter(
            task_type="originator_settlement",
            related_object_type="LoanOriginatorSettlementQueue",
            related_object_id=related_id,
        ).first()
        if task is None:
            task = admin_ops.create_admin_task(
                admin_ops.CreateAdminTaskCommand(
                    actor=actor,
                    task_type="originator_settlement",
                    title=title,
                    priority=("urgent" if row["settlement_due_at"] <= current else "high"),
                    due_at=row["settlement_due_at"],
                    notes=notes,
                    related_object_type="LoanOriginatorSettlementQueue",
                    related_object_id=related_id,
                )
            )
        elif task.status in {"resolved", "cancelled"}:
            task = admin_ops.update_admin_task(
                admin_ops.UpdateAdminTaskCommand(
                    actor=actor,
                    task_id=str(task.id),
                    status="open",
                    title=title,
                    priority=("urgent" if row["settlement_due_at"] <= current else "high"),
                    due_at=row["settlement_due_at"],
                    notes=notes,
                )
            )
        tasks.append(task)
    return tasks


@transaction.atomic
def _scan_originator_profile_lifecycle(
    *,
    actor: Model,
    profile_id: str,
    as_of_date: date,
) -> dict[str, str] | None:
    loan_id = (
        OriginatorLoanProfile.objects.filter(id=profile_id)
        .values_list("loan_id", flat=True)
        .first()
    )
    if loan_id is None:
        return None
    loan_model = apps.get_model("loans", "Loan")
    loan = loan_model.objects.select_for_update().filter(id=loan_id).first()
    if loan is None:
        return None
    profile = _locked_profile_for_loan(
        str(loan_id),
        "originator",
        "current_import",
    )
    previous_loan_status = str(loan.status)
    days_past_due = _originator_days_past_due(
        profile,
        as_of_date=as_of_date,
    )
    if previous_loan_status in {"active", "late"}:
        new_loan_status = (
            "defaulted" if days_past_due >= 16 else ("late" if days_past_due >= 5 else "active")
        )
        if new_loan_status != previous_loan_status:
            loan.status = new_loan_status
            loan.save(update_fields=["status", "updated_at"])
            loan_event_model = apps.get_model("loans", "LoanEvent")
            loan_event_model.objects.create(
                loan=loan,
                event_type="servicing_status_changed",
                actor_user_id=actor.pk,
                actor_account_type=str(getattr(actor, "account_type", "")),
                previous_status=previous_loan_status,
                new_status=new_loan_status,
                note="Originator-loan servicing status scan.",
                metadata={
                    "as_of_date": as_of_date.isoformat(),
                    "days_past_due": days_past_due,
                },
            )
            _record_event(
                actor=actor,
                event_type=OriginatorClaimEventType.SERVICING_STATUS_CHANGED,
                originator=profile.originator,
                loan_id=profile.loan_id,
                metadata={
                    "previous_status": previous_loan_status,
                    "new_status": new_loan_status,
                    "as_of_date": as_of_date.isoformat(),
                    "days_past_due": days_past_due,
                },
            )
            secondary = import_module("backend.apps.secondary_market.services")
            secondary.refresh_open_secondary_market_listings_for_loan(
                actor=actor,
                loan=loan,
                as_of_date=as_of_date,
                source_type="originator_servicing_status_scan",
                source_id=(f"{profile.loan_id}:{new_loan_status}:{as_of_date.isoformat()}"),
            )

    # Subscription opportunities leave the marketplace at their funding close and
    # remain ACTIVE only as servicing records. Historical v1 rows retain the old
    # continuously quoted catalogue lifecycle below.
    if _is_par_subscription(profile):
        return None

    reason = ""
    if profile.is_on_hold:
        reason = "administrative_hold"
    elif profile.originator.status != LoanOriginatorStatus.ACTIVE:
        reason = "originator_not_active"
    elif profile.current_outstanding_principal_minor <= 0 or loan.status == "repaid":
        reason = "repaid"
    elif originator_sellable_principal_minor(profile) <= 0:
        reason = "skin_in_the_game_floor_reached"
    elif loan.status in {"late", "defaulted", "written_off", "cancelled"}:
        reason = f"loan_status_{loan.status}"
    elif loan.status != "active":
        reason = f"loan_not_active_{loan.status}"
    elif profile.maturity_date <= as_of_date + timedelta(days=30):
        reason = "maturity_within_30_days"
    if not reason or profile.opportunity_status != OriginatorOpportunityStatus.OPEN:
        return None
    profile.opportunity_status = OriginatorOpportunityStatus.CLOSED
    profile.closed_at = now_utc()
    profile.close_reason = reason
    profile.save(update_fields=["opportunity_status", "closed_at", "close_reason", "updated_at"])
    _record_event(
        actor=actor,
        event_type=OriginatorClaimEventType.OPPORTUNITY_CLOSED,
        originator=profile.originator,
        loan_id=profile.loan_id,
        metadata={"close_reason": reason, "as_of_date": as_of_date.isoformat()},
    )
    return {"loan_id": str(profile.loan_id), "reason": reason}


def scan_originator_opportunity_lifecycle(
    *,
    actor: Model,
    as_of_date: date,
    limit: int = 1000,
) -> list[dict[str, str]]:
    _require_admin(actor)
    if limit < 1 or limit > 5000:
        raise OriginatorClaimsValidationError("Lifecycle scan limit must be between 1 and 5000.")
    profile_rows = list(
        OriginatorLoanProfile.objects.filter(
            Q(opportunity_status=OriginatorOpportunityStatus.OPEN)
            | Q(loan__status__in=["active", "late"])
        )
        .order_by("maturity_date", "id")
        .values(
            "id",
            "loan_id",
            "distribution_model",
            "opportunity_status",
            "funding_deadline",
            "loan__status",
            "loan__committed_principal_minor",
            "is_on_hold",
        )[:limit]
    )
    closed: list[dict[str, str]] = []
    for row in profile_rows:
        is_subscription = row["distribution_model"] == OriginatorDistributionModel.PAR_COMPONENT_V2
        deadline = row["funding_deadline"]
        is_expired_open_round = (
            is_subscription
            and row["opportunity_status"] == OriginatorOpportunityStatus.OPEN
            and row["loan__status"] == "published"
            and deadline is not None
            and as_of_date > deadline
            and not bool(row["is_on_hold"])
        )
        if is_expired_open_round:
            loan_id = str(row["loan_id"])
            resolution_action = (
                "funding-deadline close"
                if int(row["loan__committed_principal_minor"] or 0) > 0
                else "empty-round cancellation"
            )
            try:
                if int(row["loan__committed_principal_minor"] or 0) > 0:
                    close_originator_subscription_round(
                        CloseOriginatorSubscriptionRoundCommand(
                            actor=actor,
                            loan_id=loan_id,
                            as_of_date=as_of_date,
                            close_reason="funding_deadline_reached",
                            idempotency_key=f"originator-round-deadline-close:{loan_id}",
                        )
                    )
                    closed.append({"loan_id": loan_id, "reason": "funding_deadline_reached"})
                else:
                    cancel_originator_subscription(
                        CancelOriginatorSubscriptionCommand(
                            actor=actor,
                            loan_id=loan_id,
                            reason="Funding period ended without an allocated subscription.",
                            investor_message=(
                                "The funding period ended before any balance was allocated. "
                                "No investor money was transferred to the Loan Originator."
                            ),
                            idempotency_key=f"originator-round-empty-cancel:{loan_id}",
                        )
                    )
                    closed.append({"loan_id": loan_id, "reason": "no_subscriptions"})
            except Exception as exc:
                closed.append(
                    mark_originator_funding_close_failed(
                        triggering_actor=actor,
                        loan_id=loan_id,
                        as_of_date=as_of_date,
                        resolution_action=resolution_action,
                        error=exc,
                    )
                )
            continue
        result = _scan_originator_profile_lifecycle(
            actor=actor,
            profile_id=str(row["id"]),
            as_of_date=as_of_date,
        )
        if result is not None:
            closed.append(result)
    return closed
