from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from importlib import import_module
from typing import Any, cast

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model, QuerySet, Sum

from backend.apps.fx.models import (
    FxEvent,
    FxEventType,
    FxExchange,
    FxExternalSettlement,
    FxExternalSettlementExchange,
    FxExternalSettlementStatus,
    FxQuote,
)
from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    is_admin_actor,
    user_can_access_financial_features,
)
from backend.apps.platform_core.domain.money import Money, MoneyError, normalize_currency
from backend.apps.platform_core.domain.time import business_timezone, now_utc, to_business_time
from backend.apps.platform_core.models import Currency
from backend.apps.platform_core.selectors.settings import get_platform_setting_value
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import DomainEventCommand, record_domain_event
from backend.apps.platform_core.services.sensitive_actions import (
    FX_ACTION,
    SensitiveActionVerificationCommand,
    SensitiveActionVerificationError,
    verify_sensitive_action_code,
)


class FxError(ValueError):
    pass


class FxAuthorizationError(FxError):
    pass


class FxValidationError(FxError):
    pass


MAX_IDEMPOTENCY_KEY_LENGTH = 160
REQUEST_FINGERPRINT_METADATA_KEY = "request_fingerprint"
QUOTE_TTL_SECONDS = 60
DEFAULT_FX_PLATFORM_FEE_BPS = 150
DEFAULT_DAILY_LIMIT_CHF_MINOR = 100_000_00
DEFAULT_ENABLED_PAIRS = ("CHF/EUR", "EUR/CHF")
DEFAULT_PAIR_RATE_BOUNDS = {
    "CHF/EUR": {"min": "0.500000", "max": "2.000000"},
    "EUR/CHF": {"min": "0.500000", "max": "2.000000"},
}
DEFAULT_PROVIDER_RATE_FRESHNESS_SECONDS = 300
PREVIOUS_DAY_AVERAGE_MAX_DEVIATION_BPS = 500
LOCAL_FX_ENVIRONMENTS = {"local", "test"}
MOCK_FX_PROVIDERS = {"mock", "local"}
YAHOO_FINANCE_PROVIDER = "yahoo_finance"
DEFAULT_YAHOO_SYMBOLS = {"CHF/EUR": "CHFEUR=X", "EUR/CHF": "EURCHF=X"}


@dataclass(frozen=True, slots=True)
class ProviderRate:
    provider: str
    rate: Decimal
    observed_at: datetime
    previous_day_average_rate: Decimal | None = None
    provider_quote_id: str = ""
    raw_payload_reference: str = ""


@dataclass(frozen=True, slots=True)
class IssueFxQuoteCommand:
    actor: Model
    source_currency: str
    target_currency: str
    source_amount_minor: int
    provider_rate: ProviderRate
    idempotency_key: str
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExecuteFxQuoteCommand:
    actor: Model
    quote_id: str
    idempotency_key: str
    sensitive_action_code_id: str = ""
    sensitive_action_code: str = ""
    as_of: datetime | None = None
    ip_address: str | None = None
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class DeclareFxExternalSettlementCommand:
    actor: Model
    sold_currency: str
    bought_currency: str
    sold_amount_minor: int
    bought_amount_minor: int
    start_date: date
    end_date: date
    booking_date: date
    value_date: date
    collection_account_identifier: str
    bank_reference: str = ""
    payment_reference: str = ""
    evidence_reference: str = ""
    notes: str = ""
    idempotency_key: str = ""
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class FxDeltaReport:
    start_date: date
    end_date: date
    exchange_count: int
    source_sold_by_currency_minor: dict[str, int]
    gross_target_bought_by_currency_minor: dict[str, int]
    target_credited_by_currency_minor: dict[str, int]
    fees_by_currency_minor: dict[str, int]
    net_external_settlement_by_currency_minor: dict[str, int]


@dataclass(frozen=True, slots=True)
class FxRealizedSettlementReport:
    start_date: date
    end_date: date
    settlement_count: int
    expected_sold_by_currency_minor: dict[str, int]
    actual_sold_by_currency_minor: dict[str, int]
    expected_bought_by_currency_minor: dict[str, int]
    actual_bought_by_currency_minor: dict[str, int]
    fees_by_currency_minor: dict[str, int]
    residual_by_currency_minor: dict[str, int]


@dataclass(frozen=True, slots=True)
class FxExpectedSettlementBatch:
    exchanges: list[FxExchange]
    expected_sold_amount_minor: int
    expected_bought_amount_minor: int
    expected_target_credited_minor: int
    expected_fee_minor: int


def _ledger_services() -> Any:
    return import_module("backend.apps.ledger.services")


def _stable_json_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _clean_idempotency_key(value: str) -> str:
    key = value.strip()
    if not key:
        raise FxValidationError("Idempotency key is required.")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise FxValidationError(
            f"Idempotency key cannot exceed {MAX_IDEMPOTENCY_KEY_LENGTH} characters."
        )
    return key


def _enabled_currency(currency_code: str) -> Currency:
    try:
        code = normalize_currency(currency_code)
    except MoneyError as exc:
        raise FxValidationError(str(exc)) from exc
    currency = Currency.objects.filter(code=code, is_enabled=True).first()
    if currency is None:
        raise FxValidationError(f"Currency is not enabled: {code}")
    return currency


def _validate_money(amount_minor: int, currency_code: str, label: str) -> int:
    try:
        Money(amount_minor, currency_code)
    except MoneyError as exc:
        raise FxValidationError(str(exc)) from exc
    if amount_minor <= 0:
        raise FxValidationError(f"{label} must be positive.")
    return amount_minor


def _as_decimal(value: Any, label: str) -> Decimal:
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise FxValidationError(f"{label} must be a valid decimal value.") from exc
    if not decimal.is_finite():
        raise FxValidationError(f"{label} must be finite.")
    return decimal


