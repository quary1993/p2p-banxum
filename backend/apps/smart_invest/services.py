from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.utils import timezone

from backend.apps.platform_core.domain.access import (
    actor_ref_for_user,
    user_can_access_financial_features,
)
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event
from backend.apps.platform_core.services.events import (
    DomainEventCommand,
    OutboxCommand,
    enqueue_outbox_message,
    record_domain_event,
)
from backend.apps.smart_invest.models import (
    CollateralScope,
    CurrencyScope,
    LoanKind,
    OriginatorScope,
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
    originator_scope: str = OriginatorScope.ALL
    originator_id: str | None = None
    collateral_scope: str = CollateralScope.ALL
    collateral_type: str = ""
    currency_scope: str = CurrencyScope.ALL
    risk_rating: str = ""
    purpose: str = ""
    loan_kind: str = LoanKind.ALL


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


def _clean_optional(value: str) -> str:
    return value.strip()


def _validated_criteria(command: SaveSmartInvestRuleCommand) -> dict[str, Any]:
    minimum_yield_bps = command.minimum_yield_bps
    maximum_term_months = command.maximum_term_months
    if minimum_yield_bps is not None and not 0 <= minimum_yield_bps <= 100_000:
        raise SmartInvestValidationError("Minimum yield must be between 0 and 1000%.")
    if minimum_yield_bps == 0:
        minimum_yield_bps = None
    if maximum_term_months is not None and maximum_term_months < 1:
        raise SmartInvestValidationError("Maximum term must be at least one month.")
    if command.originator_scope not in OriginatorScope.values:
        raise SmartInvestValidationError("Originator scope is invalid.")
    if command.collateral_scope not in CollateralScope.values:
        raise SmartInvestValidationError("Collateral scope is invalid.")
    if command.currency_scope not in CurrencyScope.values:
        raise SmartInvestValidationError("Currency scope is invalid.")
    if command.loan_kind not in LoanKind.values:
        raise SmartInvestValidationError("Loan type is invalid.")

    originator_id = command.originator_id or None
    collateral_type = _clean_optional(command.collateral_type)
    if command.originator_scope == OriginatorScope.SPECIFIC and not originator_id:
        raise SmartInvestValidationError("Select a Loan Originator for this rule.")
    if command.originator_scope != OriginatorScope.SPECIFIC:
        originator_id = None
    if command.collateral_scope == CollateralScope.SPECIFIC and not collateral_type:
        raise SmartInvestValidationError("Select a collateral type for this rule.")
    if command.collateral_scope != CollateralScope.SPECIFIC:
        collateral_type = ""

    criteria = {
        "minimum_yield_bps": minimum_yield_bps,
        "maximum_term_months": maximum_term_months,
        "originator_scope": command.originator_scope,
        "originator_id": originator_id,
        "collateral_scope": command.collateral_scope,
        "collateral_type": collateral_type,
        "currency_scope": command.currency_scope,
        "risk_rating": _clean_optional(command.risk_rating),
        "purpose": _clean_optional(command.purpose),
        "loan_kind": command.loan_kind,
    }
    if not _has_effective_criterion(criteria):
        raise SmartInvestValidationError(
            "Choose at least one Smart Invest criterion before activating the rule."
        )
    return criteria


def _has_effective_criterion(criteria: dict[str, Any]) -> bool:
    return any(
        (
            criteria["minimum_yield_bps"] is not None,
            criteria["maximum_term_months"] is not None,
            criteria["originator_scope"] != OriginatorScope.ALL,
            criteria["collateral_scope"] != CollateralScope.ALL,
            criteria["currency_scope"] != CurrencyScope.ALL,
            bool(criteria["risk_rating"]),
            bool(criteria["purpose"]),
            criteria["loan_kind"] != LoanKind.ALL,
        )
    )


def _criteria_snapshot(rule: SmartInvestRule) -> dict[str, Any]:
    return {
        "minimum_yield_bps": rule.minimum_yield_bps,
        "maximum_term_months": rule.maximum_term_months,
        "originator_scope": rule.originator_scope,
        "originator_id": str(rule.originator_id) if rule.originator_id else None,
        "collateral_scope": rule.collateral_scope,
        "collateral_type": rule.collateral_type,
        "currency_scope": rule.currency_scope,
        "risk_rating": rule.risk_rating,
        "purpose": rule.purpose,
        "loan_kind": rule.loan_kind,
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


def opportunity_matches_criteria(opportunity: dict[str, Any], criteria: dict[str, Any]) -> bool:
    yield_bps = int(opportunity.get("yield_bps") or 0)
    term_months = int(opportunity.get("term_months") or 0)
    collateral_type = str(opportunity.get("collateral_type") or "")
    ltv_bps = opportunity.get("ltv_bps")
    product_type = str(opportunity.get("product_type") or "direct")
    is_unsecured = collateral_type == "unsecured_exception" or ltv_bps is None

    if criteria["minimum_yield_bps"] is not None and yield_bps < int(criteria["minimum_yield_bps"]):
        return False
    if criteria["maximum_term_months"] is not None and term_months > int(
        criteria["maximum_term_months"]
    ):
        return False
    if criteria["originator_scope"] == OriginatorScope.BANXUM and product_type != "direct":
        return False
    if criteria["originator_scope"] == OriginatorScope.SPECIFIC and str(
        opportunity.get("originator_id") or ""
    ) != str(criteria["originator_id"] or ""):
        return False
    if criteria["collateral_scope"] == CollateralScope.SECURED and is_unsecured:
        return False
    if criteria["collateral_scope"] == CollateralScope.UNSECURED and not is_unsecured:
        return False
    if criteria["collateral_scope"] == CollateralScope.SPECIFIC and collateral_type != str(
        criteria["collateral_type"]
    ):
        return False
    if criteria["currency_scope"] != CurrencyScope.ALL and str(opportunity.get("currency")) != str(
        criteria["currency_scope"]
    ):
        return False
    if criteria["risk_rating"] and str(opportunity.get("risk_rating")) != str(
        criteria["risk_rating"]
    ):
        return False
    if criteria["purpose"] and str(opportunity.get("purpose")) != str(criteria["purpose"]):
        return False
    if criteria["loan_kind"] == LoanKind.REFINANCING and not bool(
        opportunity.get("is_refinancing")
    ):
        return False
    if criteria["loan_kind"] == LoanKind.NEW and bool(opportunity.get("is_refinancing")):
        return False
    return True


def _matching_opportunities(rule: SmartInvestRule) -> tuple[list[dict[str, Any]], int]:
    opportunities = _marketplace_services().list_public_marketplace_loans(limit=10_000)
    criteria = _criteria_snapshot(rule)
    return (
        [item for item in opportunities if opportunity_matches_criteria(item, criteria)],
        len(opportunities),
    )


def get_smart_invest(*, actor: Model) -> dict[str, Any]:
    investor_user_id = _require_financial_access(actor)
    rule = SmartInvestRule.objects.filter(user_id=investor_user_id).first()
    matches: list[dict[str, Any]] = []
    open_opportunity_count = len(
        _marketplace_services().list_public_marketplace_loans(limit=10_000)
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
    now = timezone.now()
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
    rule.originator_scope = OriginatorScope.ALL
    rule.originator_id = None
    rule.collateral_scope = CollateralScope.ALL
    rule.collateral_type = ""
    rule.currency_scope = CurrencyScope.ALL
    rule.risk_rating = ""
    rule.purpose = ""
    rule.loan_kind = LoanKind.ALL
    rule.revision += 1
    rule.deactivated_at = timezone.now()
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
        "body": (
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
