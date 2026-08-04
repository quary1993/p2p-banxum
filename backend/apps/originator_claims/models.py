from __future__ import annotations

import uuid

from django.db import models
from django.db.models import F, Q

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class LoanOriginatorStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    BLOCKED = "blocked", "Blocked"
    INACTIVE = "inactive", "Inactive"


class OriginatorOpportunityStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class OriginatorImportPaymentType(models.TextChoices):
    REGULAR = "regular", "Regular payment"
    REPAYMENT_IN_ADVANCE = "repayment_in_advance", "Repayment in advance"


class OriginatorClaimEventType(models.TextChoices):
    ORIGINATOR_CREATED = "originator_created", "Originator created"
    ORIGINATOR_UPDATED = "originator_updated", "Originator updated"
    IMPORT_VALIDATED = "import_validated", "Import validated"
    LOAN_CREATED = "loan_created", "Loan created"
    OPPORTUNITY_PUBLISHED = "opportunity_published", "Opportunity published"
    OPPORTUNITY_CLOSED = "opportunity_closed", "Opportunity closed"
    QUOTE_CREATED = "quote_created", "Quote created"
    CLAIM_PURCHASED = "claim_purchased", "Claim purchased"
    REPAYMENT_RECORDED = "repayment_recorded", "Repayment recorded"
    SERVICING_STATUS_CHANGED = "servicing_status_changed", "Servicing status changed"
    SETTLEMENT_RECORDED = "settlement_recorded", "Settlement recorded"


class LoanOriginator(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_name = models.CharField(max_length=255)
    public_name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=128)
    jurisdiction = models.CharField(max_length=64)
    registered_address = models.TextField()
    contact_info = models.TextField(blank=True)
    settlement_account_name = models.CharField(max_length=255)
    settlement_iban = models.CharField(max_length=128)
    settlement_bic = models.CharField(max_length=64, blank=True)
    kyb_evidence_reference = models.CharField(max_length=255)
    kyb_aml_observations = models.TextField(blank=True)
    risk_observations = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=LoanOriginatorStatus.choices,
        default=LoanOriginatorStatus.INACTIVE,
    )
    default_premium_fee_bps = models.PositiveSmallIntegerField(default=5000)
    created_by_admin_id = models.UUIDField()
    updated_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["legal_name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(default_premium_fee_bps__lte=10_000),
                name="originator_default_fee_bps_valid",
            ),
            models.UniqueConstraint(
                fields=["jurisdiction", "registration_number"],
                name="originator_unique_registration",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "legal_name"]),
            models.Index(fields=["public_name"]),
        ]

    def __str__(self) -> str:
        return self.legal_name


