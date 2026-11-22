from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import (
    AppendOnlyModel,
    PlatformDateTimeField,
    TimestampedModel,
)


class BorrowerRepaymentEventType(models.TextChoices):
    REGULAR_INSTALLMENT = "regular_installment", "Regular installment"
    PARTIAL_INSTALLMENT = "partial_installment", "Partial installment"
    EARLY_REPAYMENT = "early_repayment", "Early repayment"


class LoanRiskNoteVisibility(models.TextChoices):
    INTERNAL = "internal", "Internal"
    PUBLIC = "public", "Public"


class LoanRiskNoteType(models.TextChoices):
    INTERNAL_NOTE = "internal_note", "Internal note"
    PUBLIC_UPDATE = "public_update", "Public update"
    DEFAULT_UPDATE = "default_update", "Default update"
    RECOVERY_UPDATE = "recovery_update", "Recovery update"
    DOCUMENT_NOTE = "document_note", "Document note"


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
    future_principal_applied_minor = models.BigIntegerField(default=0)
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
                    & models.Q(future_principal_applied_minor__gte=0)
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
                    + models.F("future_principal_applied_minor")
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
    # 18.6: the investor's part of penalty X (a separate component in the ledger and statements).
    penalty_minor = models.BigIntegerField(default=0)
    fee_minor = models.BigIntegerField(default=0)
    current_principal_before_minor = models.BigIntegerField()
    current_principal_after_minor = models.BigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = PlatformDateTimeField(auto_now_add=True)

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
                    & models.Q(penalty_minor__gte=0)
                    & models.Q(fee_minor__gte=0)
                    & models.Q(current_principal_before_minor__gte=0)
                    & models.Q(current_principal_after_minor__gte=0)
                ),
                name="servicing_distribution_amounts_nonnegative_v2",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    amount_minor=models.F("principal_minor")
                    + models.F("interest_minor")
                    + models.F("penalty_minor")
                    - models.F("fee_minor")
                ),
                name="servicing_distribution_amount_reconciles_v2",
            ),
        ]
        indexes = [
            models.Index(fields=["repayment_event", "investor_user_id"]),
            models.Index(fields=["holding", "occurred_at"]),
            models.Index(fields=["investor_user_id", "occurred_at"]),
            models.Index(fields=["balance_lot"]),
        ]


class LoanRecoveryEvent(AppendOnlyModel, TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="recovery_events",
    )
    borrower_id = models.UUIDField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="loan_recovery_events",
    )
    gross_recovered_minor = models.BigIntegerField()
    externally_deducted_costs_minor = models.BigIntegerField(default=0)
    net_received_minor = models.BigIntegerField()
    third_party_costs_from_received_minor = models.BigIntegerField(default=0)
    recovery_fee_applied = models.BooleanField(default=False)
    recovery_fee_bps = models.PositiveIntegerField(default=0)
    recovery_fee_base_minor = models.BigIntegerField(default=0)
    recovery_fee_minor = models.BigIntegerField(default=0)
    net_available_for_distribution_minor = models.BigIntegerField()
    principal_recovered_minor = models.BigIntegerField(default=0)
    contractual_interest_recovered_minor = models.BigIntegerField(default=0)
    default_interest_recovered_minor = models.BigIntegerField(default=0)
    penalties_recovered_minor = models.BigIntegerField(default=0)
    other_costs_recovered_minor = models.BigIntegerField(default=0)
    rounding_difference_minor = models.BigIntegerField(default=0)
    booking_date = models.DateField()
    value_date = models.DateField()
    received_at = models.DateTimeField()
    bank_operation = models.ForeignKey(
        "ledger.BankOperation",
        on_delete=models.PROTECT,
        related_name="loan_recovery_events",
    )
    journal_entry = models.ForeignKey(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        related_name="loan_recovery_events",
    )
    recovery_waterfall_config = models.JSONField(default=dict, blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by_admin_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-value_date", "-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(gross_recovered_minor__gt=0)
                    & models.Q(externally_deducted_costs_minor__gte=0)
                    & models.Q(net_received_minor__gt=0)
                    & models.Q(third_party_costs_from_received_minor__gte=0)
                    & models.Q(recovery_fee_bps__gte=0)
                    & models.Q(recovery_fee_base_minor__gte=0)
                    & models.Q(recovery_fee_minor__gte=0)
                    & models.Q(net_available_for_distribution_minor__gte=0)
                    & models.Q(principal_recovered_minor__gte=0)
                    & models.Q(contractual_interest_recovered_minor__gte=0)
                    & models.Q(default_interest_recovered_minor__gte=0)
                    & models.Q(penalties_recovered_minor__gte=0)
                    & models.Q(other_costs_recovered_minor__gte=0)
                    & models.Q(rounding_difference_minor__gte=0)
                ),
                name="servicing_recovery_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    net_received_minor=models.F("gross_recovered_minor")
                    - models.F("externally_deducted_costs_minor")
                ),
                name="servicing_recovery_net_received_reconciles",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    net_available_for_distribution_minor=models.F("net_received_minor")
                    - models.F("third_party_costs_from_received_minor")
                    - models.F("recovery_fee_minor")
                ),
                name="servicing_recovery_net_available_reconciles",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    net_available_for_distribution_minor=models.F("principal_recovered_minor")
                    + models.F("contractual_interest_recovered_minor")
                    + models.F("default_interest_recovered_minor")
                    + models.F("penalties_recovered_minor")
                    + models.F("other_costs_recovered_minor")
                    + models.F("rounding_difference_minor")
                ),
                name="servicing_recovery_distribution_reconciles",
            ),
        ]
        indexes = [
            models.Index(fields=["loan", "value_date"]),
            models.Index(fields=["borrower_id", "value_date"]),
            models.Index(fields=["currency", "value_date"]),
            models.Index(fields=["bank_operation"]),
            models.Index(fields=["journal_entry"]),
        ]


