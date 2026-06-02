from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class PrimaryInvestmentOrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    BALANCE_ALLOCATED = "balance_allocated", "Balance allocated"
    PARTIALLY_ALLOCATED = "partially_allocated", "Partially allocated"
    BALANCE_RELEASED = "balance_released", "Balance released"
    CLOSED_INVESTED = "closed_invested", "Closed invested"
    CLOSED_NOT_INVESTED = "closed_not_invested", "Closed not invested"


class PrimaryInvestmentOrderEventType(models.TextChoices):
    CREATED = "created", "Created"
    BALANCE_ALLOCATED = "balance_allocated", "Balance allocated"
    BALANCE_RELEASED = "balance_released", "Balance released"
    CLOSED_INVESTED = "closed_invested", "Closed invested"
    CLOSED_NOT_INVESTED = "closed_not_invested", "Closed not invested"
    LOAN_CLOSED = "loan_closed", "Loan closed"


class PrimaryLoanCloseType(models.TextChoices):
    FULL = "full", "Full"
    PARTIAL = "partial", "Partial"


class PrimaryInvestmentOrder(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="primary_investment_orders",
    )
    investor_user_id = models.UUIDField()
    status = models.CharField(
        max_length=64,
        choices=PrimaryInvestmentOrderStatus.choices,
        default=PrimaryInvestmentOrderStatus.PENDING,
    )
    requested_amount_minor = models.BigIntegerField()
    allocated_amount_minor = models.BigIntegerField(default=0)
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="primary_investment_orders",
    )
    document_acceptance = models.ForeignKey(
        "documents.DocumentAcceptanceEvidence",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="primary_investment_orders",
    )
    reservation_journal_entry = models.ForeignKey(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="primary_investment_orders_reserved",
    )
    release_journal_entry = models.ForeignKey(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="primary_investment_orders_released",
    )
    lot_allocations = models.JSONField(default=list, blank=True)
    created_by_user_id = models.UUIDField()
    allocated_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_admin_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(requested_amount_minor__gt=0),
                name="primary_order_requested_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount_minor__gte=0),
                name="primary_order_allocated_amount_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["loan", "status", "created_at"]),
            models.Index(fields=["investor_user_id", "status", "created_at"]),
            models.Index(fields=["currency", "status"]),
        ]


class PrimaryInvestmentOrderEvent(AppendOnlyModel):
    order = models.ForeignKey(
        PrimaryInvestmentOrder,
        on_delete=models.PROTECT,
        related_name="events",
    )
    loan_id = models.UUIDField()
    event_type = models.CharField(
        max_length=64,
        choices=PrimaryInvestmentOrderEventType.choices,
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
            models.Index(fields=["order", "occurred_at"]),
            models.Index(fields=["loan_id", "event_type"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]


class PrimaryLoanClose(AppendOnlyModel, TimestampedModel):
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="primary_market_closes",
    )
    close_type = models.CharField(max_length=32, choices=PrimaryLoanCloseType.choices)
    accepted_principal_minor = models.BigIntegerField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="primary_market_closes",
    )
    allocated_order_count = models.PositiveIntegerField()
    closed_not_invested_order_count = models.PositiveIntegerField(default=0)
    borrower_success_fee_bps = models.PositiveIntegerField()
    borrower_success_fee_minor = models.BigIntegerField()
    borrower_disbursement_payable_minor = models.BigIntegerField()
    funding_close_journal_entry = models.ForeignKey(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        related_name="primary_market_closes",
    )
    created_by_admin_id = models.UUIDField()
    closed_at = models.DateTimeField()
    reason = models.TextField(blank=True)
    investor_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-closed_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(accepted_principal_minor__gt=0),
                name="primary_close_accepted_principal_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(borrower_success_fee_minor__gte=0),
                name="primary_close_success_fee_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(borrower_disbursement_payable_minor__gte=0),
                name="primary_close_disbursement_payable_nonnegative",
            ),
            models.UniqueConstraint(fields=["loan"], name="unique_primary_close_per_loan"),
        ]
        indexes = [
            models.Index(fields=["loan", "closed_at"]),
            models.Index(fields=["currency", "closed_at"]),
            models.Index(fields=["created_by_admin_id", "closed_at"]),
        ]