class OriginatorLoanProfile(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.OneToOneField(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="originator_profile",
    )
    originator = models.ForeignKey(
        LoanOriginator,
        on_delete=models.PROTECT,
        related_name="loan_profiles",
    )
    opportunity_status = models.CharField(
        max_length=32,
        choices=OriginatorOpportunityStatus.choices,
        default=OriginatorOpportunityStatus.DRAFT,
    )
    target_yield_bps = models.PositiveIntegerField()
    minimum_investment_minor = models.BigIntegerField()
    premium_fee_bps = models.PositiveSmallIntegerField(default=5000)
    current_outstanding_principal_minor = models.BigIntegerField()
    unsold_principal_minor = models.BigIntegerField()
    maturity_date = models.DateField()
    schedule_revision = models.PositiveIntegerField(default=1)
    current_import = models.ForeignKey(
        "OriginatorLoanImport",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="current_for_profiles",
    )
    borrower_legal_name = models.CharField(max_length=255)
    borrower_display_name = models.CharField(max_length=255)
    borrower_year_founded = models.PositiveSmallIntegerField(null=True, blank=True)
    borrower_entity_type = models.CharField(max_length=64, blank=True)
    borrower_country = models.CharField(max_length=64, blank=True)
    borrower_registration_number = models.CharField(max_length=128, blank=True)
    business_classification = models.TextField(blank=True)
    business_classification_public = models.BooleanField(default=False)
    registered_address = models.TextField(blank=True)
    registered_address_public = models.BooleanField(default=False)
    operating_address = models.TextField(blank=True)
    contact_info = models.TextField(blank=True)
    contact_info_public = models.BooleanField(default=False)
    industry_activity = models.TextField(blank=True)
    ownership_structure = models.TextField(blank=True)
    beneficial_owners = models.JSONField(default=list, blank=True)
    directors_officers = models.JSONField(default=list, blank=True)
    authorized_signatories = models.JSONField(default=list, blank=True)
    bank_account_details = models.JSONField(default=dict, blank=True)
    kyb_aml_observations = models.TextField(blank=True)
    financial_risk = models.TextField(blank=True)
    financials_currency = models.CharField(max_length=3, blank=True)
    assets_minor = models.BigIntegerField(null=True, blank=True)
    liabilities_minor = models.BigIntegerField(null=True, blank=True)
    revenue_last_year_minor = models.BigIntegerField(null=True, blank=True)
    profit_last_year_minor = models.BigIntegerField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=128, blank=True)
    is_on_hold = models.BooleanField(default=False)
    hold_reason = models.CharField(max_length=255, blank=True)
    held_at = models.DateTimeField(null=True, blank=True)
    held_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(target_yield_bps__gt=0),
                name="originator_target_yield_positive",
            ),
            models.CheckConstraint(
                condition=Q(minimum_investment_minor__gt=0),
                name="originator_minimum_investment_positive",
            ),
            models.CheckConstraint(
                condition=Q(premium_fee_bps__lte=10_000),
                name="originator_profile_fee_bps_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(current_outstanding_principal_minor__gte=0)
                    & Q(unsold_principal_minor__gte=0)
                    & Q(unsold_principal_minor__lte=F("current_outstanding_principal_minor"))
                ),
                name="originator_unsold_within_outstanding",
            ),
        ]
        indexes = [
            models.Index(fields=["opportunity_status", "maturity_date"]),
            models.Index(fields=["originator", "opportunity_status"]),
        ]


class OriginatorLoanImport(AppendOnlyModel, TimestampedModel):
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="originator_imports",
    )
    revision = models.PositiveIntegerField()
    as_of_date = models.DateField()
    original_principal_minor = models.BigIntegerField()
    current_outstanding_principal_minor = models.BigIntegerField()
    currency_code = models.CharField(max_length=3)
    source_filename = models.CharField(max_length=255)
    source_csv = models.TextField()
    source_sha256 = models.CharField(max_length=64)
    schedule_row_count = models.PositiveIntegerField()
    payment_row_count = models.PositiveIntegerField()
    imported_by_admin_id = models.UUIDField()
    imported_at = models.DateTimeField()
    validation_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["loan", "revision", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "revision"],
                name="originator_unique_import_revision",
            ),
            models.CheckConstraint(
                condition=(
                    Q(original_principal_minor__gt=0)
                    & Q(current_outstanding_principal_minor__gte=0)
                    & Q(current_outstanding_principal_minor__lte=F("original_principal_minor"))
                ),
                name="originator_import_principal_valid",
            ),
        ]


