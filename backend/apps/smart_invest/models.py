from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class OriginatorScope(models.TextChoices):
    ALL = "all", "All sources"
    BANXUM = "banxum", "BANXUM direct lending"
    SPECIFIC = "specific", "Specific Loan Originator"


class CollateralScope(models.TextChoices):
    ALL = "all", "Any collateral"
    SECURED = "secured", "With collateral"
    UNSECURED = "unsecured", "Without collateral"
    SPECIFIC = "specific", "Specific collateral type"


class CurrencyScope(models.TextChoices):
    ALL = "all", "CHF and EUR"
    CHF = "CHF", "CHF"
    EUR = "EUR", "EUR"


class LoanKind(models.TextChoices):
    ALL = "all", "New lending and refinancing"
    NEW = "new", "New lending"
    REFINANCING = "refinancing", "Refinancing"


class SmartInvestRuleEventType(models.TextChoices):
    SAVED = "saved", "Saved and activated"
    DEACTIVATED = "deactivated", "Deactivated"


class SmartInvestRule(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="smart_invest_rule",
    )
    is_active = models.BooleanField(default=False)
    minimum_yield_bps = models.PositiveIntegerField(null=True, blank=True)
    maximum_term_months = models.PositiveIntegerField(null=True, blank=True)
    originator_scope = models.CharField(
        max_length=16,
        choices=OriginatorScope.choices,
        default=OriginatorScope.ALL,
    )
    originator_id = models.UUIDField(null=True, blank=True)
    collateral_scope = models.CharField(
        max_length=16,
        choices=CollateralScope.choices,
        default=CollateralScope.ALL,
    )
    collateral_type = models.CharField(max_length=64, blank=True)
    currency_scope = models.CharField(
        max_length=8,
        choices=CurrencyScope.choices,
        default=CurrencyScope.ALL,
    )
    risk_rating = models.CharField(max_length=32, blank=True)
    purpose = models.CharField(max_length=64, blank=True)
    loan_kind = models.CharField(
        max_length=16,
        choices=LoanKind.choices,
        default=LoanKind.ALL,
    )
    revision = models.PositiveIntegerField(default=0)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user_id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(minimum_yield_bps__isnull=True)
                    | models.Q(minimum_yield_bps__lte=100_000)
                ),
                name="smart_invest_minimum_yield_bps_bounded",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_term_months__isnull=True)
                    | models.Q(maximum_term_months__gte=1)
                ),
                name="smart_invest_maximum_term_positive",
            ),
        ]


class SmartInvestRuleEvent(AppendOnlyModel):
    rule = models.ForeignKey(
        SmartInvestRule,
        on_delete=models.PROTECT,
        related_name="events",
    )
    investor_user_id = models.UUIDField()
    actor_user_id = models.UUIDField()
    event_type = models.CharField(max_length=32, choices=SmartInvestRuleEventType.choices)
    revision = models.PositiveIntegerField()
    criteria_snapshot = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["investor_user_id", "occurred_at"]),
            models.Index(fields=["rule", "revision"]),
        ]


class SmartInvestMatchNotification(AppendOnlyModel):
    rule = models.ForeignKey(
        SmartInvestRule,
        on_delete=models.PROTECT,
        related_name="match_notifications",
    )
    investor_user_id = models.UUIDField()
    loan_id = models.UUIDField()
    product_type = models.CharField(max_length=32)
    outbox_message = models.ForeignKey(
        "platform_core.OutboxMessage",
        on_delete=models.PROTECT,
        related_name="smart_invest_match_notifications",
    )
    rule_revision = models.PositiveIntegerField()
    match_snapshot = models.JSONField(default=dict)
    notified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["notified_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["investor_user_id", "loan_id"],
                name="unique_smart_invest_match_notification",
            )
        ]
        indexes = [
            models.Index(fields=["investor_user_id", "notified_at"]),
            models.Index(fields=["loan_id", "notified_at"]),
        ]
