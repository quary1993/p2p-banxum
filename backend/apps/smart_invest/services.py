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
    SmartInvestLoanKind,
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
    # Every list criterion is multi-select; an empty list does not restrict.
    originators: Sequence[str] = ()
    collateral: Sequence[str] = ()
    currencies: Sequence[str] = ()
    risk_ratings: Sequence[str] = ()
    purposes: Sequence[str] = ()
    loan_kinds: Sequence[str] = ()


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
            "Smart Invest requires active lender access, phone verification, and approved KYC."
        )
    return str(actor.pk)


# The loan catalog's own collateral type for unsecured lending; Smart Invest
# offers it as the "unsecured" choice instead of a separate collateral type.
_UNSECURED_COLLATERAL_TYPE = "unsecured_exception"
_LIST_CRITERIA = (
    "originators",
    "collateral",
    "currencies",
    "risk_ratings",
    "purposes",
    "loan_kinds",
)


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


def _validated_criteria(command: SaveSmartInvestRuleCommand) -> dict[str, Any]:
    minimum_yield_bps = command.minimum_yield_bps
    maximum_term_months = command.maximum_term_months
    if minimum_yield_bps is not None and not 0 <= minimum_yield_bps <= 100_000:
        raise SmartInvestValidationError("Minimum yield must be between 0 and 1000%.")
    if minimum_yield_bps == 0:
        minimum_yield_bps = None
    if maximum_term_months is not None and maximum_term_months < 1:
        raise SmartInvestValidationError("Maximum term must be at least one month.")

    criteria = {
        "minimum_yield_bps": minimum_yield_bps,
        "maximum_term_months": maximum_term_months,
        "originators": _validated_originators(command.originators),
        "collateral": _validated_collateral(command.collateral),
        "currencies": _validated_choices(
            command.currencies, SmartInvestCurrency.values, "Currency"
        ),
        "risk_ratings": _validated_choices(
            command.risk_ratings,
            _choice_values(loan_field_choices("risk_rating")),
            "Risk rating",
        ),
        "purposes": _validated_choices(
            command.purposes, _choice_values(loan_field_choices("purpose")), "Purpose"
        ),
        "loan_kinds": _validated_choices(
            command.loan_kinds, SmartInvestLoanKind.values, "Loan type"
        ),
    }
    if not _has_effective_criterion(criteria):
        raise SmartInvestValidationError(
            "Choose at least one Smart Invest criterion before activating the rule."
        )
    return criteria


def _restricts(selected: Sequence[str], every_option: Sequence[str] | None = None) -> bool:
    """A list restricts matching unless it is empty or ticks every possible option."""
    if not selected:
        return False
    return every_option is None or not set(every_option).issubset(selected)


def _has_effective_criterion(criteria: dict[str, Any]) -> bool:
    return any(
        (
            criteria["minimum_yield_bps"] is not None,
            criteria["maximum_term_months"] is not None,
            _restricts(criteria["originators"]),
            _restricts(
                criteria["collateral"],
                SmartInvestCollateralOption.values,
            ),
            _restricts(criteria["currencies"], SmartInvestCurrency.values),
            _restricts(criteria["risk_ratings"], _choice_values(loan_field_choices("risk_rating"))),
            _restricts(criteria["purposes"], _choice_values(loan_field_choices("purpose"))),
            _restricts(criteria["loan_kinds"], SmartInvestLoanKind.values),
        )
    )


def _criteria_snapshot(rule: SmartInvestRule) -> dict[str, Any]:
    return {
        "minimum_yield_bps": rule.minimum_yield_bps,
        "maximum_term_months": rule.maximum_term_months,
        **{field: [str(value) for value in getattr(rule, field) or []] for field in _LIST_CRITERIA},
    }