class OriginatorLoanScheduleRow(AppendOnlyModel, TimestampedModel):
    loan_import = models.ForeignKey(
        OriginatorLoanImport,
        on_delete=models.PROTECT,
        related_name="schedule_rows",
    )
    installment_number = models.PositiveIntegerField()
    accrual_start_date = models.DateField()
    due_date = models.DateField()
    opening_principal_minor = models.BigIntegerField()
    principal_minor = models.BigIntegerField()
    interest_minor = models.BigIntegerField()
    penalty_minor = models.BigIntegerField(default=0)
    fee_minor = models.BigIntegerField(default=0)
    total_minor = models.BigIntegerField()
    closing_principal_minor = models.BigIntegerField()

    class Meta:
        ordering = ["loan_import", "installment_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan_import", "installment_number"],
                name="originator_unique_schedule_row",
            ),
            models.CheckConstraint(
                condition=(
                    Q(opening_principal_minor__gte=0)
                    & Q(principal_minor__gte=0)
                    & Q(interest_minor__gte=0)
                    & Q(penalty_minor__gte=0)
                    & Q(fee_minor__gte=0)
                    & Q(total_minor__gte=0)
                    & Q(closing_principal_minor__gte=0)
                ),
                name="originator_schedule_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(
                    total_minor=F("principal_minor")
                    + F("interest_minor")
                    + F("penalty_minor")
                    + F("fee_minor")
                ),
                name="originator_schedule_total_conserved",
            ),
        ]


class OriginatorLoanPaymentRow(AppendOnlyModel, TimestampedModel):
    loan_import = models.ForeignKey(
        OriginatorLoanImport,
        on_delete=models.PROTECT,
        related_name="payment_rows",
    )
    reference = models.CharField(max_length=128)
    value_date = models.DateField()
    payment_type = models.CharField(max_length=32, choices=OriginatorImportPaymentType.choices)
    principal_minor = models.BigIntegerField()
    interest_minor = models.BigIntegerField()
    penalty_minor = models.BigIntegerField(default=0)
    fee_minor = models.BigIntegerField(default=0)
    total_minor = models.BigIntegerField()
    resulting_principal_minor = models.BigIntegerField()

    class Meta:
        ordering = ["loan_import", "value_date", "reference", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan_import", "reference"],
                name="originator_unique_payment_reference",
            ),
            models.CheckConstraint(
                condition=(
                    Q(principal_minor__gte=0)
                    & Q(interest_minor__gte=0)
                    & Q(penalty_minor__gte=0)
                    & Q(fee_minor__gte=0)
                    & Q(total_minor__gt=0)
                    & Q(resulting_principal_minor__gte=0)
                ),
                name="originator_payment_amounts_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    total_minor=F("principal_minor")
                    + F("interest_minor")
                    + F("penalty_minor")
                    + F("fee_minor")
                ),
                name="originator_payment_total_conserved",
            ),
        ]


class OriginatorClaimQuote(AppendOnlyModel, TimestampedModel):
    loan_profile = models.ForeignKey(
        OriginatorLoanProfile,
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    investor_user_id = models.UUIDField()
    currency = models.ForeignKey("platform_core.Currency", on_delete=models.PROTECT)
    requested_cash_minor = models.BigIntegerField()
    executable_cash_minor = models.BigIntegerField()
    assigned_principal_minor = models.BigIntegerField()
    outstanding_principal_at_pricing_minor = models.BigIntegerField()
    share_ppm = models.PositiveIntegerField()
    target_yield_bps = models.PositiveIntegerField()
    premium_discount_minor = models.BigIntegerField()
    platform_fee_minor = models.BigIntegerField()
    originator_payable_minor = models.BigIntegerField()
    rounding_remainder_minor = models.BigIntegerField(default=0)
    schedule_revision = models.PositiveIntegerField()
    entitlement_start_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    cash_flows = models.JSONField(default=list)
    calculation_fingerprint = models.CharField(max_length=64)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(requested_cash_minor__gt=0)
                    & Q(executable_cash_minor__gt=0)
                    & Q(assigned_principal_minor__gt=0)
                    & Q(outstanding_principal_at_pricing_minor__gt=0)
                    & Q(assigned_principal_minor__lte=F("outstanding_principal_at_pricing_minor"))
                    & Q(share_ppm__gt=0)
                    & Q(share_ppm__lte=1_000_000)
                    & Q(platform_fee_minor__gte=0)
                    & Q(originator_payable_minor__gte=0)
                    & Q(rounding_remainder_minor__gte=0)
                ),
                name="originator_quote_amounts_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    executable_cash_minor=(F("platform_fee_minor") + F("originator_payable_minor"))
                ),
                name="originator_quote_cash_conserved",
            ),
        ]
        indexes = [
            models.Index(fields=["loan_profile", "expires_at"]),
            models.Index(fields=["investor_user_id", "created_at"]),
        ]


