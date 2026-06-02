from __future__ import annotations

import uuid

from django.db import models
from django.db.models import F, Q

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class LedgerAccountType(models.TextChoices):
    COLLECTION_CASH = "collection_cash", "Collection cash"
    INVESTOR_BALANCE_LIABILITY = "investor_balance_liability", "Investor balance liability"
    GARANTA_ACCRUED_REVENUE = "garanta_accrued_revenue", "Garanta accrued revenue"
    SUSPENSE_UNMATCHED_CASH = "suspense_unmatched_cash", "Suspense/unmatched cash"
    WITHDRAWAL_PAYABLE = "withdrawal_payable", "Withdrawal payable"
    REFUND_PAYABLE = "refund_payable", "Refund payable"
    LOAN_FUNDING_ESCROW = "loan_funding_escrow", "Loan funding escrow"
    BORROWER_DISBURSEMENT_PAYABLE = (
        "borrower_disbursement_payable",
        "Borrower disbursement payable",
    )
    PLATFORM_FEE_REVENUE = "platform_fee_revenue", "Platform fee revenue"
    FX_CLEARING = "fx_clearing", "FX clearing"
    FX_FEE_REVENUE = "fx_fee_revenue", "FX fee revenue"
    FX_GAIN_LOSS = "fx_gain_loss", "FX gain/loss"
    RECOVERY_DISTRIBUTION_PAYABLE = (
        "recovery_distribution_payable",
        "Recovery distribution payable",
    )


class LedgerPostingSide(models.TextChoices):
    DEBIT = "debit", "Debit"
    CREDIT = "credit", "Credit"


class LedgerDirection(models.TextChoices):
    IN = "in", "In"
    OUT = "out", "Out"
    INTERNAL = "internal", "Internal"


class BankOperationType(models.TextChoices):
    LENDER_DEPOSIT = "lender_deposit", "Lender deposit"
    LENDER_WITHDRAWAL = "lender_withdrawal", "Lender withdrawal"
    BORROWER_LOAN_DISBURSEMENT = (
        "borrower_loan_disbursement",
        "Borrower loan disbursement",
    )
    BORROWER_REPAYMENT = "borrower_repayment", "Borrower repayment"
    GARANTA_OUT = "garanta_out", "Garanta out"
    GARANTA_IN = "garanta_in", "Garanta in"
    CURRENCY_EXCHANGE_EXTERNAL_SETTLEMENT = (
        "currency_exchange_external_settlement",
        "Currency exchange external settlement",
    )


class BankOperationStatus(models.TextChoices):
    RECONCILED = "reconciled", "Reconciled"
    PENDING_REVIEW = "pending_review", "Pending review"
    UNMATCHED = "unmatched", "Unmatched"
    RETURNED = "returned", "Returned"


class BalanceLotSourceType(models.TextChoices):
    DEPOSIT = "deposit", "Deposit"
    INSTALLMENT = "installment", "Installment"
    SECONDARY_MARKET_PROCEEDS = "secondary_market_proceeds", "Secondary-market proceeds"
    FX_PROCEEDS = "fx_proceeds", "FX proceeds"
    REFUND = "refund", "Refund"
    CORRECTION = "correction", "Correction"
    PENALTY_REVERSAL = "penalty_reversal", "Penalty reversal"


class BalanceLotStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    CONSUMED = "consumed", "Consumed"
    FROZEN = "frozen", "Frozen"
    PENALTY_MODE = "penalty_mode", "Penalty mode"
    PENALTY_EXHAUSTED = "penalty_exhausted", "Penalty exhausted"


class InvestorWithdrawalRequestStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    FINALIZED = "finalized", "Finalized"
    CANCELLED = "cancelled", "Cancelled"


class LedgerAccount(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=160, unique=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=64, choices=LedgerAccountType.choices)
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="ledger_accounts",
    )
    owner_type = models.CharField(max_length=64, blank=True)
    owner_id = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["account_type", "currency"]),
            models.Index(fields=["owner_type", "owner_id"]),
        ]

    def __str__(self) -> str:
        return self.code


