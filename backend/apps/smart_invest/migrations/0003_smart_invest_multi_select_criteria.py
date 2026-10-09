"""Turn the single-choice Smart Invest criteria into multi-select lists.

Every existing rule is converted to the list form that matches exactly the
same opportunities as before (an empty list means no restriction):

- currency_scope: all -> [], CHF -> ["CHF"], EUR -> ["EUR"]
- collateral_scope: all -> [], secured -> ["any_secured"], unsecured -> ["unsecured"],
  specific + collateral_type T -> [T] ("unsecured_exception" -> ["unsecured"])
- risk_rating / purpose: "" -> [], value -> [value]
- loan_kind: all -> [], new -> ["new"], refinancing -> ["refinancing"]
- originator_scope: all -> [], banxum -> ["banxum"], specific + originator_id -> [id]

Rule revisions, activation timestamps and the append-only rule events are left
untouched: the conversion changes the storage shape, not the investor's criteria.
The old single-value columns are dropped by the next migration.
"""

from __future__ import annotations

from django.db import migrations, models


def _single(value: str, *, unrestricted: str = "") -> list[str]:
    value = (value or "").strip()
    return [] if value in ("", unrestricted) else [value]


def _collateral(scope: str, collateral_type: str) -> list[str]:
    if scope == "secured":
        return ["any_secured"]
    if scope == "unsecured":
        return ["unsecured"]
    if scope == "specific":
        value = (collateral_type or "").strip()
        if value == "unsecured_exception":
            return ["unsecured"]
        return [value] if value else []
    return []


def _originators(scope: str, originator_id: object) -> list[str]:
    if scope == "banxum":
        return ["banxum"]
    if scope == "specific" and originator_id:
        return [str(originator_id)]
    return []


def convert_to_lists(apps, schema_editor):
    rule_model = apps.get_model("smart_invest", "SmartInvestRule")
    for rule in rule_model.objects.all().iterator():
        # queryset.update() keeps updated_at: the investor did not change the rule.
        rule_model.objects.filter(pk=rule.pk).update(
            currencies=_single(rule.currency_scope, unrestricted="all"),
            collateral=_collateral(rule.collateral_scope, rule.collateral_type),
            risk_ratings=_single(rule.risk_rating),
            purposes=_single(rule.purpose),
            loan_kinds=_single(rule.loan_kind, unrestricted="all"),
            originators=_originators(rule.originator_scope, rule.originator_id),
        )


def convert_to_single_values(apps, schema_editor):
    """Best-effort reverse: a list with several values widens to "all"."""
    rule_model = apps.get_model("smart_invest", "SmartInvestRule")
    for rule in rule_model.objects.all().iterator():
        currencies = list(rule.currencies or [])
        collateral = list(rule.collateral or [])
        originators = list(rule.originators or [])
        risk_ratings = list(rule.risk_ratings or [])
        purposes = list(rule.purposes or [])
        loan_kinds = list(rule.loan_kinds or [])
        collateral_scope, collateral_type = "all", ""
        if collateral == ["any_secured"]:
            collateral_scope = "secured"
        elif collateral == ["unsecured"]:
            collateral_scope = "unsecured"
        elif len(collateral) == 1:
            collateral_scope, collateral_type = "specific", collateral[0]
        originator_scope, originator_id = "all", None
        if originators == ["banxum"]:
            originator_scope = "banxum"
        elif len(originators) == 1:
            originator_scope, originator_id = "specific", originators[0]
        rule_model.objects.filter(pk=rule.pk).update(
            currency_scope=currencies[0] if len(currencies) == 1 else "all",
            collateral_scope=collateral_scope,
            collateral_type=collateral_type,
            risk_rating=risk_ratings[0] if len(risk_ratings) == 1 else "",
            purpose=purposes[0] if len(purposes) == 1 else "",
            loan_kind=loan_kinds[0] if len(loan_kinds) == 1 else "all",
            originator_scope=originator_scope,
            originator_id=originator_id,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("smart_invest", "0002_smart_invest_append_only_guards"),
    ]

    operations = [
        migrations.AddField(
            model_name="smartinvestrule",
            name="originators",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="smartinvestrule",
            name="collateral",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="smartinvestrule",
            name="currencies",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="smartinvestrule",
            name="risk_ratings",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="smartinvestrule",
            name="purposes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="smartinvestrule",
            name="loan_kinds",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(convert_to_lists, convert_to_single_values),
    ]
