from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class InvestorLoanHoldingStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    TRANSFERRED = "transferred", "Transferred"
    CLOSED = "closed", "Closed"


class InvestorLoanHoldingSourceType(models.TextChoices):
    PRIMARY_MARKET = "primary_market", "Primary market"
    SECONDARY_MARKET = "secondary_market", "Secondary market"
    MANUAL_ADMIN = "manual_admin", "Manual admin"


class InvestorLoanHoldingEventType(models.TextChoices):
    CREATED = "created", "Created"
    TRANSFERRED = "transferred", "Transferred"
    PRINCIPAL_UPDATED = "principal_updated", "Principal updated"
    CLOSED = "closed", "Closed"


class InvestorLoanHolding(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="investor_holdings",
    )
    investor_user_id = models.UUIDField()
    source_type = models.CharField(
        max_length=64,
        choices=InvestorLoanHoldingSourceType.choices,
    )
    source_id = models.CharField(max_length=128)
    source_primary_order = models.ForeignKey(
        "marketplace_primary.PrimaryInvestmentOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_holdings",
    )
    status = models.CharField(
        max_length=32,
        choices=InvestorLoanHoldingStatus.choices,
        default=InvestorLoanHoldingStatus.ACTIVE,
    )
    original_principal_minor = models.BigIntegerField()
    current_principal_minor = models.BigIntegerField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="investor_loan_holdings",
    )
    loan_share_ppm = models.PositiveIntegerField()
    assignment_effective_at = models.DateTimeField()
    created_by_admin_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["loan", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(original_principal_minor__gt=0),
                name="holding_original_principal_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(current_principal_minor__gte=0),
                name="holding_current_principal_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(current_principal_minor__lte=models.F("original_principal_minor")),
                name="holding_current_principal_not_above_original",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id"],
                name="unique_holding_source",
            ),
        ]
        indexes = [
            models.Index(fields=["loan", "status"]),
            models.Index(fields=["investor_user_id", "status"]),
            models.Index(fields=["currency", "status"]),
            models.Index(fields=["source_type", "source_id"]),
        ]


class InvestorLoanHoldingEvent(AppendOnlyModel):
    holding = models.ForeignKey(
        InvestorLoanHolding,
        on_delete=models.PROTECT,
        related_name="events",
    )
    loan_id = models.UUIDField()
    investor_user_id = models.UUIDField()
    event_type = models.CharField(
        max_length=64,
        choices=InvestorLoanHoldingEventType.choices,
    )
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    previous_status = models.CharField(max_length=64, blank=True)
    new_status = models.CharField(max_length=64, blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["holding", "occurred_at"]),
            models.Index(fields=["loan_id", "event_type"]),
            models.Index(fields=["investor_user_id", "occurred_at"]),
        ]