class OriginatorClaimPurchase(AppendOnlyModel, TimestampedModel):
    loan_profile = models.ForeignKey(
        OriginatorLoanProfile,
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    quote = models.OneToOneField(
        OriginatorClaimQuote,
        on_delete=models.PROTECT,
        related_name="purchase",
    )
    investor_user_id = models.UUIDField()
    currency = models.ForeignKey("platform_core.Currency", on_delete=models.PROTECT)
    cash_consideration_minor = models.BigIntegerField()
    assigned_principal_minor = models.BigIntegerField()
    outstanding_principal_at_pricing_minor = models.BigIntegerField()
    share_ppm = models.PositiveIntegerField()
    target_yield_bps = models.PositiveIntegerField()
    premium_discount_minor = models.BigIntegerField()
    platform_fee_minor = models.BigIntegerField()
    originator_payable_minor = models.BigIntegerField()
    schedule_revision = models.PositiveIntegerField()
    entitlement_start_at = models.DateTimeField()
    document_acceptance = models.ForeignKey(
        "documents.DocumentAcceptanceEvidence",
        on_delete=models.PROTECT,
    )
    journal_entry = models.ForeignKey("ledger.LedgerJournalEntry", on_delete=models.PROTECT)
    holding = models.OneToOneField(
        "holdings.InvestorLoanHolding",
        on_delete=models.PROTECT,
        related_name="originator_purchase",
    )
    lot_allocations = models.JSONField(default=list)
    purchased_at = models.DateTimeField()
    idempotency_key = models.CharField(max_length=160, unique=True)
    request_fingerprint = models.CharField(max_length=64)

    class Meta:
        ordering = ["-purchased_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(cash_consideration_minor__gt=0)
                    & Q(assigned_principal_minor__gt=0)
                    & Q(outstanding_principal_at_pricing_minor__gt=0)
                    & Q(assigned_principal_minor__lte=F("outstanding_principal_at_pricing_minor"))
                    & Q(platform_fee_minor__gte=0)
                    & Q(originator_payable_minor__gte=0)
                ),
                name="originator_purchase_amounts_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    cash_consideration_minor=(
                        F("platform_fee_minor") + F("originator_payable_minor")
                    )
                ),
                name="originator_purchase_cash_conserved",
            ),
        ]


class OriginatorClaimEntitlement(AppendOnlyModel, TimestampedModel):
    purchase = models.ForeignKey(
        OriginatorClaimPurchase,
        on_delete=models.PROTECT,
        related_name="entitlements",
    )
    schedule_row = models.ForeignKey(OriginatorLoanScheduleRow, on_delete=models.PROTECT)
    accrual_start_date = models.DateField()
    due_date = models.DateField()
    expected_principal_minor = models.BigIntegerField()
    expected_interest_minor = models.BigIntegerField()
    expected_penalty_minor = models.BigIntegerField(default=0)
    expected_total_minor = models.BigIntegerField()

    class Meta:
        ordering = ["purchase", "due_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["purchase", "schedule_row"],
                name="originator_unique_purchase_entitlement_row",
            ),
            models.CheckConstraint(
                condition=Q(
                    expected_total_minor=F("expected_principal_minor")
                    + F("expected_interest_minor")
                    + F("expected_penalty_minor")
                ),
                name="originator_entitlement_total_conserved",
            ),
        ]


