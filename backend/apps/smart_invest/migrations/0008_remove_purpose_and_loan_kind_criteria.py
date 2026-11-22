# IP of Webby-Soft SRL.
"""U33-DEC-19: remove the purpose and loan-kind criteria from saved Smart Invest rules.

Smart Invest no longer filters by purpose or by new lending / refinancing, so a saved
rule must not keep doing it in a hidden way. For every rule with one of these criteria:

- the criteria are emptied and the revision goes up by one;
- an append-only rule event records the removed values;
- an active rule that has no other effective criterion is paused (its other
  preferences stay saved), so it does not start to alert on every opportunity.

Smart Invest never invests or reserves money, so nothing is placed for anyone.
The columns are dropped by the next migration.
"""

from __future__ import annotations

import uuid

from django.db import migrations
from django.utils import timezone

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
LIST_CRITERIA = ("originators", "collateral", "currencies", "countries", "purposes", "loan_kinds")


def _restricts(selected, every_option=None) -> bool:
    if not selected:
        return False
    return every_option is None or not set(every_option).issubset(selected)


def _has_other_criterion(rule) -> bool:
    return any(
        (
            rule.minimum_yield_bps is not None,
            rule.maximum_term_months is not None,
            rule.maximum_ltv_bps is not None,
            _restricts(rule.originators),
            _restricts(rule.collateral, ("any_secured", "unsecured")),
            _restricts(rule.currencies, ("CHF", "EUR")),
            _restricts(rule.countries),
        )
    )


def plan_retired_criteria_removal(rule, now):
    """The row changes and the event fields for one rule with a purpose or loan-kind criterion."""
    removed_purposes = [str(value) for value in rule.purposes or []]
    removed_loan_kinds = [str(value) for value in rule.loan_kinds or []]
    snapshot = {
        "minimum_yield_bps": rule.minimum_yield_bps,
        "maximum_term_months": rule.maximum_term_months,
        "maximum_ltv_bps": rule.maximum_ltv_bps,
        "preferred_amount_minor": rule.preferred_amount_minor,
        **{field: [str(value) for value in getattr(rule, field) or []] for field in LIST_CRITERIA},
    }
    pause = bool(rule.is_active) and not _has_other_criterion(rule)
    revision = int(rule.revision) + 1
    changes = {"purposes": [], "loan_kinds": [], "revision": revision}
    if pause:
        changes.update(is_active=False, deactivated_at=now)
    event = {
        "investor_user_id": rule.user_id,
        "actor_user_id": SYSTEM_ACTOR_ID,
        "event_type": "retired_criteria_removed",
        "revision": revision,
        "criteria_snapshot": snapshot,
        "metadata": {
            "decision": "U33-DEC-19",
            "removed_purposes": removed_purposes,
            "removed_loan_kinds": removed_loan_kinds,
            "paused": pause,
        },
    }
    return changes, event


def remove_retired_criteria(apps, schema_editor):
    rule_model = apps.get_model("smart_invest", "SmartInvestRule")
    event_model = apps.get_model("smart_invest", "SmartInvestRuleEvent")
    now = timezone.now()
    for rule in rule_model.objects.all().iterator():
        if not rule.purposes and not rule.loan_kinds:
            continue
        changes, event = plan_retired_criteria_removal(rule, now)
        # queryset.update() keeps updated_at: the investor did not edit the rule.
        rule_model.objects.filter(pk=rule.pk).update(**changes)
        event_model.objects.create(rule_id=rule.pk, **event)


class Migration(migrations.Migration):
    dependencies = [
        ("smart_invest", "0007_smart_invest_pause_and_new_criteria"),
    ]

    operations = [
        migrations.RunPython(remove_retired_criteria, migrations.RunPython.noop),
    ]