def _round_minor(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _minor_factor(currency: Currency) -> Decimal:
    return Decimal(10) ** int(currency.minor_units)


def _pair_key(source_currency: str, target_currency: str) -> str:
    return f"{source_currency}/{target_currency}"


def _enabled_pairs() -> set[str]:
    configured = get_platform_setting_value("fx.enabled_pairs", list(DEFAULT_ENABLED_PAIRS))
    if not isinstance(configured, list):
        return set(DEFAULT_ENABLED_PAIRS)
    return {str(pair).strip().upper() for pair in configured if str(pair).strip()}


def _platform_fee_bps() -> int:
    value = get_platform_setting_value("fx.platform_fee_bps", DEFAULT_FX_PLATFORM_FEE_BPS)
    if type(value) is not int:
        return DEFAULT_FX_PLATFORM_FEE_BPS
    return max(0, value)


def _daily_limit_chf_minor() -> int:
    value = get_platform_setting_value("fx.daily_limit_chf_minor", DEFAULT_DAILY_LIMIT_CHF_MINOR)
    if type(value) is not int or value <= 0:
        return DEFAULT_DAILY_LIMIT_CHF_MINOR
    return value


def _pair_rate_bounds(pair: str) -> tuple[Decimal, Decimal] | None:
    configured = get_platform_setting_value("fx.pair_rate_bounds", DEFAULT_PAIR_RATE_BOUNDS)
    if not isinstance(configured, dict):
        configured = DEFAULT_PAIR_RATE_BOUNDS
    bounds = configured.get(pair)
    if not isinstance(bounds, dict):
        return None
    minimum = _as_decimal(bounds.get("min"), "FX minimum pair rate")
    maximum = _as_decimal(bounds.get("max"), "FX maximum pair rate")
    if minimum <= 0 or maximum <= minimum:
        raise FxValidationError("FX pair rate bounds are invalid.")
    return minimum, maximum


def _quote_request_fingerprint(
    command: IssueFxQuoteCommand,
    *,
    source_currency_code: str,
    target_currency_code: str,
    source_amount_minor: int,
    fee_bps: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "actor_id": str(command.actor.pk),
            "source_currency": source_currency_code,
            "target_currency": target_currency_code,
            "source_amount_minor": source_amount_minor,
            "provider": command.provider_rate.provider,
            "rate": str(command.provider_rate.rate),
            "previous_day_average_rate": str(
                command.provider_rate.previous_day_average_rate or ""
            ),
            "provider_quote_id": command.provider_rate.provider_quote_id,
            "provider_observed_at": command.provider_rate.observed_at.isoformat(),
            "fee_bps": fee_bps,
            "idempotency_key": idempotency_key,
        }
    )


def _exchange_request_fingerprint(
    command: ExecuteFxQuoteCommand,
    *,
    quote: FxQuote,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "actor_id": str(command.actor.pk),
            "quote_id": str(quote.id),
            "investor_user_id": str(quote.investor_user_id),
            "source_currency": quote.source_currency_id,
            "target_currency": quote.target_currency_id,
            "source_amount_minor": quote.source_amount_minor,
            "gross_target_amount_minor": quote.gross_target_amount_minor,
            "target_amount_minor": quote.target_amount_minor,
            "fee_minor": quote.fee_minor,
            "rate": str(quote.rate),
            "idempotency_key": idempotency_key,
        }
    )


def _external_settlement_request_fingerprint(
    command: DeclareFxExternalSettlementCommand,
    *,
    sold_currency_code: str,
    bought_currency_code: str,
    sold_amount_minor: int,
    bought_amount_minor: int,
    idempotency_key: str,
) -> str:
    return _stable_json_fingerprint(
        {
            "actor_id": str(command.actor.pk),
            "sold_currency": sold_currency_code,
            "bought_currency": bought_currency_code,
            "sold_amount_minor": sold_amount_minor,
            "bought_amount_minor": bought_amount_minor,
            "start_date": command.start_date.isoformat(),
            "end_date": command.end_date.isoformat(),
            "booking_date": command.booking_date.isoformat(),
            "value_date": command.value_date.isoformat(),
            "collection_account_identifier": command.collection_account_identifier.strip(),
            "bank_reference": command.bank_reference.strip(),
            "payment_reference": command.payment_reference.strip(),
            "evidence_reference": command.evidence_reference.strip(),
            "notes": command.notes.strip(),
            "idempotency_key": idempotency_key,
        }
    )