def _rule_payload(rule: SmartInvestRule | None) -> dict[str, Any] | None:
    if rule is None:
        return None
    return {
        "id": str(rule.id),
        "is_active": rule.is_active,
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

    single_value_lists = (
        ("currencies", str(opportunity.get("currency") or "")),
        ("risk_ratings", str(opportunity.get("risk_rating") or "")),
        ("purposes", str(opportunity.get("purpose") or "")),
        (
            "loan_kinds",
            SmartInvestLoanKind.REFINANCING
            if bool(opportunity.get("is_refinancing"))
            else SmartInvestLoanKind.NEW,
        ),
    )
    for field, value in single_value_lists:
        selected = criteria.get(field) or []
        if selected and value not in selected:
            return False
    return True


def _matching_opportunities(rule: SmartInvestRule) -> tuple[list[dict[str, Any]], int]:
    marketplace = _marketplace_services()
    opportunities = marketplace.list_open_marketplace_loans(limit=10_000)
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


def get_smart_invest(*, actor: Model) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    matches: list[dict[str, Any]] = []
    open_opportunity_count = len(
        _marketplace_services().list_open_marketplace_loans(limit=10_000)
    )
    if rule is not None and rule.is_active:
        matches, open_opportunity_count = _matching_opportunities(rule)
    return {
        "rule": _rule_payload(rule),
        "match_count": len(matches),
        "open_opportunity_count": open_opportunity_count,
        "matches": matches,
    }


@transaction.atomic
def save_smart_invest_rule(command: SaveSmartInvestRuleCommand) -> dict[str, Any]:
    investor_user_id = _require_financial_access(command.actor)
    criteria = _validated_criteria(command)
    user_model = apps.get_model("accounts_auth", "User")
    user_model.objects.select_for_update().get(pk=investor_user_id)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    now = now_utc()
    if rule is None:
        rule = SmartInvestRule(user_id=investor_user_id)
    for field, value in criteria.items():
        setattr(rule, field, value)
    rule.is_active = True
    rule.revision += 1
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
    )
    actor_ref = actor_ref_for_user(command.actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="smart_invest.rule_saved",
            target_type="SmartInvestRule",
            target_id=str(rule.id),
            metadata={"revision": rule.revision, "criteria": snapshot},
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


@transaction.atomic
def deactivate_smart_invest_rule(*, actor: Model) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    user_model = apps.get_model("accounts_auth", "User")
    user_model.objects.select_for_update().get(pk=investor_user_id)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    if rule is None or not rule.is_active:
        return get_smart_invest(actor=actor)
    previous_snapshot = _criteria_snapshot(rule)
    rule.is_active = False
    rule.minimum_yield_bps = None
    rule.maximum_term_months = None
    for field in _LIST_CRITERIA:
        setattr(rule, field, [])
    rule.revision += 1
    rule.deactivated_at = now_utc()
    rule.save()
    SmartInvestRuleEvent.objects.create(
        rule=rule,
        investor_user_id=investor_user_id,
        actor_user_id=actor.pk,
        event_type=SmartInvestRuleEventType.DEACTIVATED,
        revision=rule.revision,
        criteria_snapshot=previous_snapshot,
    )
    actor_ref = actor_ref_for_user(actor)
    record_audit_event(
        AuditCommand(
            actor=actor_ref,
            action="smart_invest.rule_deactivated",
            target_type="SmartInvestRule",
            target_id=str(rule.id),
            metadata={"revision": rule.revision},
        )
    )
    record_domain_event(
        DomainEventCommand(
            event_type="SmartInvestRuleDeactivated",
            aggregate_type="SmartInvestRule",
            aggregate_id=str(rule.id),
            payload={"investor_user_id": investor_user_id, "revision": rule.revision},
            idempotency_key=f"smart-invest-rule:{rule.id}:revision:{rule.revision}",
        )
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


def _email_payload(*, user: Model, opportunity: dict[str, Any]) -> dict[str, Any]:
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
        "subject": f"A new BANXUM opportunity matches your Smart Invest rule: {title}",
        "notice_label": "SMART INVEST MATCH",
        "preheader": f"{title} matches the criteria you selected.",
        "status_label": "New match",
        "status_tone": "info",
        "headline": "A new opportunity matches your rule",
        # The email renderer and the notification centre read `body_text`.
        "body_text": (
            f"{title} matches the Smart Invest criteria you selected. "
            "Smart Invest does not reserve or invest funds; review the opportunity before deciding."
        ),
        "data_rows": [
            ["Currency", currency],
            ["Target yield", f"{yield_bps / 100:.2f}% p.a."],
            ["Term", f"{term_months} months"],
            ["Source", source],
        ],
        "buttons": [{"label": "Review opportunity", "url": action_url}],
        "fine_print": (
            "Capital is at risk. Smart Invest is an alerting tool and never places an order "
            "or reserves money on your behalf."
        ),
        "loan_id": str(opportunity["loan_id"]),
        "action_url": action_url,
    }


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
        outbox = enqueue_outbox_message(
            OutboxCommand(
                idempotency_key=f"smart-match:{user.pk}:{loan_id}",
                topic="email.smart_invest_opportunity_match",
                payload=_email_payload(user=user, opportunity=opportunity),
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
