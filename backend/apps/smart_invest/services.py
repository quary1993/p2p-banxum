from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.db.models import Model

from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    user_can_access_financial_features,
)
from backend.apps.platform_core.domain.time import now_utc
from backend.apps.platform_core.models.events import OutboxStatus
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    record_domain_event,
)
from backend.apps.smart_invest.models import (
    SMART_INVEST_BANXUM_SOURCE,
    SmartInvestCollateralOption,
    SmartInvestCurrency,
    SmartInvestMatchNotification,
    SmartInvestRule,
    SmartInvestRuleEvent,
    SmartInvestRuleEventType,
)


class SmartInvestAuthorizationError(RuntimeError):
    pass


class SmartInvestValidationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SaveSmartInvestRuleCommand:
    actor: Model
    minimum_yield_bps: int | None = None
    maximum_term_months: int | None = None
    maximum_ltv_bps: int | None = None
    # Optional usual amount (U33-DEC-19); it never restricts matching.
    preferred_amount_minor: int | None = None
    # Every list criterion is multi-select; an empty list does not restrict.
    originators: Sequence[str] = ()
    collateral: Sequence[str] = ()
    currencies: Sequence[str] = ()
    countries: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class SmartInvestNotificationResult:
    loan_id: str
    eligible_rule_count: int
    matched_rule_count: int
    notification_count: int


def _marketplace_services() -> Any:
    return import_module("backend.apps.marketplace_primary.services")


def _originator_services() -> Any:
    return import_module("backend.apps.originator_claims.services")


def _require_financial_access(actor: Model) -> str:
    if not user_can_access_financial_features(actor):
        raise SmartInvestAuthorizationError(
            "Smart-Invest requires active lender access, phone verification, and approved KYC."
        )
    return str(actor.pk)


# The loan catalog's own collateral type for unsecured lending; Smart-Invest
# offers it as the "unsecured" choice instead of a separate collateral type.
_UNSECURED_COLLATERAL_TYPE = "unsecured_exception"
_LIST_CRITERIA = (
    "originators",
    "collateral",
    "currencies",
    "countries",
)
# Smart Invest states (U33-DEC-19). A rule without an effective criterion is not set up.
STATE_NOT_SET_UP = "not_set_up"
STATE_ACTIVE = "active"
STATE_PAUSED = "paused"


def loan_field_choices(field_name: str) -> list[tuple[str, str]]:
    """Reuse the loan catalog choices without a domain-module import dependency."""
    loan_model = apps.get_model("loans", "Loan")
    field = cast(Any, loan_model)._meta.get_field(field_name)
    return [(str(value), str(label)) for value, label in field.choices]


def collateral_choices() -> list[tuple[str, str]]:
    """Collateral options: any collateral, each loan collateral type, or none."""
    any_secured = SmartInvestCollateralOption.ANY_SECURED
    unsecured = SmartInvestCollateralOption.UNSECURED
    return [
        (str(any_secured.value), str(any_secured.label)),
        *(
            (value, label)
            for value, label in loan_field_choices("collateral_type")
            if value != _UNSECURED_COLLATERAL_TYPE
        ),
        (str(unsecured.value), str(unsecured.label)),
    ]


def _choice_values(choices: Sequence[tuple[str, str]]) -> list[str]:
    return [value for value, _label in choices]


def _validated_choices(values: Sequence[str], allowed: Sequence[str], label: str) -> list[str]:
    """De-duplicate a multi-select list and return it in the catalog order."""
    selected: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if value not in allowed:
            raise SmartInvestValidationError(f"{label} {value!r} is not a valid choice.")
        selected.add(value)
    return [value for value in allowed if value in selected]


def _validated_collateral(values: Sequence[str]) -> list[str]:
    collateral = _validated_choices(values, _choice_values(collateral_choices()), "Collateral")
    if SmartInvestCollateralOption.ANY_SECURED in collateral:
        # "Any collateral" already covers every collateral type, including new ones.
        collateral = [
            value
            for value in collateral
            if value
            in (SmartInvestCollateralOption.ANY_SECURED, SmartInvestCollateralOption.UNSECURED)
        ]
    return collateral