class InvestorRecoveryDistributionLine(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recovery_event = models.ForeignKey(
        LoanRecoveryEvent,
        on_delete=models.PROTECT,
        related_name="distribution_lines",
    )
    holding = models.ForeignKey(
        "holdings.InvestorLoanHolding",
        on_delete=models.PROTECT,
        related_name="recovery_distribution_lines",
    )
    investor_user_id = models.UUIDField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="recovery_distribution_lines",
    )
    balance_lot = models.ForeignKey(
        "ledger.InvestorBalanceLot",
        on_delete=models.PROTECT,
        related_name="recovery_distribution_lines",
    )
    amount_minor = models.BigIntegerField()
    principal_minor = models.BigIntegerField(default=0)
    contractual_interest_minor = models.BigIntegerField(default=0)
    default_interest_minor = models.BigIntegerField(default=0)
    penalties_minor = models.BigIntegerField(default=0)
    other_costs_minor = models.BigIntegerField(default=0)
    current_principal_before_minor = models.BigIntegerField()
    current_principal_after_minor = models.BigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = PlatformDateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recovery_event", "occurred_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0),
                name="servicing_recovery_line_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(principal_minor__gte=0)
                    & models.Q(contractual_interest_minor__gte=0)
                    & models.Q(default_interest_minor__gte=0)
                    & models.Q(penalties_minor__gte=0)
                    & models.Q(other_costs_minor__gte=0)
                    & models.Q(current_principal_before_minor__gte=0)
                    & models.Q(current_principal_after_minor__gte=0)
                ),
                name="servicing_recovery_line_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    amount_minor=models.F("principal_minor")
                    + models.F("contractual_interest_minor")
                    + models.F("default_interest_minor")
                    + models.F("penalties_minor")
                    + models.F("other_costs_minor")
                ),
                name="servicing_recovery_line_amount_reconciles",
            ),
        ]
        indexes = [
            models.Index(fields=["recovery_event", "investor_user_id"]),
            models.Index(fields=["holding", "occurred_at"]),
            models.Index(fields=["investor_user_id", "occurred_at"]),
            models.Index(fields=["balance_lot"]),
        ]


class LoanRiskNote(AppendOnlyModel, TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="risk_notes",
    )
    # Empty for Loan Originator loans: their final borrower is not a BANXUM borrower.
    borrower_id = models.UUIDField(null=True, blank=True)
    visibility = models.CharField(max_length=16, choices=LoanRiskNoteVisibility.choices)
    note_type = models.CharField(max_length=64, choices=LoanRiskNoteType.choices)
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    evidence_reference = models.CharField(max_length=255, blank=True)
    created_by_admin_id = models.UUIDField()
    occurred_at = models.DateTimeField()
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["loan", "visibility", "occurred_at"]),
            models.Index(fields=["borrower_id", "occurred_at"]),
            models.Index(fields=["created_by_admin_id", "occurred_at"]),
        ]


