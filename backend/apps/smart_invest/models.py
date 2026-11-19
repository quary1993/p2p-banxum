from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from backend.apps.platform_core.models.base import (
    AppendOnlyModel,
    PlatformDateTimeField,
    TimestampedModel,
)

# Smart-Invest criteria are multi-select lists. An empty list never restricts
# matching; a non-empty list matches an opportunity carrying any listed value.
SMART_INVEST_BANXUM_SOURCE = "banxum"


class SmartInvestCurrency(models.TextChoices):
    CHF = "CHF", "CHF"
    EUR = "EUR", "EUR"


class SmartInvestCollateralOption(models.TextChoices):
    """Collateral tokens beside the loan catalog's own collateral types."""

    ANY_SECURED = "any_secured", "With collateral (any type)"
    UNSECURED = "unsecured", "No collateral (unsecured)"


class SmartInvestRepaymentOption(models.TextChoices):
    """18.3: the design's Repayments step (U33-DEC-11 groups; final types in 18.6)."""

    # Periodic repayments: interest during the term, principal at the end.
    INTEREST_ONLY = "interest_only", "Periodic repayments: interest only"
    # Periodic repayments: part of the principal and interest with each payment.
    PRINCIPAL_AND_INTEREST = "principal_and_interest", "Periodic repayments: principal and interest"
    # Payment at maturity: principal and interest in one payment at the end.
    AT_MATURITY = "at_maturity", "Payment at maturity"


class SmartInvestRuleEventType(models.TextChoices):
    SAVED = "saved", "Saved and activated"
    # Before U33-DEC-19 switching off cleared the preferences; now the investor pauses.
    DEACTIVATED = "deactivated", "Deactivated"
    PAUSED = "paused", "Paused"
    RESUMED = "resumed", "Resumed"
    # U33-DEC-16: the migration that removed the risk-rating criterion from saved rules.
    RATING_CRITERION_REMOVED = "rating_criterion_removed", "Risk-rating criterion removed"
    # U33-DEC-19: the migration that removed the purpose and loan-kind criteria.
    RETIRED_CRITERIA_REMOVED = "retired_criteria_removed", "Purpose and loan-kind criteria removed"
    # U33-DEC-30: the investor changed the in-app / email channels of the match alerts.
    CHANNELS_CHANGED = "channels_changed", "Notification channels changed"


class SmartInvestRule(TimestampedModel):
    """One set of Smart Invest preferences per investor (U33-DEC-19).

    Active: matches are shown and new matches are announced. Paused (`is_active` false with
    the preferences kept, `deactivated_at` = when paused): no marks, counters or alerts until
    the investor resumes. 18.3: an active rule without any limiting criterion matches every open
    opportunity; a paused rule without one counts as not set up.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="smart_invest_rule",
    )
    is_active = models.BooleanField(default=False)
    minimum_yield_bps = models.PositiveIntegerField(null=True, blank=True)
    maximum_term_months = models.PositiveIntegerField(null=True, blank=True)
    # U33-DEC-19: an opportunity without a loan-to-value figure does not match a limit.
    maximum_ltv_bps = models.PositiveIntegerField(null=True, blank=True)
    # Borrower countries as the opportunities carry them; empty = any country.
    countries = models.JSONField(default=list, blank=True)
    # U33-DEC-19: optional usual amount, in minor units of each selected currency. It only
    # prepares the amount on an opportunity page; it never excludes an opportunity.
    preferred_amount_minor = models.PositiveBigIntegerField(null=True, blank=True)
    # "banxum" for BANXUM direct loans and/or Loan Originator ids.
    originators = models.JSONField(default=list, blank=True)
    # "any_secured", "unsecured" and/or loan collateral types.
    collateral = models.JSONField(default=list, blank=True)
    currencies = models.JSONField(default=list, blank=True)
    # 18.3: SmartInvestRepaymentOption values; empty = no preference.
    repayment = models.JSONField(default=list, blank=True)
    revision = models.PositiveIntegerField(default=0)
    # U33-DEC-30: each channel of the match alerts has its own switch. Off stops only that
    # channel: matching, the matches list and service messages go on. Pause stops both.
    notify_in_app = models.BooleanField(default=True)
    notify_email = models.BooleanField(default=True)
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
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_ltv_bps__isnull=True)
                    | models.Q(maximum_ltv_bps__gte=1, maximum_ltv_bps__lte=10_000)
                ),
                name="smart_invest_maximum_ltv_bounded",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(preferred_amount_minor__isnull=True)
                    | models.Q(preferred_amount_minor__gte=1)
                ),
                name="smart_invest_preferred_amount_positive",
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
    # Empty when both channels were off (U33-DEC-30): the match is recorded, nothing is sent.
    outbox_message = models.ForeignKey(
        "platform_core.OutboxMessage",
        on_delete=models.PROTECT,
        related_name="smart_invest_match_notifications",
        null=True,
        blank=True,
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