class BankOperation(AppendOnlyModel, TimestampedModel):
    operation_type = models.CharField(max_length=64, choices=BankOperationType.choices)
    status = models.CharField(
        max_length=32,
        choices=BankOperationStatus.choices,
        default=BankOperationStatus.RECONCILED,
    )
    amount_minor = models.BigIntegerField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="bank_operations",
    )
    booking_date = models.DateField()
    value_date = models.DateField()
    collection_account_identifier = models.CharField(max_length=128, blank=True)
    payer_name = models.CharField(max_length=255, blank=True)
    payer_account_identifier = models.CharField(max_length=128, blank=True)
    payee_name = models.CharField(max_length=255, blank=True)
    payee_account_identifier = models.CharField(max_length=128, blank=True)
    bank_reference = models.CharField(max_length=160, blank=True)
    payment_reference = models.CharField(max_length=160, blank=True)
    linked_object_type = models.CharField(max_length=128, blank=True)
    linked_object_id = models.CharField(max_length=128, blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True)
    confirmed_by_admin_id = models.UUIDField()
    confirmed_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-confirmed_at", "-id"]
        indexes = [
            models.Index(fields=["operation_type", "status"]),
            models.Index(fields=["currency", "value_date"]),
            models.Index(fields=["bank_reference"]),
            models.Index(fields=["payment_reference"]),
            models.Index(fields=["linked_object_type", "linked_object_id"]),
        ]


class LedgerJournalEntry(AppendOnlyModel, TimestampedModel):
    event_type = models.CharField(max_length=128)
    direction = models.CharField(max_length=16, choices=LedgerDirection.choices)
    booking_date = models.DateField()
    value_date = models.DateField()
    effective_at = models.DateTimeField()
    received_at = models.DateTimeField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="ledger_journal_entries",
    )
    gross_amount_minor = models.BigIntegerField()
    net_amount_minor = models.BigIntegerField()
    source_type = models.CharField(max_length=128)
    source_id = models.CharField(max_length=128)
    lender_user_id = models.UUIDField(null=True, blank=True)
    borrower_id = models.UUIDField(null=True, blank=True)
    loan_id = models.UUIDField(null=True, blank=True)
    bank_operation = models.ForeignKey(
        BankOperation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    bank_reference = models.CharField(max_length=160, blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True)
    actor_type = models.CharField(max_length=64)
    actor_id = models.CharField(max_length=128)
    tax_metadata = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversals",
    )
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["booking_date", "created_at", "id"]
        indexes = [
            models.Index(fields=["event_type", "booking_date"]),
            models.Index(fields=["currency", "booking_date"]),
            models.Index(fields=["lender_user_id", "currency"]),
            models.Index(fields=["source_type", "source_id"]),
            models.Index(fields=["bank_reference"]),
        ]


class LedgerPosting(AppendOnlyModel, TimestampedModel):
    journal_entry = models.ForeignKey(
        LedgerJournalEntry,
        on_delete=models.PROTECT,
        related_name="postings",
    )
    account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name="postings",
    )
    side = models.CharField(max_length=16, choices=LedgerPostingSide.choices)
    amount_minor = models.BigIntegerField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="ledger_postings",
    )
    memo = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["journal_entry", "side", "id"]
        indexes = [
            models.Index(fields=["journal_entry", "side"]),
            models.Index(fields=["account", "currency"]),
        ]