class LoanWriteOffEvent(AppendOnlyModel, TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="write_off_events",
    )
    borrower_id = models.UUIDField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="loan_write_off_events",
    )
    written_off_principal_minor = models.BigIntegerField(default=0)
    written_off_contractual_interest_minor = models.BigIntegerField(default=0)
    written_off_default_interest_minor = models.BigIntegerField(default=0)
    written_off_fees_minor = models.BigIntegerField(default=0)
    written_off_penalties_minor = models.BigIntegerField(default=0)
    total_written_off_minor = models.BigIntegerField()
    previous_loan_status = models.CharField(max_length=32)
    new_loan_status = models.CharField(max_length=32)
    reason = models.TextField()
    notes = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True)
    written_off_at = models.DateTimeField()
    created_by_admin_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-written_off_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(written_off_principal_minor__gte=0)
                    & models.Q(written_off_contractual_interest_minor__gte=0)
                    & models.Q(written_off_default_interest_minor__gte=0)
                    & models.Q(written_off_fees_minor__gte=0)
                    & models.Q(written_off_penalties_minor__gte=0)
                ),
                name="servicing_write_off_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total_written_off_minor=models.F("written_off_principal_minor")
                    + models.F("written_off_contractual_interest_minor")
                    + models.F("written_off_default_interest_minor")
                    + models.F("written_off_fees_minor")
                    + models.F("written_off_penalties_minor")
                ),
                name="servicing_write_off_total_reconciles",
            ),
            models.CheckConstraint(
                condition=models.Q(total_written_off_minor__gt=0),
                name="servicing_write_off_total_positive",
            ),
            models.UniqueConstraint(
                fields=["loan"],
                name="unique_loan_write_off_event",
            ),
        ]
        indexes = [
            models.Index(fields=["loan", "written_off_at"]),
            models.Index(fields=["borrower_id", "written_off_at"]),
            models.Index(fields=["currency", "written_off_at"]),
            models.Index(fields=["created_by_admin_id", "written_off_at"]),
        ]


class InvestorLossRecognitionLine(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    write_off_event = models.ForeignKey(
        LoanWriteOffEvent,
        on_delete=models.PROTECT,
        related_name="loss_recognition_lines",
    )
    holding = models.ForeignKey(
        "holdings.InvestorLoanHolding",
        on_delete=models.PROTECT,
        related_name="loss_recognition_lines",
    )
    investor_user_id = models.UUIDField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="loss_recognition_lines",
    )
    principal_loss_minor = models.BigIntegerField(default=0)
    contractual_interest_loss_minor = models.BigIntegerField(default=0)
    default_interest_loss_minor = models.BigIntegerField(default=0)
    fees_loss_minor = models.BigIntegerField(default=0)
    penalties_loss_minor = models.BigIntegerField(default=0)
    total_loss_minor = models.BigIntegerField()
    current_principal_before_minor = models.BigIntegerField()
    current_principal_after_minor = models.BigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = PlatformDateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["write_off_event", "occurred_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(principal_loss_minor__gte=0)
                    & models.Q(contractual_interest_loss_minor__gte=0)
                    & models.Q(default_interest_loss_minor__gte=0)
                    & models.Q(fees_loss_minor__gte=0)
                    & models.Q(penalties_loss_minor__gte=0)
                    & models.Q(current_principal_before_minor__gte=0)
                    & models.Q(current_principal_after_minor__gte=0)
                ),
                name="servicing_loss_line_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(total_loss_minor__gt=0),
                name="servicing_loss_line_total_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total_loss_minor=models.F("principal_loss_minor")
                    + models.F("contractual_interest_loss_minor")
                    + models.F("default_interest_loss_minor")
                    + models.F("fees_loss_minor")
                    + models.F("penalties_loss_minor")
                ),
                name="servicing_loss_line_total_reconciles",
            ),
        ]
        indexes = [
            models.Index(fields=["write_off_event", "investor_user_id"]),
            models.Index(fields=["holding", "occurred_at"]),
            models.Index(fields=["investor_user_id", "occurred_at"]),
        ]


class LoanRecoveryStageStatus(models.TextChoices):
    # A step that happened, with its real date.
    DONE = "done", "Done"
    # The step that really comes next; shown only when the admin knows it.
    NEXT = "next", "Next"


class LoanRecoveryResult(models.TextChoices):
    """Q16: the result recorded with "Recovery closed"."""

    FULL = "full", "Full recovery"
    PARTIAL = "partial", "Partial recovery"
    NONE = "none", "No recovery"