def _validated_originators(values: Sequence[str]) -> list[str]:
    include_banxum = False
    originator_ids: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if value == SMART_INVEST_BANXUM_SOURCE:
            include_banxum = True
            continue
        try:
            originator_ids.add(str(uuid.UUID(value)))
        except ValueError as exc:
            raise SmartInvestValidationError(f"Loan Originator {value!r} is not valid.") from exc
    if originator_ids:
        originator_model = apps.get_model("originator_claims", "LoanOriginator")
        known = {
            str(pk)
            for pk in originator_model.objects.filter(id__in=originator_ids).values_list(
                "id", flat=True
            )
        }
        unknown = sorted(originator_ids - known)
        if unknown:
            raise SmartInvestValidationError(f"Loan Originator {unknown[0]!r} does not exist.")
    banxum = [SMART_INVEST_BANXUM_SOURCE] if include_banxum else []
    return banxum + sorted(originator_ids)


def _validated_countries(values: Sequence[str]) -> list[str]:
    """Borrower countries as the opportunities carry them, without duplicates."""
    countries: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if not value or len(value) > 64:
            raise SmartInvestValidationError(f"Country {value!r} is not valid.")
        if value.casefold() not in seen:
            seen.add(value.casefold())
            countries.append(value)
    return countries


def _validated_criteria(command: SaveSmartInvestRuleCommand) -> dict[str, Any]:
    minimum_yield_bps = command.minimum_yield_bps
    maximum_term_months = command.maximum_term_months
    maximum_ltv_bps = command.maximum_ltv_bps
    preferred_amount_minor = command.preferred_amount_minor
    if minimum_yield_bps is not None and not 0 <= minimum_yield_bps <= 100_000:
        raise SmartInvestValidationError("Minimum yield must be between 0 and 1000%.")
    if minimum_yield_bps == 0:
        minimum_yield_bps = None
    if maximum_term_months is not None and maximum_term_months < 1:
        raise SmartInvestValidationError("Maximum term must be at least one month.")
    if maximum_ltv_bps is not None and not 1 <= maximum_ltv_bps <= 10_000:
        raise SmartInvestValidationError("Maximum loan-to-value must be between 0.01% and 100%.")
    if preferred_amount_minor is not None and preferred_amount_minor < 0:
        raise SmartInvestValidationError("The usual amount cannot be negative.")
    if preferred_amount_minor == 0:
        preferred_amount_minor = None

    criteria = {
        "minimum_yield_bps": minimum_yield_bps,
        "maximum_term_months": maximum_term_months,
        "maximum_ltv_bps": maximum_ltv_bps,
        "preferred_amount_minor": preferred_amount_minor,
        "originators": _validated_originators(command.originators),
        "collateral": _validated_collateral(command.collateral),
        "currencies": _validated_choices(
            command.currencies, SmartInvestCurrency.values, "Currency"
        ),
        "countries": _validated_countries(command.countries),
    }
    if not _has_effective_criterion(criteria):
        raise SmartInvestValidationError(
            "Choose at least one Smart-Invest criterion before activating the rule."
        )
    return criteria


def _restricts(selected: Sequence[str], every_option: Sequence[str] | None = None) -> bool:
    """A list restricts matching unless it is empty or ticks every possible option."""
    if not selected:
        return False
    return every_option is None or not set(every_option).issubset(selected)


def _has_effective_criterion(criteria: dict[str, Any]) -> bool:
    """A criterion that limits the matches; the usual amount never does (U33-DEC-19)."""
    return any(
        (
            criteria["minimum_yield_bps"] is not None,
            criteria["maximum_term_months"] is not None,
            criteria.get("maximum_ltv_bps") is not None,
            _restricts(criteria["originators"]),
            _restricts(
                criteria["collateral"],
                SmartInvestCollateralOption.values,
            ),
            _restricts(criteria["currencies"], SmartInvestCurrency.values),
            _restricts(criteria.get("countries") or []),
        )
    )


def _criteria_snapshot(rule: SmartInvestRule) -> dict[str, Any]:
    return {
        "minimum_yield_bps": rule.minimum_yield_bps,
        "maximum_term_months": rule.maximum_term_months,
        "maximum_ltv_bps": rule.maximum_ltv_bps,
        "preferred_amount_minor": rule.preferred_amount_minor,
        **{field: [str(value) for value in getattr(rule, field) or []] for field in _LIST_CRITERIA},
    }


def _rule_state(rule: SmartInvestRule | None) -> str:
    if rule is None or not _has_effective_criterion(_criteria_snapshot(rule)):
        return STATE_NOT_SET_UP
    return STATE_ACTIVE if rule.is_active else STATE_PAUSED


