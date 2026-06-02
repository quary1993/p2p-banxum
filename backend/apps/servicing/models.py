from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class BorrowerRepaymentEventType(models.TextChoices):
    REGULAR_INSTALLMENT = "regular_installment", "Regular installment"
    PARTIAL_INSTALLMENT = "partial_installment", "Partial installment"


class BorrowerRepaymentEvent(AppendOnlyModel, TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="borrower_repayment_events",
    )
    installment = models.ForeignKey(
        "loans.LoanInstallment",
        on_delete=models.PROTECT,
        related_name="borrower_repayment_events",
    )
    event_type = models.CharField(max_length=64, choices=BorrowerRepaymentEventType.choices)
    amount_minor = models.BigIntegerField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="borrower_repayment_events",
    )
    booking_date = models.DateField()
    value_date = models.DateField()
    received_at = models.DateTimeField()
    expected_due_minor = models.BigIntegerField()
    interest_applied_minor = models.BigIntegerField(default=0)
    principal_applied_minor = models.BigIntegerField(default=0)
    fees_applied_minor = models.BigIntegerField(default=0)
    penalties_applied_minor = models.BigIntegerField(default=0)
    remaining_installment_interest_minor = models.BigIntegerField(default=0)
    remaining_installment_principal_minor = models.BigIntegerField(default=0)
    warning_acknowledged = models.BooleanField(default=False)
    bank_operation = models.ForeignKey(
        "ledger.BankOperation",
        on_delete=models.PROTECT,
        related_name="borrower_repayment_events",
    )
    journal_entry = models.ForeignKey(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        related_name="borrower_repayment_events",
    )
    created_by_admin_id = models.UUIDField()
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-value_date", "-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0),
                name="servicing_repayment_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(expected_due_minor__gte=0)
                    & models.Q(interest_applied_minor__gte=0)
                    & models.Q(principal_applied_minor__gte=0)
                    & models.Q(fees_applied_minor__gte=0)
                    & models.Q(penalties_applied_minor__gte=0)
                    & models.Q(remaining_installment_interest_minor__gte=0)
                    & models.Q(remaining_installment_principal_minor__gte=0)
                ),
                name="servicing_repayment_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    amount_minor=models.F("interest_applied_minor")
                    + models.F("principal_applied_minor")
                    + models.F("fees_applied_minor")
                    + models.F("penalties_applied_minor")
                ),
                name="servicing_repayment_amount_allocated",
            ),
        ]
        indexes = [
            models.Index(fields=["loan", "value_date"]),
            models.Index(fields=["installment", "value_date"]),
            models.Index(fields=["currency", "value_date"]),
            models.Index(fields=["bank_operation"]),
        ]


class InvestorRepaymentDistributionLine(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repayment_event = models.ForeignKey(
        BorrowerRepaymentEvent,
        on_delete=models.PROTECT,
        related_name="distribution_lines",
    )
    holding = models.ForeignKey(
        "holdings.InvestorLoanHolding",
        on_delete=models.PROTECT,
        related_name="repayment_distribution_lines",
    )
    investor_user_id = models.UUIDField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="repayment_distribution_lines",
    )
    balance_lot = models.ForeignKey(
        "ledger.InvestorBalanceLot",
        on_delete=models.PROTECT,
        related_name="repayment_distribution_lines",
    )
    amount_minor = models.BigIntegerField()
    principal_minor = models.BigIntegerField(default=0)
    interest_minor = models.BigIntegerField(default=0)
    fee_minor = models.BigIntegerField(default=0)
    current_principal_before_minor = models.BigIntegerField()
    current_principal_after_minor = models.BigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["repayment_event", "occurred_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0),
                name="servicing_distribution_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(principal_minor__gte=0)
                    & models.Q(interest_minor__gte=0)
                    & models.Q(fee_minor__gte=0)
                    & models.Q(current_principal_before_minor__gte=0)
                    & models.Q(current_principal_after_minor__gte=0)
                ),
                name="servicing_distribution_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    amount_minor=models.F("principal_minor")
                    + models.F("interest_minor")
                    - models.F("fee_minor")
                ),
                name="servicing_distribution_amount_reconciles",
            ),
        ]
        indexes = [
            models.Index(fields=["repayment_event", "investor_user_id"]),
            models.Index(fields=["holding", "occurred_at"]),
            models.Index(fields=["investor_user_id", "occurred_at"]),
            models.Index(fields=["balance_lot"]),
        ]