class LoanRecoveryStage(TimestampedModel):
    """U33-DEC-22: a real stage of the follow-up of a late or defaulted loan, recorded by an admin.

    Titles follow the real process (no fixed list and no automatic progress); the note is written
    for the loan's investors. One "next" step at most is current. A wrong entry is removed with a
    reason, never deleted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey("loans.Loan", on_delete=models.PROTECT, related_name="recovery_stages")
    status = models.CharField(max_length=8, choices=LoanRecoveryStageStatus.choices)
    title = models.CharField(max_length=120)
    # Q16: the standard stage name the admin picked (empty for an own title); German names in 18.13.
    standard_key = models.CharField(max_length=40, blank=True, default="")
    # Q16: "Recovery closed" states the result (full, partial or no recovery).
    recovery_result = models.CharField(
        max_length=8, choices=LoanRecoveryResult.choices, blank=True, default=""
    )
    occurred_on = models.DateField(null=True, blank=True)
    investor_note = models.TextField(blank=True, default="")
    created_by_admin_id = models.UUIDField()
    removed_at = PlatformDateTimeField(null=True, blank=True)
    removed_by_admin_id = models.UUIDField(null=True, blank=True)
    removed_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["occurred_on", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status="next") | models.Q(occurred_on__isnull=False),
                name="loan_recovery_stage_done_has_date",
            ),
            models.UniqueConstraint(
                fields=["loan"],
                condition=models.Q(status="next", removed_at__isnull=True),
                name="loan_recovery_stage_one_next_step",
            ),
        ]
        indexes = [models.Index(fields=["loan", "removed_at"])]


class LoanExpense(AppendOnlyModel, TimestampedModel):
    """18.6: a real outside cost of recovery (for example a lawyer's notice), recorded by an admin.

    Owed by the borrower, paid first from the next payments; penalty X runs on it from the day
    after its value date. Recordable from the "Due" status (an installment unpaid after the
    Pending window), in "Late" and after a Default declaration. Only real external costs.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey("loans.Loan", on_delete=models.PROTECT, related_name="expenses")
    currency = models.ForeignKey(
        "platform_core.Currency", on_delete=models.PROTECT, related_name="loan_expenses"
    )
    amount_minor = models.BigIntegerField()
    value_date = models.DateField()
    note = models.TextField()
    evidence_reference = models.CharField(max_length=255, blank=True, default="")
    # The invoice or notice, uploaded to the borrower's document library.
    document_id = models.UUIDField(null=True, blank=True)
    created_by_admin_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["value_date", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0), name="servicing_expense_amount_positive"
            ),
        ]
        indexes = [models.Index(fields=["loan", "value_date"])]


class LoanDefaultDeclaration(TimestampedModel):
    """18.6: the admin's Default declaration (maturity: everything due at once), and its
    cancellation by a super admin with a written reason. Both stay in the history."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.Loan", on_delete=models.PROTECT, related_name="default_declarations"
    )
    declared_on = models.DateField()
    declared_by_admin_id = models.UUIDField()
    note = models.TextField(blank=True, default="")
    days_late = models.PositiveIntegerField(default=0)
    # The whole amount that became due (engine loans): principal, interest (unpaid installments
    # and interest built up to the declaration day) and the penalties counted until then.
    whole_principal_minor = models.BigIntegerField(default=0)
    whole_interest_minor = models.BigIntegerField(default=0)
    frozen_penalty_minor = models.BigIntegerField(default=0)
    schedule_version_before = models.PositiveIntegerField(default=0)
    schedule_version_after = models.PositiveIntegerField(default=0)
    # The penalty state before the declaration, restored if a super admin cancels it.
    penalty_state_before = models.JSONField(default=dict, blank=True)
    cancelled_at = PlatformDateTimeField(null=True, blank=True)
    cancelled_by_admin_id = models.UUIDField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True, default="")
    restored_schedule_version = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-declared_on", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan"],
                condition=models.Q(cancelled_at__isnull=True),
                name="servicing_one_active_default_declaration",
            ),
        ]


class LoanPenaltyState(TimestampedModel):
    """18.6: penalty X counted per installment and expense up to ``through_date`` (the value date
    of the last payment, expense or declaration), with what was paid. One row per loan.

    ``state`` holds exact accruals as decimal strings: {"installments": {key: {"accrued", "paid"}},
    "expenses": {id: {"paid", "accrued", "penalty_paid"}}, "frozen": {"minor", "paid"},
    "default": {"accrued", "paid"}}. Each payment keeps a copy in its event metadata.
    """

    loan = models.OneToOneField(
        "loans.Loan", on_delete=models.PROTECT, related_name="penalty_state", primary_key=True
    )
    through_date = models.DateField()
    state = models.JSONField(default=dict, blank=True)


class InvestorDistributionFraction(TimestampedModel):
    """18.6 (F13 B): the part of a cent not yet paid to an investor, per loan and currency.

    Investors receive whole cents; the fractions are carried to the next payment (also after the
    investor sold the investment) and the last cents are paid by largest remainder when the loan
    is fully repaid. The undistributed cents sit on the ledger account for undistributed fractions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(
        "loans.Loan", on_delete=models.PROTECT, related_name="distribution_fractions"
    )
    investor_user_id = models.UUIDField()
    currency = models.ForeignKey(
        "platform_core.Currency", on_delete=models.PROTECT, related_name="distribution_fractions"
    )
    interest_fraction = models.DecimalField(max_digits=24, decimal_places=12, default=0)
    penalty_fraction = models.DecimalField(max_digits=24, decimal_places=12, default=0)
    final_paid_minor = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "investor_user_id"], name="servicing_one_fraction_per_investor"
            ),
        ]