def _rule_payload(rule: SmartInvestRule | None) -> dict[str, Any] | None:
    if rule is None:
        return None
    return {
        "id": str(rule.id),
        "is_active": rule.is_active,
        "state": _rule_state(rule),
        "revision": rule.revision,
        **_criteria_snapshot(rule),
        "activated_at": rule.activated_at,
        "deactivated_at": rule.deactivated_at,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _opportunity_is_unsecured(opportunity: dict[str, Any]) -> bool:
    collateral_type = str(opportunity.get("collateral_type") or "")
    return collateral_type == _UNSECURED_COLLATERAL_TYPE or opportunity.get("ltv_bps") is None


def opportunity_matches_criteria(opportunity: dict[str, Any], criteria: dict[str, Any]) -> bool:
    """One matching rule for the matches list and for new-publication alerts.

    Conditions combine with AND; the values ticked inside one list combine with OR.
    """
    yield_bps = int(opportunity.get("yield_bps") or 0)
    term_months = int(opportunity.get("term_months") or 0)

    if criteria["minimum_yield_bps"] is not None and yield_bps < int(criteria["minimum_yield_bps"]):
        return False
    if criteria["maximum_term_months"] is not None and term_months > int(
        criteria["maximum_term_months"]
    ):
        return False

    originators = set(criteria.get("originators") or [])
    if originators:
        if str(opportunity.get("product_type") or "direct") == "direct":
            source_matches = SMART_INVEST_BANXUM_SOURCE in originators
        else:
            source_matches = str(opportunity.get("originator_id") or "") in originators
        if not source_matches:
            return False

    collateral = set(criteria.get("collateral") or [])
    if collateral:
        if _opportunity_is_unsecured(opportunity):
            collateral_matches = SmartInvestCollateralOption.UNSECURED in collateral
        else:
            collateral_matches = (
                SmartInvestCollateralOption.ANY_SECURED in collateral
                or str(opportunity.get("collateral_type") or "") in collateral
            )
        if not collateral_matches:
            return False

    maximum_ltv_bps = criteria.get("maximum_ltv_bps")
    if maximum_ltv_bps is not None:
        # Without a loan-to-value figure the limit cannot be checked: no match.
        ltv_bps = opportunity.get("ltv_bps")
        if ltv_bps is None or int(ltv_bps) > int(maximum_ltv_bps):
            return False

    currencies = criteria.get("currencies") or []
    if currencies and str(opportunity.get("currency") or "") not in currencies:
        return False

    countries = {str(value).casefold() for value in criteria.get("countries") or []}
    if countries and str(opportunity.get("borrower_country") or "").casefold() not in countries:
        return False
    return True


def _matching_opportunities(rule: SmartInvestRule) -> tuple[list[dict[str, Any]], int]:
    marketplace = _marketplace_services()
    # The investor's own minimum (Swiss-borrower investor limit, plan/09 MKT-DEC-028).
    opportunities = marketplace.list_open_marketplace_loans(
        limit=10_000,
        viewer_user_id=str(rule.user_id),
    )
    criteria = _criteria_snapshot(rule)
    # A fully funded loan is no match: no order can go into it.
    return (
        [
            item
            for item in opportunities
            if marketplace.marketplace_payload_has_capacity(item)
            and opportunity_matches_criteria(item, criteria)
        ],
        len(opportunities),
    )


def _coming_soon_matches(rule: SmartInvestRule) -> list[dict[str, Any]]:
    """U33-DEC-17: Coming soon opportunities that match, apart from the open matches."""
    criteria = _criteria_snapshot(rule)
    return [
        item
        for item in _marketplace_services().coming_soon_marketplace_payloads(
            viewer_user_id=str(rule.user_id)
        )
        if opportunity_matches_criteria(item, criteria)
    ]


def get_smart_invest(*, actor: Model) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    matches: list[dict[str, Any]] = []
    coming_soon: list[dict[str, Any]] = []
    open_opportunity_count = len(_marketplace_services().list_open_marketplace_loans(limit=10_000))
    # A paused rule shows no matches (U33-DEC-19); resuming recalculates them.
    if rule is not None and rule.is_active:
        matches, open_opportunity_count = _matching_opportunities(rule)
        coming_soon = _coming_soon_matches(rule)
    return {
        "rule": _rule_payload(rule),
        "notification_channels": _channels_payload(rule),
        # Open matches only: the counters never include Coming soon (U33-DEC-17).
        "match_count": len(matches),
        "open_opportunity_count": open_opportunity_count,
        "matches": matches,
        "coming_soon_matches": coming_soon,
    }


def _channels_payload(rule: SmartInvestRule | None) -> dict[str, bool]:
    """U33-DEC-30: both channels are on until the investor switches one off."""
    if rule is None:
        return {"in_app": True, "email": True}
    return {"in_app": bool(rule.notify_in_app), "email": bool(rule.notify_email)}


@dataclass(frozen=True, slots=True)
class SetSmartInvestChannelsCommand:
    actor: Model
    in_app: bool
    email: bool


@transaction.atomic
def set_smart_invest_channels(command: SetSmartInvestChannelsCommand) -> dict[str, Any]:
    """U33-DEC-30: switch the in-app and email match alerts separately.

    Also before set-up: the choice is kept for when the investor saves preferences. Neither
    channel stops matching or service messages; Pause stops both.
    """
    investor_user_id = _require_financial_access(command.actor)
    user_model = apps.get_model("accounts_auth", "User")
    user_model.objects.select_for_update().get(pk=investor_user_id)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    if rule is None:
        # Nothing saved yet: an empty, inactive rule only holds the channels (state not_set_up).
        rule = SmartInvestRule(user_id=investor_user_id, is_active=False)
    previous = _channels_payload(rule if rule.pk else None)
    new = {"in_app": bool(command.in_app), "email": bool(command.email)}
    if rule.pk and previous == new:
        return get_smart_invest(actor=command.actor)
    rule.notify_in_app = new["in_app"]
    rule.notify_email = new["email"]
    rule.save()
    SmartInvestRuleEvent.objects.create(
        rule=rule,
        investor_user_id=investor_user_id,
        actor_user_id=command.actor.pk,
        event_type=SmartInvestRuleEventType.CHANNELS_CHANGED,
        revision=rule.revision,
        criteria_snapshot=_criteria_snapshot(rule),
        metadata={"previous": previous, "new": new},
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(command.actor),
            action="smart_invest.channels_changed",
            target_type="SmartInvestRule",
            target_id=str(rule.id),
            metadata={"previous": previous, "new": new},
        )
    )
    return get_smart_invest(actor=command.actor)