class OriginatorSettlement(AppendOnlyModel, TimestampedModel):
    originator = models.ForeignKey(
        LoanOriginator,
        on_delete=models.PROTECT,
        related_name="settlements",
    )
    currency = models.ForeignKey("platform_core.Currency", on_delete=models.PROTECT)
    amount_minor = models.BigIntegerField()
    purchase_amount_minor = models.BigIntegerField(default=0)
    servicing_amount_minor = models.BigIntegerField(default=0)
    purchase_count = models.PositiveIntegerField(default=0)
    repayment_count = models.PositiveIntegerField(default=0)
    bank_operation = models.OneToOneField("ledger.BankOperation", on_delete=models.PROTECT)
    journal_entry = models.OneToOneField("ledger.LedgerJournalEntry", on_delete=models.PROTECT)
    settled_by_admin_id = models.UUIDField()
    settled_at = models.DateTimeField()
    idempotency_key = models.CharField(max_length=160, unique=True)
    request_fingerprint = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-settled_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(amount_minor__gt=0)
                    & Q(purchase_amount_minor__gte=0)
                    & Q(servicing_amount_minor__gte=0)
                    & (Q(purchase_count__gt=0) | Q(repayment_count__gt=0))
                ),
                name="originator_settlement_positive",
            ),
            models.CheckConstraint(
                condition=Q(amount_minor=F("purchase_amount_minor") + F("servicing_amount_minor")),
                name="originator_settlement_amount_conserved",
            ),
        ]


class OriginatorSettlementPurchase(AppendOnlyModel, TimestampedModel):
    settlement = models.ForeignKey(
        OriginatorSettlement,
        on_delete=models.PROTECT,
        related_name="purchase_links",
    )
    purchase = models.OneToOneField(
        OriginatorClaimPurchase,
        on_delete=models.PROTECT,
        related_name="settlement_link",
    )
    amount_minor = models.BigIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0),
                name="originator_settlement_link_positive",
            ),
        ]


class OriginatorBorrowerRepayment(AppendOnlyModel, TimestampedModel):
    loan_profile = models.ForeignKey(
        OriginatorLoanProfile,
        on_delete=models.PROTECT,
        related_name="repayments",
    )
    loan_import = models.ForeignKey(
        OriginatorLoanImport,
        on_delete=models.PROTECT,
        related_name="recorded_repayments",
    )
    payment_reference = models.CharField(max_length=128)
    payment_type = models.CharField(
        max_length=32,
        choices=OriginatorImportPaymentType.choices,
    )
    currency = models.ForeignKey("platform_core.Currency", on_delete=models.PROTECT)
    principal_minor = models.BigIntegerField()
    interest_minor = models.BigIntegerField()
    penalty_minor = models.BigIntegerField(default=0)
    fee_minor = models.BigIntegerField(default=0)
    amount_minor = models.BigIntegerField()
    investor_distributed_minor = models.BigIntegerField()
    originator_payable_minor = models.BigIntegerField()
    principal_before_minor = models.BigIntegerField()
    principal_after_minor = models.BigIntegerField()
    originator_principal_before_minor = models.BigIntegerField()
    originator_principal_after_minor = models.BigIntegerField()
    booking_date = models.DateField()
    value_date = models.DateField()
    bank_operation = models.OneToOneField(
        "ledger.BankOperation",
        on_delete=models.PROTECT,
        related_name="originator_borrower_repayment",
    )
    journal_entry = models.OneToOneField(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        related_name="originator_borrower_repayment",
    )
    created_by_admin_id = models.UUIDField()
    evidence_reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)
    request_fingerprint = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-value_date", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan_profile", "payment_reference"],
                name="originator_unique_recorded_payment_reference",
            ),
            models.CheckConstraint(
                condition=(
                    Q(principal_minor__gte=0)
                    & Q(interest_minor__gte=0)
                    & Q(penalty_minor__gte=0)
                    & Q(fee_minor__gte=0)
                    & Q(amount_minor__gt=0)
                    & Q(investor_distributed_minor__gte=0)
                    & Q(originator_payable_minor__gte=0)
                    & Q(principal_before_minor__gt=0)
                    & Q(principal_after_minor__gte=0)
                    & Q(originator_principal_before_minor__gte=0)
                    & Q(originator_principal_after_minor__gte=0)
                ),
                name="originator_repayment_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(
                    amount_minor=F("principal_minor")
                    + F("interest_minor")
                    + F("penalty_minor")
                    + F("fee_minor")
                ),
                name="originator_repayment_components_conserved",
            ),
            models.CheckConstraint(
                condition=Q(
                    amount_minor=F("investor_distributed_minor") + F("originator_payable_minor")
                ),
                name="originator_repayment_distribution_conserved",
            ),
            models.CheckConstraint(
                condition=Q(
                    principal_after_minor=F("principal_before_minor") - F("principal_minor")
                ),
                name="originator_repayment_principal_conserved",
            ),
        ]