class InvestorBalanceLot(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investor_user_id = models.UUIDField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="investor_balance_lots",
    )
    source_journal_entry = models.ForeignKey(
        LedgerJournalEntry,
        on_delete=models.PROTECT,
        related_name="balance_lots",
    )
    source_type = models.CharField(max_length=64, choices=BalanceLotSourceType.choices)
    source_id = models.CharField(max_length=128)
    status = models.CharField(
        max_length=32,
        choices=BalanceLotStatus.choices,
        default=BalanceLotStatus.AVAILABLE,
    )
    received_at = models.DateTimeField()
    investment_deadline_at = models.DateTimeField()
    withdrawal_deadline_at = models.DateTimeField()
    original_amount_minor = models.BigIntegerField()
    available_amount_minor = models.BigIntegerField()
    invested_amount_minor = models.BigIntegerField(default=0)
    withdrawn_amount_minor = models.BigIntegerField(default=0)
    penalized_amount_minor = models.BigIntegerField(default=0)
    lineage = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["received_at", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(original_amount_minor__gte=0)
                & Q(available_amount_minor__gte=0)
                & Q(invested_amount_minor__gte=0)
                & Q(withdrawn_amount_minor__gte=0)
                & Q(penalized_amount_minor__gte=0),
                name="ledger_balance_lot_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(
                    original_amount_minor=F("available_amount_minor")
                    + F("invested_amount_minor")
                    + F("withdrawn_amount_minor")
                    + F("penalized_amount_minor")
                ),
                name="ledger_balance_lot_amounts_conserved",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status__in=[BalanceLotStatus.CONSUMED, BalanceLotStatus.PENALTY_EXHAUSTED])
                    | Q(available_amount_minor=0)
                ),
                name="ledger_balance_lot_terminal_zero_available",
            ),
        ]
        indexes = [
            models.Index(fields=["investor_user_id", "currency", "status"]),
            models.Index(fields=["currency", "investment_deadline_at"]),
            models.Index(fields=["currency", "withdrawal_deadline_at"]),
            models.Index(fields=["source_type", "source_id"]),
        ]


class InvestorWithdrawalRequest(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investor_user_id = models.UUIDField()
    status = models.CharField(
        max_length=32,
        choices=InvestorWithdrawalRequestStatus.choices,
        default=InvestorWithdrawalRequestStatus.REQUESTED,
    )
    amount_minor = models.BigIntegerField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="investor_withdrawal_requests",
    )
    destination_iban = models.CharField(max_length=128)
    destination_account_name = models.CharField(max_length=255, blank=True)
    requested_by_user_id = models.UUIDField()
    requested_at = models.DateTimeField()
    request_journal_entry = models.ForeignKey(
        LedgerJournalEntry,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="withdrawal_requests_opened",
    )
    is_forced = models.BooleanField(default=False)
    lot_allocations = models.JSONField(default=list, blank=True)
    bank_operation = models.ForeignKey(
        BankOperation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="withdrawal_requests",
    )
    finalization_journal_entry = models.ForeignKey(
        LedgerJournalEntry,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="withdrawal_requests_finalized",
    )
    finalized_by_admin_id = models.UUIDField(null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    bank_reference = models.CharField(max_length=160, blank=True)
    payment_reference = models.CharField(max_length=160, blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0),
                name="ledger_withdrawal_request_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["investor_user_id", "currency", "status"]),
            models.Index(fields=["status", "requested_at"]),
            models.Index(fields=["finalized_at"]),
            models.Index(fields=["bank_reference"]),
        ]


class ReconciliationSnapshot(AppendOnlyModel, TimestampedModel):
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="reconciliation_snapshots",
    )
    as_of_date = models.DateField()
    bank_stated_balance_minor = models.BigIntegerField()
    investor_balance_liability_minor = models.BigIntegerField()
    garanta_accrued_revenue_minor = models.BigIntegerField(default=0)
    suspense_unmatched_cash_minor = models.BigIntegerField(default=0)
    pending_exception_balance_minor = models.BigIntegerField(default=0)
    reconciliation_difference_minor = models.BigIntegerField()
    created_by_admin_id = models.UUIDField()
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-as_of_date", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["currency", "as_of_date"]),
            models.Index(fields=["created_by_admin_id", "created_at"]),
        ]