@transaction.atomic
def save_smart_invest_rule(command: SaveSmartInvestRuleCommand) -> dict[str, Any]:
    investor_user_id = _require_financial_access(command.actor)
    criteria = _validated_criteria(command)
    user_model = apps.get_model("accounts_auth", "User")
    user_model.objects.select_for_update().get(pk=investor_user_id)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    now = now_utc()
    # Editing a paused rule keeps it paused (U33-DEC-19); a new set-up is active at once.
    keep_paused = _rule_state(rule) == STATE_PAUSED
    if rule is None:
        rule = SmartInvestRule(user_id=investor_user_id)
    for field, value in criteria.items():
        setattr(rule, field, value)
    rule.revision += 1
    if not keep_paused:
        rule.is_active = True
        rule.activated_at = now
        rule.deactivated_at = None
    rule.save()
    snapshot = _criteria_snapshot(rule)
    SmartInvestRuleEvent.objects.create(
        rule=rule,
        investor_user_id=investor_user_id,
        actor_user_id=command.actor.pk,
        event_type=SmartInvestRuleEventType.SAVED,
        revision=rule.revision,
        criteria_snapshot=snapshot,
        metadata={"paused": keep_paused},
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="smart_invest.rule_saved",
            target_type="SmartInvestRule",
            target_id=str(rule.id),
            metadata={"revision": rule.revision, "criteria": snapshot, "paused": keep_paused},
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="SmartInvestRuleSaved",
            aggregate_type="SmartInvestRule",
            aggregate_id=str(rule.id),
            payload={"investor_user_id": investor_user_id, "revision": rule.revision},
            idempotency_key=f"smart-invest-rule:{rule.id}:revision:{rule.revision}",
        )
    )
    return get_smart_invest(actor=command.actor)