class InvestorOriginatorRepaymentDistributionLine(AppendOnlyModel, TimestampedModel):
    repayment = models.ForeignKey(
        OriginatorBorrowerRepayment,
        on_delete=models.PROTECT,
        related_name="investor_distribution_lines",
    )
    holding = models.ForeignKey(
        "holdings.InvestorLoanHolding",
        on_delete=models.PROTECT,
        related_name="originator_repayment_distribution_lines",
    )
    investor_user_id = models.UUIDField()
    currency = models.ForeignKey("platform_core.Currency", on_delete=models.PROTECT)
    balance_lot = models.ForeignKey(
        "ledger.InvestorBalanceLot",
        on_delete=models.PROTECT,
        related_name="originator_repayment_distribution_lines",
    )
    amount_minor = models.BigIntegerField()
    principal_minor = models.BigIntegerField(default=0)
    interest_minor = models.BigIntegerField(default=0)
    penalty_minor = models.BigIntegerField(default=0)
    current_principal_before_minor = models.BigIntegerField()
    current_principal_after_minor = models.BigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["repayment", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["repayment", "holding"],
                name="originator_unique_repayment_holding_line",
            ),
            models.CheckConstraint(
                condition=(
                    Q(amount_minor__gt=0)
                    & Q(principal_minor__gte=0)
                    & Q(interest_minor__gte=0)
                    & Q(penalty_minor__gte=0)
                    & Q(current_principal_before_minor__gte=0)
                    & Q(current_principal_after_minor__gte=0)
                ),
                name="originator_distribution_amounts_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(
                    amount_minor=F("principal_minor") + F("interest_minor") + F("penalty_minor")
                ),
                name="originator_distribution_amount_conserved",
            ),
            models.CheckConstraint(
                condition=Q(
                    current_principal_after_minor=(
                        F("current_principal_before_minor") - F("principal_minor")
                    )
                ),
                name="originator_distribution_principal_conserved",
            ),
        ]


class OriginatorSettlementRepayment(AppendOnlyModel, TimestampedModel):
    settlement = models.ForeignKey(
        OriginatorSettlement,
        on_delete=models.PROTECT,
        related_name="repayment_links",
    )
    repayment = models.OneToOneField(
        OriginatorBorrowerRepayment,
        on_delete=models.PROTECT,
        related_name="settlement_link",
    )
    amount_minor = models.BigIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_minor__gt=0),
                name="originator_repayment_settlement_link_positive",
            ),
        ]


class OriginatorClaimEvent(AppendOnlyModel):
    event_type = models.CharField(max_length=64, choices=OriginatorClaimEventType.choices)
    originator = models.ForeignKey(
        LoanOriginator,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
    )
    loan_id = models.UUIDField(null=True, blank=True)
    purchase_id = models.UUIDField(null=True, blank=True)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["loan_id", "occurred_at"]),
            models.Index(fields=["purchase_id", "occurred_at"]),
        ]