def _existing_quote_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> FxQuote | None:
    existing = FxQuote.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(REQUEST_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise FxValidationError("Idempotency key was already used for a different FX quote.")
    return cast(FxQuote, existing)


def _existing_exchange_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> FxExchange | None:
    existing = FxExchange.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(REQUEST_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise FxValidationError("Idempotency key was already used for a different FX exchange.")
    return cast(FxExchange, existing)


def _existing_external_settlement_for_idempotency(
    idempotency_key: str,
    *,
    expected_fingerprint: str,
) -> FxExternalSettlement | None:
    existing = FxExternalSettlement.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if (
        cast(dict[str, Any], existing.metadata).get(REQUEST_FINGERPRINT_METADATA_KEY)
        != expected_fingerprint
    ):
        raise FxValidationError(
            "Idempotency key was already used for a different FX external settlement."
        )
    return cast(FxExternalSettlement, existing)


def _require_financial_actor(actor: Model) -> None:
    if not user_can_access_financial_features(actor):
        raise FxAuthorizationError("Investor account cannot access FX features.")


def _chf_equivalent_minor(
    *,
    source_currency_code: str,
    target_currency_code: str,
    source_amount_minor: int,
    gross_target_amount_minor: int,
) -> int:
    if source_currency_code == "CHF":
        return source_amount_minor
    if target_currency_code == "CHF":
        return gross_target_amount_minor
    # Launch FX pairs are CHF-based. Cross pairs need a CHF bridge before enablement.
    raise FxValidationError("Daily FX limit currently requires one side of the pair to be CHF.")


def _business_day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min, tzinfo=business_timezone())
    return start, start + timedelta(days=1)


def _business_date_for_timestamp(value: datetime) -> date:
    return to_business_time(value).date()


def _actual_rate(
    *,
    sold_currency: Currency,
    bought_currency: Currency,
    sold_amount_minor: int,
    bought_amount_minor: int,
) -> Decimal:
    sold_major = Decimal(sold_amount_minor) / _minor_factor(sold_currency)
    bought_major = Decimal(bought_amount_minor) / _minor_factor(bought_currency)
    if sold_major <= 0:
        raise FxValidationError("FX external sold amount must be positive.")
    return (bought_major / sold_major).quantize(Decimal("0.000000000001"))


def _exchange_date_range_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    if end_date < start_date:
        raise FxValidationError("End date cannot be before start date.")
    start, _ = _business_day_bounds(start_date)
    _, end = _business_day_bounds(end_date)
    return start, end


def _unsettled_exchanges_in_range(start_date: date, end_date: date) -> QuerySet[FxExchange]:
    start, end = _exchange_date_range_bounds(start_date, end_date)
    return FxExchange.objects.filter(
        executed_at__gte=start,
        executed_at__lt=end,
        settlement_links__isnull=True,
    )


def _expected_pair_batch(
    *,
    sold_currency_code: str,
    bought_currency_code: str,
    start_date: date,
    end_date: date,
) -> FxExpectedSettlementBatch:
    start, end = _exchange_date_range_bounds(start_date, end_date)
    settled_exchange_ids = FxExternalSettlementExchange.objects.values("exchange_id")
    exchanges = list(
        FxExchange.objects.select_for_update()
        .filter(
            source_currency_id=sold_currency_code,
            target_currency_id=bought_currency_code,
            executed_at__gte=start,
            executed_at__lt=end,
        )
        .exclude(id__in=settled_exchange_ids)
        .order_by("executed_at", "id")
    )
    return FxExpectedSettlementBatch(
        exchanges=exchanges,
        expected_sold_amount_minor=sum(exchange.source_amount_minor for exchange in exchanges),
        expected_bought_amount_minor=sum(
            exchange.gross_target_amount_minor for exchange in exchanges
        ),
        expected_target_credited_minor=sum(exchange.target_amount_minor for exchange in exchanges),
        expected_fee_minor=sum(exchange.fee_minor for exchange in exchanges),
    )


def _create_external_settlement_exchange_links(
    *,
    settlement: FxExternalSettlement,
    exchanges: list[FxExchange],
    settled_at: datetime,
) -> None:
    try:
        with transaction.atomic():
            FxExternalSettlementExchange.objects.bulk_create(
                [
                    FxExternalSettlementExchange(
                        external_settlement=settlement,
                        exchange=exchange,
                        source_amount_minor=exchange.source_amount_minor,
                        gross_target_amount_minor=exchange.gross_target_amount_minor,
                        target_amount_minor=exchange.target_amount_minor,
                        fee_minor=exchange.fee_minor,
                        settled_at=settled_at,
                        metadata={
                            "quote_id": str(exchange.quote_id),
                            "source_currency": exchange.source_currency_id,
                            "target_currency": exchange.target_currency_id,
                        },
                    )
                    for exchange in exchanges
                ]
            )
    except IntegrityError as exc:
        raise FxValidationError(
            "One or more FX exchanges in this date range were already settled."
        ) from exc


def _expected_unsettled_totals(
    *,
    sold_currency_code: str,
    bought_currency_code: str,
    start_date: date,
    end_date: date,
) -> tuple[int, int, int, int]:
    start, end = _exchange_date_range_bounds(start_date, end_date)
    aggregate = FxExchange.objects.filter(
        source_currency_id=sold_currency_code,
        target_currency_id=bought_currency_code,
        executed_at__gte=start,
        executed_at__lt=end,
        settlement_links__isnull=True,
    ).aggregate(
        sold=Sum("source_amount_minor"),
        bought=Sum("gross_target_amount_minor"),
        credited=Sum("target_amount_minor"),
        fees=Sum("fee_minor"),
    )
    return (
        int(aggregate["sold"] or 0),
        int(aggregate["bought"] or 0),
        int(aggregate["credited"] or 0),
        int(aggregate["fees"] or 0),
    )


def _daily_executed_chf_equivalent(investor_user_id: str, business_day: date) -> int:
    start, end = _business_day_bounds(business_day)
    aggregate = FxExchange.objects.filter(
        investor_user_id=investor_user_id,
        executed_at__gte=start,
        executed_at__lt=end,
    ).aggregate(total=Sum("limit_chf_equivalent_minor"))
    return int(aggregate["total"] or 0)


def _assert_daily_limit(
    *,
    investor_user_id: str,
    business_day: date,
    requested_chf_equivalent_minor: int,
) -> None:
    already_executed = _daily_executed_chf_equivalent(investor_user_id, business_day)
    limit = _daily_limit_chf_minor()
    if already_executed + requested_chf_equivalent_minor > limit:
        raise FxValidationError("FX daily conversion limit exceeded for this investor.")


def _validate_provider_rate(
    *,
    pair: str,
    rate: Decimal,
    previous_day_average_rate: Decimal | None,
    observed_at: datetime,
    as_of: datetime,
) -> dict[str, Any]:
    sanity: dict[str, Any] = {
        "pair": pair,
        "rate": str(rate),
        "observed_at": observed_at.isoformat(),
        "checks": [],
    }
    if rate <= 0:
        raise FxValidationError("FX provider rate must be positive.")
    max_age = int(
        get_platform_setting_value(
            "fx.provider_rate_freshness_seconds",
            DEFAULT_PROVIDER_RATE_FRESHNESS_SECONDS,
        )
        or DEFAULT_PROVIDER_RATE_FRESHNESS_SECONDS
    )
    age_seconds = abs((as_of - observed_at).total_seconds())
    if age_seconds > max_age:
        raise FxValidationError("FX provider rate is stale.")
    sanity["checks"].append({"name": "freshness", "age_seconds": age_seconds})
    bounds = _pair_rate_bounds(pair)
    if bounds is not None:
        minimum, maximum = bounds
        if rate < minimum or rate > maximum:
            raise FxValidationError("FX provider rate is outside configured pair bounds.")
        sanity["checks"].append({"name": "pair_bounds", "min": str(minimum), "max": str(maximum)})
    if previous_day_average_rate is not None:
        if previous_day_average_rate <= 0:
            raise FxValidationError("Previous-day average FX rate must be positive.")
        deviation_bps = int(
            (
                abs(rate - previous_day_average_rate)
                / previous_day_average_rate
                * Decimal(10_000)
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        if deviation_bps > PREVIOUS_DAY_AVERAGE_MAX_DEVIATION_BPS:
            raise FxValidationError(
                "FX provider rate deviates too far from previous-day average."
            )
        sanity["checks"].append(
            {
                "name": "previous_day_average",
                "previous_day_average_rate": str(previous_day_average_rate),
                "deviation_bps": deviation_bps,
            }
        )
    return sanity


def _calculate_quote_amounts(
    *,
    source_currency: Currency,
    target_currency: Currency,
    source_amount_minor: int,
    rate: Decimal,
    platform_fee_bps: int,
) -> tuple[int, int, int]:
    source_major = Decimal(source_amount_minor) / _minor_factor(source_currency)
    target_minor_decimal = source_major * rate * _minor_factor(target_currency)
    gross_target_amount_minor = _round_minor(target_minor_decimal)
    fee_minor = _round_minor(
        Decimal(gross_target_amount_minor) * Decimal(platform_fee_bps) / Decimal(10_000)
    )
    target_amount_minor = gross_target_amount_minor - fee_minor
    if gross_target_amount_minor <= 0 or target_amount_minor <= 0:
        raise FxValidationError("FX quote target amount is too small after fees.")
    return gross_target_amount_minor, fee_minor, target_amount_minor


@transaction.atomic
def issue_fx_quote(command: IssueFxQuoteCommand) -> FxQuote:
    _require_financial_actor(command.actor)
    source_currency = _enabled_currency(command.source_currency)
    target_currency = _enabled_currency(command.target_currency)
    if source_currency.code == target_currency.code:
        raise FxValidationError("FX source and target currencies must differ.")
    pair = _pair_key(source_currency.code, target_currency.code)
    if pair not in _enabled_pairs():
        raise FxValidationError("FX pair is not enabled.")
    source_amount_minor = _validate_money(
        command.source_amount_minor,
        source_currency.code,
        "FX source amount",
    )
    as_of = command.as_of or now_utc()
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    rate = _as_decimal(command.provider_rate.rate, "FX provider rate")
    previous_average = (
        _as_decimal(command.provider_rate.previous_day_average_rate, "Previous-day average rate")
        if command.provider_rate.previous_day_average_rate is not None
        else None
    )
    sanity_metadata = _validate_provider_rate(
        pair=pair,
        rate=rate,
        previous_day_average_rate=previous_average,
        observed_at=command.provider_rate.observed_at,
        as_of=as_of,
    )
    fee_bps = _platform_fee_bps()
    gross_target_amount_minor, fee_minor, target_amount_minor = _calculate_quote_amounts(
        source_currency=source_currency,
        target_currency=target_currency,
        source_amount_minor=source_amount_minor,
        rate=rate,
        platform_fee_bps=fee_bps,
    )
    limit_chf_equivalent_minor = _chf_equivalent_minor(
        source_currency_code=source_currency.code,
        target_currency_code=target_currency.code,
        source_amount_minor=source_amount_minor,
        gross_target_amount_minor=gross_target_amount_minor,
    )
    request_fingerprint = _quote_request_fingerprint(
        command,
        source_currency_code=source_currency.code,
        target_currency_code=target_currency.code,
        source_amount_minor=source_amount_minor,
        fee_bps=fee_bps,
        idempotency_key=idempotency_key,
    )
    existing = _existing_quote_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    _assert_daily_limit(
        investor_user_id=str(command.actor.pk),
        business_day=_business_date_for_timestamp(as_of),
        requested_chf_equivalent_minor=limit_chf_equivalent_minor,
    )
    metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "raw_payload_reference": command.provider_rate.raw_payload_reference,
    }
    try:
        with transaction.atomic():
            quote = cast(
                FxQuote,
                FxQuote.objects.create(
                    investor_user_id=command.actor.pk,
                    source_currency=source_currency,
                    target_currency=target_currency,
                    source_amount_minor=source_amount_minor,
                    provider=command.provider_rate.provider,
                    provider_quote_id=command.provider_rate.provider_quote_id,
                    rate=rate,
                    previous_day_average_rate=previous_average,
                    platform_fee_bps=fee_bps,
                    gross_target_amount_minor=gross_target_amount_minor,
                    fee_minor=fee_minor,
                    target_amount_minor=target_amount_minor,
                    limit_chf_equivalent_minor=limit_chf_equivalent_minor,
                    issued_at=as_of,
                    expires_at=as_of + timedelta(seconds=QUOTE_TTL_SECONDS),
                    provider_rate_timestamp=command.provider_rate.observed_at,
                    sanity_check_passed=True,
                    sanity_metadata=sanity_metadata,
                    metadata=metadata,
                    idempotency_key=idempotency_key,
                ),
            )
    except IntegrityError:
        existing_after_race = _existing_quote_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    actor_ref = actor_ref_for_user(command.actor)
    event_metadata = {
        "quote_id": str(quote.id),
        "investor_user_id": str(quote.investor_user_id),
        "pair": pair,
        "source_amount_minor": source_amount_minor,
        "gross_target_amount_minor": gross_target_amount_minor,
        "target_amount_minor": target_amount_minor,
        "fee_minor": fee_minor,
        "rate": str(rate),
        "expires_at": quote.expires_at.isoformat(),
    }
    FxEvent.objects.create(
        quote=quote,
        event_type=FxEventType.QUOTE_ISSUED,
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        metadata=event_metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="fx.quote_issued",
            target_type="FxQuote",
            target_id=str(quote.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="FxExecutableQuoteIssued",
            aggregate_type="FxQuote",
            aggregate_id=str(quote.id),
            payload=event_metadata,
            idempotency_key=f"fx-quote:{quote.id}:issued",
        )
    )
    return quote


def execute_fx_quote(command: ExecuteFxQuoteCommand) -> FxExchange:
    _require_financial_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    quote = (
        FxQuote.objects.select_related("source_currency", "target_currency")
        .filter(id=command.quote_id)
        .first()
    )
    if quote is None:
        raise FxValidationError("FX quote does not exist.")
    if str(quote.investor_user_id) != str(command.actor.pk):
        raise FxAuthorizationError("Investor can only execute their own FX quote.")
    request_fingerprint = _exchange_request_fingerprint(
        command,
        quote=cast(FxQuote, quote),
        idempotency_key=idempotency_key,
    )
    existing = _existing_exchange_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    if quote.exchanges.exists():
        raise FxValidationError("FX quote has already been executed.")
    as_of = command.as_of or now_utc()
    if as_of > quote.expires_at:
        raise FxValidationError("FX quote has expired.")
    _assert_daily_limit(
        investor_user_id=str(command.actor.pk),
        business_day=_business_date_for_timestamp(as_of),
        requested_chf_equivalent_minor=quote.limit_chf_equivalent_minor,
    )

    try:
        verify_sensitive_action_code(
            SensitiveActionVerificationCommand(
                actor=command.actor,
                action=FX_ACTION,
                code_id=command.sensitive_action_code_id,
                raw_code=command.sensitive_action_code,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
    except SensitiveActionVerificationError as exc:
        raise FxValidationError(str(exc)) from exc

    return _execute_fx_quote_after_sensitive_code(command)


@transaction.atomic
def _execute_fx_quote_after_sensitive_code(command: ExecuteFxQuoteCommand) -> FxExchange:
    _require_financial_actor(command.actor)
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    quote = (
        FxQuote.objects.select_for_update()
        .select_related("source_currency", "target_currency")
        .filter(id=command.quote_id)
        .first()
    )
    if quote is None:
        raise FxValidationError("FX quote does not exist.")
    if str(quote.investor_user_id) != str(command.actor.pk):
        raise FxAuthorizationError("Investor can only execute their own FX quote.")
    request_fingerprint = _exchange_request_fingerprint(
        command,
        quote=cast(FxQuote, quote),
        idempotency_key=idempotency_key,
    )
    existing = _existing_exchange_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    if quote.exchanges.exists():
        raise FxValidationError("FX quote has already been executed.")
    as_of = command.as_of or now_utc()
    if as_of > quote.expires_at:
        raise FxValidationError("FX quote has expired.")
    _assert_daily_limit(
        investor_user_id=str(command.actor.pk),
        business_day=_business_date_for_timestamp(as_of),
        requested_chf_equivalent_minor=quote.limit_chf_equivalent_minor,
    )
    ledger = _ledger_services()
    try:
        ledger_result = ledger.execute_investor_fx_exchange_ledger(
            ledger.ExecuteInvestorFxExchangeLedgerCommand(
                actor=command.actor,
                investor_user_id=str(command.actor.pk),
                source_currency=quote.source_currency_id,
                target_currency=quote.target_currency_id,
                source_amount_minor=quote.source_amount_minor,
                gross_target_amount_minor=quote.gross_target_amount_minor,
                target_amount_minor=quote.target_amount_minor,
                fee_minor=quote.fee_minor,
                source_type="fx_quote",
                source_id=str(quote.id),
                idempotency_key=idempotency_key,
                as_of=as_of,
                metadata={
                    "quote_id": str(quote.id),
                    "rate": str(quote.rate),
                    "platform_fee_bps": quote.platform_fee_bps,
                },
            )
        )
    except ledger.LedgerError as exc:
        raise FxValidationError(str(exc)) from exc
    metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "quote_id": str(quote.id),
        "provider": quote.provider,
        "provider_quote_id": quote.provider_quote_id,
        "source_journal_entry_id": str(ledger_result.source_journal_entry.id),
        "target_journal_entry_id": str(ledger_result.target_journal_entry.id),
        "target_balance_lot_id": str(ledger_result.target_balance_lot.id),
    }
    try:
        with transaction.atomic():
            exchange = cast(
                FxExchange,
                FxExchange.objects.create(
                    quote=quote,
                    investor_user_id=command.actor.pk,
                    source_currency=quote.source_currency,
                    target_currency=quote.target_currency,
                    source_amount_minor=quote.source_amount_minor,
                    rate=quote.rate,
                    platform_fee_bps=quote.platform_fee_bps,
                    gross_target_amount_minor=quote.gross_target_amount_minor,
                    fee_minor=quote.fee_minor,
                    target_amount_minor=quote.target_amount_minor,
                    limit_chf_equivalent_minor=quote.limit_chf_equivalent_minor,
                    source_journal_entry=ledger_result.source_journal_entry,
                    target_journal_entry=ledger_result.target_journal_entry,
                    target_balance_lot=ledger_result.target_balance_lot,
                    source_lot_allocations=ledger_result.source_lot_allocations,
                    executed_at=as_of,
                    metadata=metadata,
                    idempotency_key=idempotency_key,
                ),
            )
    except IntegrityError:
        existing_after_race = _existing_exchange_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race
    actor_ref = actor_ref_for_user(command.actor)
    event_metadata = {
        "exchange_id": str(exchange.id),
        "quote_id": str(quote.id),
        "investor_user_id": str(exchange.investor_user_id),
        "source_currency": quote.source_currency_id,
        "target_currency": quote.target_currency_id,
        "source_amount_minor": quote.source_amount_minor,
        "gross_target_amount_minor": quote.gross_target_amount_minor,
        "target_amount_minor": quote.target_amount_minor,
        "fee_minor": quote.fee_minor,
    }
    FxEvent.objects.create(
        quote=quote,
        exchange=exchange,
        event_type=FxEventType.EXCHANGE_COMPLETED,
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        metadata=event_metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="fx.exchange_completed",
            target_type="FxExchange",
            target_id=str(exchange.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="CurrencyExchangeCompleted",
            aggregate_type="FxExchange",
            aggregate_id=str(exchange.id),
            payload=event_metadata,
            idempotency_key=f"fx-exchange:{exchange.id}:completed",
        )
    )
    return exchange


def create_fx_delta_report(
    *,
    actor: Model,
    start_date: date,
    end_date: date,
) -> FxDeltaReport:
    if not is_admin_actor(actor):
        raise FxAuthorizationError("Only an active admin can inspect FX delta reports.")
    if end_date < start_date:
        raise FxValidationError("End date cannot be before start date.")
    exchanges = _unsettled_exchanges_in_range(start_date, end_date)
    source_sold: dict[str, int] = {}
    gross_target_bought: dict[str, int] = {}
    target_credited: dict[str, int] = {}
    fees: dict[str, int] = {}
    for exchange in exchanges:
        source_code = exchange.source_currency_id
        target_code = exchange.target_currency_id
        source_sold[source_code] = source_sold.get(source_code, 0) + exchange.source_amount_minor
        gross_target_bought[target_code] = (
            gross_target_bought.get(target_code, 0) + exchange.gross_target_amount_minor
        )
        target_credited[target_code] = (
            target_credited.get(target_code, 0) + exchange.target_amount_minor
        )
        fees[target_code] = fees.get(target_code, 0) + exchange.fee_minor
    net: dict[str, int] = {}
    for currency, amount in source_sold.items():
        net[currency] = net.get(currency, 0) - amount
    for currency, amount in gross_target_bought.items():
        net[currency] = net.get(currency, 0) + amount
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="fx.delta_report_generated",
            target_type="FxDeltaReport",
            target_id=f"{start_date.isoformat()}:{end_date.isoformat()}",
            metadata={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "exchange_count": exchanges.count(),
            },
        )
    )
    return FxDeltaReport(
        start_date=start_date,
        end_date=end_date,
        exchange_count=exchanges.count(),
        source_sold_by_currency_minor=source_sold,
        gross_target_bought_by_currency_minor=gross_target_bought,
        target_credited_by_currency_minor=target_credited,
        fees_by_currency_minor=fees,
        net_external_settlement_by_currency_minor=net,
    )


@transaction.atomic
def declare_fx_external_settlement(
    command: DeclareFxExternalSettlementCommand,
) -> FxExternalSettlement:
    if not is_admin_actor(command.actor):
        raise FxAuthorizationError("Only an active admin can declare FX external settlements.")
    sold_currency = _enabled_currency(command.sold_currency)
    bought_currency = _enabled_currency(command.bought_currency)
    if sold_currency.code == bought_currency.code:
        raise FxValidationError("FX external settlement currencies must differ.")
    pair = _pair_key(sold_currency.code, bought_currency.code)
    if pair not in _enabled_pairs():
        raise FxValidationError("FX pair is not enabled.")
    _exchange_date_range_bounds(command.start_date, command.end_date)
    sold_amount_minor = _validate_money(
        command.sold_amount_minor,
        sold_currency.code,
        "FX external sold amount",
    )
    bought_amount_minor = _validate_money(
        command.bought_amount_minor,
        bought_currency.code,
        "FX external bought amount",
    )
    collection_account_identifier = command.collection_account_identifier.strip()
    if not collection_account_identifier:
        raise FxValidationError("Collection account identifier is required.")
    idempotency_key = _clean_idempotency_key(command.idempotency_key)
    request_fingerprint = _external_settlement_request_fingerprint(
        command,
        sold_currency_code=sold_currency.code,
        bought_currency_code=bought_currency.code,
        sold_amount_minor=sold_amount_minor,
        bought_amount_minor=bought_amount_minor,
        idempotency_key=idempotency_key,
    )
    existing = _existing_external_settlement_for_idempotency(
        idempotency_key,
        expected_fingerprint=request_fingerprint,
    )
    if existing is not None:
        return existing
    batch = _expected_pair_batch(
        sold_currency_code=sold_currency.code,
        bought_currency_code=bought_currency.code,
        start_date=command.start_date,
        end_date=command.end_date,
    )
    expected_sold_amount_minor = batch.expected_sold_amount_minor
    expected_bought_amount_minor = batch.expected_bought_amount_minor
    expected_target_credited_minor = batch.expected_target_credited_minor
    expected_fee_minor = batch.expected_fee_minor
    if expected_sold_amount_minor <= 0 or expected_bought_amount_minor <= 0:
        raise FxValidationError(
            "No unsettled internal FX exchanges exist for this pair and date range."
        )
    sold_currency_residual_minor = expected_sold_amount_minor - sold_amount_minor
    bought_currency_residual_minor = bought_amount_minor - expected_bought_amount_minor
    actual_rate = _actual_rate(
        sold_currency=sold_currency,
        bought_currency=bought_currency,
        sold_amount_minor=sold_amount_minor,
        bought_amount_minor=bought_amount_minor,
    )

    as_of = command.as_of or now_utc()
    settlement_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"banxum:fx-external-settlement:{idempotency_key}",
    )
    settlement_metadata = {
        REQUEST_FINGERPRINT_METADATA_KEY: request_fingerprint,
        "pair": pair,
        "expected_target_credited_minor": expected_target_credited_minor,
        "settled_exchange_ids": [str(exchange.id) for exchange in batch.exchanges],
        "settled_exchange_count": len(batch.exchanges),
        "sold_currency_residual_policy": (
            "expected sold minus actual sold; positive means source-currency clearing remains"
        ),
        "bought_currency_residual_policy": (
            "actual bought minus expected bought; positive means target-currency surplus"
        ),
    }
    ledger = _ledger_services()
    try:
        ledger_result = ledger.declare_fx_external_settlement_ledger(
            ledger.DeclareFxExternalSettlementLedgerCommand(
                actor=command.actor,
                settlement_id=str(settlement_id),
                sold_currency=sold_currency.code,
                bought_currency=bought_currency.code,
                sold_amount_minor=sold_amount_minor,
                bought_amount_minor=bought_amount_minor,
                booking_date=command.booking_date,
                value_date=command.value_date,
                collection_account_identifier=collection_account_identifier,
                bank_reference=command.bank_reference,
                payment_reference=command.payment_reference,
                evidence_reference=command.evidence_reference,
                notes=command.notes,
                idempotency_key=idempotency_key,
                as_of=as_of,
                metadata={
                    "pair": pair,
                    "start_date": command.start_date.isoformat(),
                    "end_date": command.end_date.isoformat(),
                    "expected_sold_amount_minor": expected_sold_amount_minor,
                    "expected_bought_amount_minor": expected_bought_amount_minor,
                    "expected_fee_minor": expected_fee_minor,
                    "sold_currency_residual_minor": sold_currency_residual_minor,
                    "bought_currency_residual_minor": bought_currency_residual_minor,
                    "settled_exchange_ids": [str(exchange.id) for exchange in batch.exchanges],
                },
            )
        )
    except ledger.LedgerError as exc:
        raise FxValidationError(str(exc)) from exc

    try:
        with transaction.atomic():
            settlement = cast(
                FxExternalSettlement,
                FxExternalSettlement.objects.create(
                    id=settlement_id,
                    sold_currency=sold_currency,
                    bought_currency=bought_currency,
                    start_date=command.start_date,
                    end_date=command.end_date,
                    expected_sold_amount_minor=expected_sold_amount_minor,
                    expected_bought_amount_minor=expected_bought_amount_minor,
                    expected_fee_minor=expected_fee_minor,
                    sold_amount_minor=sold_amount_minor,
                    bought_amount_minor=bought_amount_minor,
                    sold_currency_residual_minor=sold_currency_residual_minor,
                    bought_currency_residual_minor=bought_currency_residual_minor,
                    actual_rate=actual_rate,
                    booking_date=command.booking_date,
                    value_date=command.value_date,
                    collection_account_identifier=collection_account_identifier,
                    bank_reference=command.bank_reference.strip(),
                    payment_reference=command.payment_reference.strip(),
                    evidence_reference=command.evidence_reference.strip(),
                    notes=command.notes.strip(),
                    status=FxExternalSettlementStatus.DECLARED,
                    sold_bank_operation=ledger_result.sold_bank_operation,
                    bought_bank_operation=ledger_result.bought_bank_operation,
                    sold_journal_entry=ledger_result.sold_journal_entry,
                    bought_journal_entry=ledger_result.bought_journal_entry,
                    declared_by_admin_id=command.actor.pk,
                    declared_at=as_of,
                    metadata=settlement_metadata,
                    idempotency_key=idempotency_key,
                ),
            )
            _create_external_settlement_exchange_links(
                settlement=settlement,
                exchanges=batch.exchanges,
                settled_at=as_of,
            )
    except IntegrityError:
        existing_after_race = _existing_external_settlement_for_idempotency(
            idempotency_key,
            expected_fingerprint=request_fingerprint,
        )
        if existing_after_race is None:
            raise
        return existing_after_race

    actor_ref = actor_ref_for_user(command.actor)
    event_metadata = {
        "settlement_id": str(settlement.id),
        "pair": pair,
        "start_date": command.start_date.isoformat(),
        "end_date": command.end_date.isoformat(),
        "sold_currency": sold_currency.code,
        "bought_currency": bought_currency.code,
        "expected_sold_amount_minor": expected_sold_amount_minor,
        "expected_bought_amount_minor": expected_bought_amount_minor,
        "sold_amount_minor": sold_amount_minor,
        "bought_amount_minor": bought_amount_minor,
        "sold_currency_residual_minor": sold_currency_residual_minor,
        "bought_currency_residual_minor": bought_currency_residual_minor,
        "actual_rate": str(actual_rate),
    }
    FxEvent.objects.create(
        external_settlement=settlement,
        event_type=FxEventType.EXTERNAL_SETTLEMENT_DECLARED,
        actor_user_id=command.actor.pk,
        actor_account_type=str(getattr(command.actor, "account_type", "")),
        metadata=event_metadata,
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="fx.external_settlement_declared",
            target_type="FxExternalSettlement",
            target_id=str(settlement.id),
            metadata=event_metadata,
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="FxExternalSettlementDeclared",
            aggregate_type="FxExternalSettlement",
            aggregate_id=str(settlement.id),
            payload=event_metadata,
            idempotency_key=f"fx-external-settlement:{settlement.id}:declared",
        )
    )
    return settlement