def _record_state_change(
    *, rule: SmartInvestRule, actor: Model, event_type: str, action: str, domain_event: str
) -> None:
    SmartInvestRuleEvent.objects.create(
        rule=rule,
        investor_user_id=rule.user_id,
        actor_user_id=actor.pk,
        event_type=event_type,
        revision=rule.revision,
        criteria_snapshot=_criteria_snapshot(rule),
    )
    record_audit_event(
        AuditCommand(
            actor=actor_ref_for_user(actor),
            action=action,
            target_type="SmartInvestRule",
            target_id=str(rule.id),
            metadata={"revision": rule.revision},
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type=domain_event,
            aggregate_type="SmartInvestRule",
            aggregate_id=str(rule.id),
            payload={"investor_user_id": str(rule.user_id), "revision": rule.revision},
            idempotency_key=f"smart-invest-rule:{rule.id}:revision:{rule.revision}",
        )
    )


@transaction.atomic
def pause_smart_invest_rule(*, actor: Model) -> dict[str, Any]:
    """U33-DEC-19: stop matches and alerts, keep the preferences and the history."""
    investor_user_id = _require_financial_access(actor)
    user_model = apps.get_model("accounts_auth", "User")
    user_model.objects.select_for_update().get(pk=investor_user_id)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    if rule is None or not rule.is_active:
        return get_smart_invest(actor=actor)
    rule.is_active = False
    rule.revision += 1
    rule.deactivated_at = now_utc()
    rule.save(update_fields=["is_active", "revision", "deactivated_at", "updated_at"])
    _record_state_change(
        rule=rule,
        actor=actor,
        event_type=SmartInvestRuleEventType.PAUSED,
        action="smart_invest.rule_paused",
        domain_event="SmartInvestRulePaused",
    )
    return get_smart_invest(actor=actor)


@transaction.atomic
def resume_smart_invest_rule(*, actor: Model) -> dict[str, Any]:
    """U33-DEC-19: use the saved preferences again; the matches are calculated anew."""
    investor_user_id = _require_financial_access(actor)
    user_model = apps.get_model("accounts_auth", "User")
    user_model.objects.select_for_update().get(pk=investor_user_id)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    state = _rule_state(rule)
    if rule is None or state == STATE_NOT_SET_UP:
        raise SmartInvestValidationError("Set up Smart Invest before you resume it.")
    if state == STATE_ACTIVE:
        return get_smart_invest(actor=actor)
    rule.is_active = True
    rule.revision += 1
    rule.activated_at = now_utc()
    rule.deactivated_at = None
    rule.save(
        update_fields=["is_active", "revision", "activated_at", "deactivated_at", "updated_at"]
    )
    _record_state_change(
        rule=rule,
        actor=actor,
        event_type=SmartInvestRuleEventType.RESUMED,
        action="smart_invest.rule_resumed",
        domain_event="SmartInvestRuleResumed",
    )
    return get_smart_invest(actor=actor)


def _public_opportunity(*, loan_id: str, product_type: str) -> dict[str, Any] | None:
    loan_model = apps.get_model("loans", "Loan")
    loan = loan_model.objects.filter(id=loan_id).first()
    if loan is None:
        return None
    if product_type == "originator_claim":
        profile_model = apps.get_model("originator_claims", "OriginatorLoanProfile")
        profile = profile_model.objects.filter(loan_id=loan_id).first()
        if profile is None:
            return None
        try:
            return cast(
                dict[str, Any],
                _originator_services().originator_marketplace_payload(
                    profile, include_detail=False
                ),
            )
        except _originator_services().OriginatorClaimsValidationError:
            return None
    if str(getattr(loan, "status", "")) != "published":
        return None
    return cast(dict[str, Any], _marketplace_services().public_marketplace_listing_payload(loan))


def _email_payload(
    *, user: Model, opportunity: dict[str, Any], in_app: bool = True
) -> dict[str, Any]:
    currency = str(opportunity.get("currency", ""))
    yield_bps = int(opportunity.get("yield_bps") or 0)
    term_months = int(opportunity.get("term_months") or 0)
    originator_name = opportunity.get("originator_name")
    source = str(originator_name) if originator_name else "BANXUM direct lending"
    action_url = f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/smart-invest"
    title = str(opportunity.get("title") or "New lending opportunity")
    return {
        "user_id": str(user.pk),
        "recipient_email": str(getattr(user, "email", "")),
        "subject": f"A new BANXUM opportunity matches your Smart-Invest rule: {title}",
        "notice_label": "SMART INVEST MATCH",
        "preheader": f"{title} matches the criteria you selected.",
        "status_label": "New match",
        "status_tone": "info",
        "headline": "A new opportunity matches your rule",
        # The email renderer and the notification centre read `body_text`.
        "body_text": (
            f"{title} matches the Smart-Invest criteria you selected. "
            "Smart-Invest does not reserve or invest funds; review the opportunity before deciding."
        ),
        "data_rows": [
            ["Currency", currency],
            ["Target yield", f"{yield_bps / 100:.2f}% p.a."],
            ["Term", f"{term_months} months"],
            ["Source", source],
        ],
        "buttons": [{"label": "Review opportunity", "url": action_url}],
        "fine_print": (
            "Capital is at risk. Smart-Invest is an alerting tool and never places an order "
            "or reserves money on your behalf."
        ),
        "loan_id": str(opportunity["loan_id"]),
        "action_url": action_url,
        # U33-DEC-30: false keeps the email out of Notifications (in-app channel off).
        **({} if in_app else {"in_app": False}),
    }


