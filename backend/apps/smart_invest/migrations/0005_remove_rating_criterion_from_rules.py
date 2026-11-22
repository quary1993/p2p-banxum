"""U33-DEC-16: remove the risk-rating criterion from saved Smart Invest rules.

Ratings are no longer part of the investor experience, so a saved rule must not
keep filtering on them in a hidden way. For every rule with a rating criterion:

- the criterion is emptied and the revision goes up by one;
- an append-only rule event records the removed values (the investor can see
  why the matches changed);
- an active rule that has no other effective criterion is deactivated, so it does
  not start to alert on every opportunity. Its other preferences stay saved.

Smart Invest never invests or reserves money, so nothing is placed for anyone.
The column is dropped by the next migration.
"""

from __future__ import annotations

import uuid

from django.db import migrations
from django.utils import timezone

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
LIST_CRITERIA = ("originators", "collateral", "currencies", "risk_ratings", "purposes", "loan_kinds")


def _restricts(selected, every_option=None) -> bool:
    if not selected:
        return False
    return every_option is None or not set(every_option).issubset(selected)


def _has_other_criterion(rule, purpose_values) -> bool:
    return any(
        (
            rule.minimum_yield_bps is not None,
            rule.maximum_term_months is not None,
            _restricts(rule.originators),
            _restricts(rule.collateral, ("any_secured", "unsecured")),
            _restricts(rule.currencies, ("CHF", "EUR")),
            _restricts(rule.purposes, purpose_values),
            _restricts(rule.loan_kinds, ("new", "refinancing")),
        )
    )


def plan_rating_removal(rule, purpose_values, now):
    """The row changes and the event fields for one rule with a rating criterion."""
    removed = [str(value) for value in rule.risk_ratings or []]
    snapshot = {
        "minimum_yield_bps": rule.minimum_yield_bps,
        "maximum_term_months": rule.maximum_term_months,
        **{field: [str(value) for value in getattr(rule, field) or []] for field in LIST_CRITERIA},
    }
    deactivate = bool(rule.is_active) and not _has_other_criterion(rule, purpose_values)
    revision = int(rule.revision) + 1
    changes = {"risk_ratings": [], "revision": revision}
    if deactivate:
        changes.update(is_active=False, deactivated_at=now)
    event = {
        "investor_user_id": rule.user_id,
        "actor_user_id": SYSTEM_ACTOR_ID,
        "event_type": "rating_criterion_removed",
        "revision": revision,
        "criteria_snapshot": snapshot,
        "metadata": {
            "decision": "U33-DEC-16",
            "removed_risk_ratings": removed,
            "deactivated": deactivate,
        },
    }
    return changes, event


def remove_rating_criterion(apps, schema_editor):
    rule_model = apps.get_model("smart_invest", "SmartInvestRule")
    event_model = apps.get_model("smart_invest", "SmartInvestRuleEvent")
    loan_model = apps.get_model("loans", "Loan")
    purpose_values = [value for value, _label in loan_model._meta.get_field("purpose").choices]
    now = timezone.now()
    for rule in rule_model.objects.exclude(risk_ratings=[]).iterator():
        if not rule.risk_ratings:
            continue
        changes, event = plan_rating_removal(rule, purpose_values, now)
        # queryset.update() keeps updated_at: the investor did not edit the rule.
        rule_model.objects.filter(pk=rule.pk).update(**changes)
        event_model.objects.create(rule_id=rule.pk, **event)


class Migration(migrations.Migration):
    dependencies = [
        ("smart_invest", "0004_remove_single_value_criteria"),
        ("loans", "0018_alter_loanevent_event_type"),
    ]

    operations = [
        migrations.RunPython(remove_rating_criterion, migrations.RunPython.noop),
    ]