def create_fx_realized_settlement_report(
    *,
    actor: Model,
    start_date: date,
    end_date: date,
) -> FxRealizedSettlementReport:
    if not is_admin_actor(actor):
        raise FxAuthorizationError("Only an active admin can inspect FX realized reports.")
    if end_date < start_date:
        raise FxValidationError("End date cannot be before start date.")
    settlements = FxExternalSettlement.objects.filter(
        value_date__gte=start_date,
        value_date__lte=end_date,
    )
    expected_sold: dict[str, int] = {}
    actual_sold: dict[str, int] = {}
    expected_bought: dict[str, int] = {}
    actual_bought: dict[str, int] = {}
    fees: dict[str, int] = {}
    residual: dict[str, int] = {}
    for settlement in settlements:
        sold_code = settlement.sold_currency_id
        bought_code = settlement.bought_currency_id
        expected_sold[sold_code] = (
            expected_sold.get(sold_code, 0) + settlement.expected_sold_amount_minor
        )
        actual_sold[sold_code] = actual_sold.get(sold_code, 0) + settlement.sold_amount_minor
        expected_bought[bought_code] = (
            expected_bought.get(bought_code, 0) + settlement.expected_bought_amount_minor
        )
        actual_bought[bought_code] = (
            actual_bought.get(bought_code, 0) + settlement.bought_amount_minor
        )
        fees[bought_code] = fees.get(bought_code, 0) + settlement.expected_fee_minor
        residual[sold_code] = (
            residual.get(sold_code, 0) + settlement.sold_currency_residual_minor
        )
        residual[bought_code] = (
            residual.get(bought_code, 0) + settlement.bought_currency_residual_minor
        )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action="fx.realized_settlement_report_generated",
            target_type="FxRealizedSettlementReport",
            target_id=f"{start_date.isoformat()}:{end_date.isoformat()}",
            metadata={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "settlement_count": settlements.count(),
            },
        )
    )
    return FxRealizedSettlementReport(
        start_date=start_date,
        end_date=end_date,
        settlement_count=settlements.count(),
        expected_sold_by_currency_minor=expected_sold,
        actual_sold_by_currency_minor=actual_sold,
        expected_bought_by_currency_minor=expected_bought,
        actual_bought_by_currency_minor=actual_bought,
        fees_by_currency_minor=fees,
        residual_by_currency_minor=residual,
    )