IN_APP_MATCH_TOPIC = "notice.smart_invest_opportunity_match"


def _opening_alert_sent(*, investor_user_id: str, loan_id: str) -> bool:
    alert_model = apps.get_model("marketplace_primary", "LoanOpeningAlert")
    return bool(
        alert_model.objects.filter(
            loan_id=loan_id, investor_user_id=investor_user_id, notified_at__isnull=False
        ).exists()
    )


def _enqueue_match_alert(
    *, rule: SmartInvestRule, user: Model, loan_id: str, opportunity: dict[str, Any]
) -> Any:
    """U33-DEC-30: one message per match, shaped by the investor's channels.

    Email on: the email (listed in Notifications unless in-app is off). Email off, in-app on:
    an in-app notice that is never emailed. Both off: nothing; the match is still recorded.
    """
    if rule.notify_email:
        return enqueue_outbox_message(
            OutboxCommand(
                idempotency_key=f"smart-match:{user.pk}:{loan_id}",
                topic="email.smart_invest_opportunity_match",
                payload=_email_payload(
                    user=user, opportunity=opportunity, in_app=rule.notify_in_app
                ),
            )
        )
    if rule.notify_in_app:
        notice = enqueue_outbox_message(
            OutboxCommand(
                idempotency_key=f"smart-match:{user.pk}:{loan_id}",
                topic=IN_APP_MATCH_TOPIC,
                payload=_email_payload(user=user, opportunity=opportunity),
            )
        )
        # Not an email topic, so no sender picks it up: it is done once it is listed.
        type(notice).objects.filter(pk=notice.pk).update(
            status=OutboxStatus.PROCESSED, processed_at=now_utc()
        )
        return notice
    return None


@transaction.atomic
def notify_smart_invest_matches_for_published_loan(
    *, loan_id: str, product_type: str
) -> SmartInvestNotificationResult:
    opportunity = _public_opportunity(loan_id=loan_id, product_type=product_type)
    if opportunity is None:
        return SmartInvestNotificationResult(loan_id, 0, 0, 0)
    rules = list(
        SmartInvestRule.objects.filter(is_active=True).select_related("user").order_by("id")
    )
    matched = 0
    created_count = 0
    for rule in rules:
        user = cast(Model, rule.user)
        if not user_can_access_financial_features(user):
            continue
        criteria = _criteria_snapshot(rule)
        if not opportunity_matches_criteria(opportunity, criteria):
            continue
        matched += 1
        if SmartInvestMatchNotification.objects.filter(
            investor_user_id=user.pk, loan_id=loan_id
        ).exists():
            continue
        # U33-DEC-17: no second alert for an investor who just got this loan's opening alert.
        outbox = (
            None
            if _opening_alert_sent(investor_user_id=str(user.pk), loan_id=loan_id)
            else _enqueue_match_alert(
                rule=rule, user=user, loan_id=loan_id, opportunity=opportunity
            )
        )
        try:
            with transaction.atomic():
                SmartInvestMatchNotification.objects.create(
                    rule=rule,
                    investor_user_id=user.pk,
                    loan_id=loan_id,
                    product_type=product_type,
                    outbox_message=outbox,
                    rule_revision=rule.revision,
                    match_snapshot={
                        "criteria": criteria,
                        "opportunity": json.loads(json.dumps(opportunity, cls=DjangoJSONEncoder)),
                    },
                )
            created_count += 1
        except IntegrityError:
            continue
    return SmartInvestNotificationResult(
        loan_id=loan_id,
        eligible_rule_count=len(rules),
        matched_rule_count=matched,
        notification_count=created_count,
    )
