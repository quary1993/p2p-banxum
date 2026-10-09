from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from backend.apps.platform_core.models.base import (
    AppendOnlyModel,
    PlatformDateTimeField,
    TimestampedModel,
)

# Smart Invest criteria are multi-select lists. An empty list never restricts
# matching; a non-empty list matches an opportunity carrying any listed value.
SMART_INVEST_BANXUM_SOURCE = "banxum"


class SmartInvestCurrency(models.TextChoices):
    CHF = "CHF", "CHF"
    EUR = "EUR", "EUR"


class SmartInvestLoanKind(models.TextChoices):
    NEW = "new", "New lending"
    REFINANCING = "refinancing", "Refinancing"


class SmartInvestCollateralOption(models.TextChoices):
    """Collateral tokens beside the loan catalog's own collateral types."""

    ANY_SECURED = "any_secured", "With collateral (any type)"
    UNSECURED = "unsecured", "No collateral (unsecured)"


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
    # "banxum" for BANXUM direct loans and/or Loan Originator ids.
    originators = models.JSONField(default=list, blank=True)
    # "any_secured", "unsecured" and/or loan collateral types.
    collateral = models.JSONField(default=list, blank=True)
    currencies = models.JSONField(default=list, blank=True)
    risk_ratings = models.JSONField(default=list, blank=True)
    purposes = models.JSONField(default=list, blank=True)
    loan_kinds = models.JSONField(default=list, blank=True)
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
    occurred_at = PlatformDateTimeField(auto_now_add=True)

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
    notified_at = PlatformDateTimeField(auto_now_add=True)

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