def _fx_environment() -> str:
    return str(settings.ENVIRONMENT).strip().lower()


def _mock_fx_provider_allowed() -> bool:
    return _fx_environment() in LOCAL_FX_ENVIRONMENTS and not bool(settings.IS_PRODUCTION)


def _yahoo_symbol_for_pair(pair: str) -> str:
    configured = get_platform_setting_value("fx.yahoo_symbols", DEFAULT_YAHOO_SYMBOLS)
    if not isinstance(configured, dict):
        configured = DEFAULT_YAHOO_SYMBOLS
    symbol = str(configured.get(pair, DEFAULT_YAHOO_SYMBOLS.get(pair, ""))).strip()
    if not symbol:
        raise FxValidationError(f"Yahoo Finance symbol is not configured for FX pair {pair}.")
    return symbol


def _latest_numeric_close(values: list[Any]) -> Decimal | None:
    for value in reversed(values):
        if value is None:
            continue
        decimal = _as_decimal(value, "Yahoo Finance close price")
        if decimal > 0:
            return decimal
    return None


def _yahoo_chart_provider_rate(
    *,
    source_currency: str,
    target_currency: str,
) -> ProviderRate:
    source = normalize_currency(source_currency)
    target = normalize_currency(target_currency)
    pair = _pair_key(source, target)
    symbol = _yahoo_symbol_for_pair(pair)
    base_url = str(settings.FX_YAHOO_CHART_URL).rstrip("/")
    url = (
        f"{base_url}/{urllib.parse.quote(symbol, safe='=')}"
        "?range=2d&interval=1d&includePrePost=false"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": str(settings.FX_YAHOO_USER_AGENT),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=settings.FX_YAHOO_TIMEOUT_SECONDS,
        ) as response:
            if response.status < 200 or response.status >= 300:
                raise FxValidationError(f"Yahoo Finance returned HTTP {response.status}.")
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise FxValidationError(f"Yahoo Finance returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise FxValidationError("Yahoo Finance rate request failed.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FxValidationError("Yahoo Finance returned malformed JSON.") from exc

    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict):
        raise FxValidationError("Yahoo Finance chart payload is malformed.")
    if chart.get("error"):
        raise FxValidationError("Yahoo Finance returned a chart error.")
    results = chart.get("result")
    if not isinstance(results, list) or not results:
        raise FxValidationError("Yahoo Finance chart payload has no result.")
    result = results[0]
    if not isinstance(result, dict):
        raise FxValidationError("Yahoo Finance chart result is malformed.")
    meta = result.get("meta")
    if not isinstance(meta, dict):
        raise FxValidationError("Yahoo Finance chart metadata is missing.")

    quote_rows = (result.get("indicators") or {}).get("quote") if isinstance(
        result.get("indicators"),
        dict,
    ) else None
    closes: list[Any] = []
    if isinstance(quote_rows, list) and quote_rows and isinstance(quote_rows[0], dict):
        close_values = quote_rows[0].get("close")
        if isinstance(close_values, list):
            closes = close_values

    rate_value = meta.get("regularMarketPrice")
    rate = _as_decimal(rate_value, "Yahoo Finance regular market price") if rate_value else None
    if rate is None or rate <= 0:
        rate = _latest_numeric_close(closes)
    if rate is None or rate <= 0:
        raise FxValidationError("Yahoo Finance did not return a positive executable rate.")

    previous_value = meta.get("previousClose") or meta.get("chartPreviousClose")
    previous_average: Decimal | None = None
    if previous_value is not None:
        previous_average = _as_decimal(previous_value, "Yahoo Finance previous close")
    elif len(closes) >= 2:
        previous_average = _latest_numeric_close(closes[:-1])

    observed_timestamp = meta.get("regularMarketTime")
    if observed_timestamp is None:
        timestamps = result.get("timestamp")
        if isinstance(timestamps, list) and timestamps:
            observed_timestamp = timestamps[-1]
    if not isinstance(observed_timestamp, int):
        raise FxValidationError("Yahoo Finance did not return a usable rate timestamp.")
    observed_at = datetime.fromtimestamp(observed_timestamp, tz=UTC)
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return ProviderRate(
        provider=YAHOO_FINANCE_PROVIDER,
        rate=rate,
        previous_day_average_rate=previous_average,
        observed_at=observed_at,
        provider_quote_id=f"yahoo:{symbol}:{observed_timestamp}",
        raw_payload_reference=f"sha256:{payload_hash}",
    )


