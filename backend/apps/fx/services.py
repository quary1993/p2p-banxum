from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from importlib import import_module
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.db.models import Model, Sum

from backend.apps.fx.models import FxEvent, FxEventType, FxExchange, FxQuote
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
    raise FxValidationError("Daily FX limit currently requires one side of the pair to be CHF.")


def _business_day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min, tzinfo=business_timezone())
    return start, start + timedelta(days=1)


def _business_date_for_timestamp(value: datetime) -> date:
    return to_business_time(value).date()


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


@transaction.atomic
def execute_fx_quote(command: ExecuteFxQuoteCommand) -> FxExchange:
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
    start, _ = _business_day_bounds(start_date)
    _, end = _business_day_bounds(end_date)
    exchanges = FxExchange.objects.filter(executed_at__gte=start, executed_at__lt=end)
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


def configured_mock_provider_rate(
    *,
    source_currency: str,
    target_currency: str,
    as_of: datetime | None = None,
) -> ProviderRate:
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