def configured_provider_rate(
    *,
    source_currency: str,
    target_currency: str,
    as_of: datetime | None = None,
) -> ProviderRate:
    provider = str(settings.FX_RATE_PROVIDER).strip().lower()
    if provider in MOCK_FX_PROVIDERS:
        return configured_mock_provider_rate(
            source_currency=source_currency,
            target_currency=target_currency,
            as_of=as_of,
        )
    if provider == YAHOO_FINANCE_PROVIDER:
        return _yahoo_chart_provider_rate(
            source_currency=source_currency,
            target_currency=target_currency,
        )
    raise FxValidationError(f"Unsupported FX rate provider '{provider}'.")


def configured_mock_provider_rate(
    *,
    source_currency: str,
    target_currency: str,
    as_of: datetime | None = None,
) -> ProviderRate:
    if not _mock_fx_provider_allowed():
        raise FxValidationError("Mock FX provider can be used only in local/test environments.")
    source = normalize_currency(source_currency)
    target = normalize_currency(target_currency)
    pair = _pair_key(source, target)
    default_rates = {"CHF/EUR": "1.050000", "EUR/CHF": "0.952381"}
    configured = get_platform_setting_value("fx.mock_rates", default_rates)
    if not isinstance(configured, dict):
        configured = default_rates
    rate = _as_decimal(configured.get(pair, default_rates.get(pair, "0")), "Mock FX rate")
    timestamp = as_of or now_utc()
    return ProviderRate(
        provider="mock",
        rate=rate,
        previous_day_average_rate=rate,
        observed_at=timestamp,
        provider_quote_id=f"mock:{pair}:{timestamp.isoformat()}",
    )
