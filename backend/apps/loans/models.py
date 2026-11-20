from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import models

from backend.apps.platform_core.domain.payment_waterfall import PAYMENT_WATERFALL_VERSION
from backend.apps.platform_core.models.base import (
    AppendOnlyModel,
    PlatformDateTimeField,
    TimestampedModel,
)


class LoanStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    FUNDING_CLOSE_FAILED = "funding_close_failed", "Funding close failed"
    FUNDED = "funded", "Funded"
    ACTIVE = "active", "Active"
    LATE = "late", "Late"
    DEFAULTED = "defaulted", "Defaulted"
    REPAID = "repaid", "Repaid"
    WRITTEN_OFF = "written_off", "Written off"
    CANCELLED = "cancelled", "Cancelled"


class LoanProductType(models.TextChoices):
    DIRECT = "direct", "Direct loan"
    ORIGINATOR_CLAIM = "originator_claim", "Loan Originator claim"


class LoanPurpose(models.TextChoices):
    WORKING_CAPITAL = "working_capital", "Working capital"
    LIQUIDITY = "liquidity", "Liquidity"
    REFINANCING = "refinancing", "Refinancing"
    DEBT_CONSOLIDATION = "debt_consolidation", "Debt consolidation"
    ACQUISITION = "acquisition", "Acquisition"
    BRIDGE_FINANCING = "bridge_financing", "Bridge financing"
    PROJECT_FINANCE = "project_finance", "Project finance"
    CORPORATE_PROJECT_FINANCE = "corporate_project_finance", "Corporate project finance"
    CAPEX = "capex", "Capex / business expansion"
    DEVELOPMENT = "development", "Development"
    INVENTORY_TRADE_FINANCE = "inventory_trade_finance", "Inventory or trade finance"
    OTHER = "other", "Other"


class CollateralType(models.TextChoices):
    REAL_ESTATE = "real_estate", "Real estate"
    CORPORATE_GUARANTEE = "corporate_guarantee", "Corporate guarantee"
    PERSONAL_GUARANTEE = "personal_guarantee", "Personal guarantee"
    RECEIVABLES = "receivables", "Receivables"
    INVOICES = "invoices", "Invoices"
    EQUIPMENT = "equipment", "Equipment"
    INVENTORY = "inventory", "Inventory"
    # Q15 (2026-11-13): vehicles have their own type from the start.
    VEHICLE = "vehicle", "Vehicle"
    SECURITIES_PLEDGE = "securities_pledge", "Securities pledge"
    CASH_COLLATERAL = "cash_collateral", "Cash collateral"
    SHARE_PLEDGE = "share_pledge", "Share pledge"
    ASSET_BACKED = "asset_backed", "Asset backed"
    MIXED_COLLATERAL = "mixed_collateral", "Mixed collateral"
    UNSECURED_EXCEPTION = "unsecured_exception", "Unsecured exception"
    OTHER = "other", "Other"


class RiskRating(models.TextChoices):
    AAA = "AAA", "AAA"
    AA_PLUS = "AA+", "AA+"
    AA = "AA", "AA"
    AA_MINUS = "AA-", "AA-"
    A_PLUS = "A+", "A+"
    A = "A", "A"
    A_MINUS = "A-", "A-"
    BBB_PLUS = "BBB+", "BBB+"
    BBB = "BBB", "BBB"
    BBB_MINUS = "BBB-", "BBB-"
    BB_PLUS = "BB+", "BB+"
    BB = "BB", "BB"
    BB_MINUS = "BB-", "BB-"
    B_PLUS = "B+", "B+"
    B = "B", "B"
    B_MINUS = "B-", "B-"
    CCC = "CCC", "CCC"
    CC = "CC", "CC"
    C = "C", "C"
    D = "D", "D"
    UNRATED = "unrated", "Unrated"


class RepaymentType(models.TextChoices):
    EQUAL_INSTALLMENTS = "equal_installments", "Equal installments"
    BULLET_PERIODIC_INTEREST = "bullet_periodic_interest", "Bullet principal with periodic interest"
    AMORTIZING_PRINCIPAL_INTEREST = (
        "amortizing_principal_interest",
        "Amortizing principal and interest",
    )
    INTEREST_ONLY_THEN_BULLET = "interest_only_then_bullet", "Interest-only then bullet"
    INTEREST_ONLY_THEN_AMORTIZING = (
        "interest_only_then_amortizing",
        "Interest-only then amortizing",
    )
    # 18.6 (Q08): all principal and interest at the end; custom schedules by import.
    FULL_AT_MATURITY = "full_at_maturity", "Full payment at maturity"
    CUSTOM_SCHEDULE = "custom_schedule", "Custom schedule"


class PaymentFrequency(models.TextChoices):
    """18.6 (Q08): the four frequencies of new direct loans."""

    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    HALF_YEARLY = "half_yearly", "Half-yearly"
    ANNUAL = "annual", "Annual"


class InterestConvention(models.TextChoices):
    """18.6: Actual/365 Fixed engine for new direct loans; earlier loans keep their schedule."""

    ACT_365_FIXED = "act_365_fixed", "Actual/365 Fixed (18.6 engine)"
    LEGACY_MONTHLY = "legacy_monthly", "Earlier schedule (before 18.6)"


class LoanEventType(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    PUBLISHED = "published", "Published"
    FUNDING_CLOSED = "funding_closed", "Funding closed"
    FUNDING_CLOSE_FAILED = "funding_close_failed", "Funding close failed"
    DISBURSED = "disbursed", "Disbursed"
    FUNDING_CANCELLED = "funding_cancelled", "Funding cancelled"
    ORIGINATOR_SUBSCRIPTION_ACTIVATED = (
        "originator_subscription_activated",
        "Originator subscription activated",
    )
    SCHEDULE_GENERATED = "schedule_generated", "Schedule generated"
    SERVICING_STATUS_CHANGED = "servicing_status_changed", "Servicing status changed"
    RECOVERY_RECORDED = "recovery_recorded", "Recovery recorded"
    WRITE_OFF_RECORDED = "write_off_recorded", "Write-off recorded"
    STATUS_THRESHOLDS_CHANGED = "status_thresholds_changed", "Status thresholds changed"
    CONTRACT_TERMINATED = "contract_terminated", "Contract terminated"
    COMING_SOON_ANNOUNCED = "coming_soon_announced", "Coming soon announced"
    COMING_SOON_WITHDRAWN = "coming_soon_withdrawn", "Coming soon withdrawn"
    # 18.6: the schedule recalculated from the real payout day; the admin's Default declaration
    # (and its correction by a super admin); recovery expenses.
    SCHEDULE_CONFIRMED = "schedule_confirmed", "Schedule confirmed at payout"
    DEFAULT_DECLARED = "default_declared", "Default declared"
    DEFAULT_CANCELLED = "default_cancelled", "Default declaration cancelled"
    EXPENSE_RECORDED = "expense_recorded", "Recovery expense recorded"


class Loan(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(
        "entities.BorrowerEntity",
        on_delete=models.PROTECT,
        related_name="loans",
        null=True,
        blank=True,
    )
    product_type = models.CharField(
        max_length=32,
        choices=LoanProductType.choices,
        default=LoanProductType.DIRECT,
    )
    status = models.CharField(max_length=32, choices=LoanStatus.choices, default=LoanStatus.DRAFT)
    title = models.CharField(max_length=255)
    investor_summary = models.TextField()
    purpose = models.CharField(max_length=64, choices=LoanPurpose.choices)
    purpose_description = models.TextField(blank=True)
    is_refinancing = models.BooleanField(default=False)
    original_principal_minor = models.BigIntegerField()
    original_interest_rate_bps = models.PositiveIntegerField(null=True, blank=True)
    original_term_months = models.PositiveSmallIntegerField(null=True, blank=True)
    original_repayment_type = models.CharField(
        max_length=64,
        choices=RepaymentType.choices,
        blank=True,
        default="",
    )
    original_interest_only_months = models.PositiveSmallIntegerField(null=True, blank=True)
    original_loan_start_date = models.DateField(null=True, blank=True)
    principal_minor = models.BigIntegerField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="loans",
    )
    interest_rate_bps = models.PositiveIntegerField()
    term_months = models.PositiveSmallIntegerField()
    repayment_type = models.CharField(max_length=64, choices=RepaymentType.choices)
    interest_only_months = models.PositiveSmallIntegerField(default=0)
    loan_start_date = models.DateField()
    funding_deadline = models.DateField(null=True, blank=True)
    first_payment_date = models.DateField()
    pre_publication_paid_installments = models.JSONField(default=list, blank=True)
    collateral_type = models.CharField(
        max_length=64,
        choices=CollateralType.choices,
        default=CollateralType.REAL_ESTATE,
    )
    collateral_value_minor = models.BigIntegerField()
    collateral_description = models.TextField(blank=True)
    risk_rating = models.CharField(max_length=16, choices=RiskRating.choices)
    borrower_success_fee_bps = models.PositiveSmallIntegerField(default=200)
    lender_payment_fee_minor = models.BigIntegerField(default=0)
    default_penalty_interest_bps = models.PositiveIntegerField(default=0)
    skin_in_the_game_bps = models.PositiveSmallIntegerField(default=0)
    minimum_subscription_bps = models.PositiveSmallIntegerField(default=5_000)
    recovery_fee_bps = models.PositiveIntegerField(default=0)
    # U33-DEC-09: the contract's own Late / Default days; both empty = the platform settings
    # servicing.late_threshold_days / servicing.default_threshold_days.
    late_threshold_days = models.PositiveSmallIntegerField(null=True, blank=True)
    default_threshold_days = models.PositiveSmallIntegerField(null=True, blank=True)
    # U33-DEC-09: the contract termination date, recorded by an admin (never automatic).
    contract_terminated_on = models.DateField(null=True, blank=True)
    # 18.6 interest engine (new direct loans): convention, frequency, grace in business days, the
    # daily penalty X (% per day) and the investors' share of it (the rest is Garanta's), the real
    # payout day (the schedule is confirmed from it) and the admin's Default declaration.
    # Audit S5-7: a new loan is an engine loan; the loans that existed at the 18.6 release kept
    # legacy_monthly through migration 0029.
    interest_convention = models.CharField(
        max_length=32,
        choices=InterestConvention.choices,
        default=InterestConvention.ACT_365_FIXED,
    )
    payment_frequency = models.CharField(
        max_length=16, choices=PaymentFrequency.choices, default=PaymentFrequency.MONTHLY
    )
    grace_business_days = models.PositiveSmallIntegerField(default=0)
    penalty_daily_rate_percent = models.DecimalField(
        max_digits=7, decimal_places=4, default=Decimal("0")
    )
    penalty_investor_share_bps = models.PositiveSmallIntegerField(default=10_000)
    payout_date = models.DateField(null=True, blank=True)
    default_declared_on = models.DateField(null=True, blank=True)
    # U33-DEC-17: a draft shown as "Coming soon" with its planned opening date. Nothing can be
    # invested or reserved until the admin publishes it; publishing sends the opening alerts.
    # U33-DEC-20: how the loan is followed, for the credit file's "Checks & updates".
    monitoring_frequency = models.TextField(blank=True, default="")
    monitoring_focus = models.TextField(blank=True, default="")
    # 18.3: the credit file's "Source of repayment" (where the money to repay comes from).
    repayment_source = models.TextField(blank=True, default="")
    # U33-DEC-20 "Reporting over the loan term": what the borrower reports and when
    # ([{"when", "title", "body"}]), as a proposed or an agreed plan; empty when none is recorded.
    reporting_plan_status = models.CharField(max_length=16, blank=True, default="")
    reporting_milestones = models.JSONField(default=list, blank=True)
    coming_soon_at = models.DateTimeField(null=True, blank=True)
    planned_opening_date = models.DateField(null=True, blank=True)
    recovery_waterfall_version = models.CharField(
        max_length=64,
        default=PAYMENT_WATERFALL_VERSION,
    )
    schedule_version = models.PositiveIntegerField(default=1)
    total_scheduled_principal_minor = models.BigIntegerField(default=0)
    total_scheduled_interest_minor = models.BigIntegerField(default=0)
    committed_principal_minor = models.BigIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by_admin_id = models.UUIDField()
    updated_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(committed_principal_minor__gte=0)
                    & models.Q(committed_principal_minor__lte=models.F("principal_minor"))
                ),
                name="loan_committed_principal_within_principal",
            ),
            models.CheckConstraint(
                condition=models.Q(original_principal_minor__gte=models.F("principal_minor")),
                name="loan_original_principal_not_below_financeable",
            ),
            models.CheckConstraint(
                condition=models.Q(skin_in_the_game_bps__lt=10_000),
                name="loan_skin_in_the_game_bps_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(penalty_investor_share_bps__lte=10_000)
                    & models.Q(penalty_daily_rate_percent__gte=0)
                    & models.Q(grace_business_days__lte=30)
                ),
                name="loan_penalty_and_grace_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_subscription_bps__lte=10_000),
                name="loan_minimum_subscription_bps_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(late_threshold_days__isnull=True)
                        & models.Q(default_threshold_days__isnull=True)
                    )
                    | (
                        models.Q(late_threshold_days__gte=1)
                        & models.Q(default_threshold_days__gt=models.F("late_threshold_days"))
                        & models.Q(default_threshold_days__lte=365)
                    )
                ),
                name="loan_status_thresholds_pair_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(skin_in_the_game_bps=0) | models.Q(product_type="originator_claim")
                ),
                name="loan_skin_in_the_game_originator_only",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_refinancing=False)
                    | (
                        models.Q(original_interest_rate_bps__isnull=False)
                        & models.Q(original_term_months__isnull=False)
                        & ~models.Q(original_repayment_type="")
                        & models.Q(original_interest_only_months__isnull=False)
                        & models.Q(original_loan_start_date__isnull=False)
                    )
                ),
                name="loan_refinancing_requires_original_terms",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(product_type=LoanProductType.DIRECT)
                        & models.Q(borrower__isnull=False)
                        & models.Q(funding_deadline__isnull=False)
                    )
                    | (
                        models.Q(product_type=LoanProductType.ORIGINATOR_CLAIM)
                        & models.Q(borrower__isnull=True)
                        & models.Q(is_refinancing=False)
                    )
                ),
                name="loan_product_type_required_fields",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "funding_deadline"]),
            models.Index(fields=["borrower", "status"]),
            models.Index(fields=["currency", "status"]),
            models.Index(fields=["purpose", "status"]),
            models.Index(fields=["risk_rating", "status"]),
            models.Index(fields=["product_type", "status"]),
        ]

    @property
    def ltv_bps(self) -> int | None:
        if self.collateral_value_minor <= 0:
            return None
        value = Decimal(self.principal_minor * 10_000) / Decimal(self.collateral_value_minor)
        return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @property
    def ltv_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.collateral_value_minor <= 0:
            warnings.append("collateral_value_zero")
        elif self.collateral_value_minor > self.principal_minor:
            warnings.append("collateral_value_exceeds_principal")
        return warnings

    def __str__(self) -> str:
        return self.title


class LoanInstallment(AppendOnlyModel, TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="installments")
    schedule_version = models.PositiveIntegerField()
    installment_number = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    principal_minor = models.BigIntegerField()
    interest_minor = models.BigIntegerField()
    total_minor = models.BigIntegerField()
    admin_overridden = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["schedule_version", "installment_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "schedule_version", "installment_number"],
                name="unique_loan_schedule_installment_number",
            ),
        ]
        indexes = [
            models.Index(fields=["loan", "schedule_version"]),
            models.Index(fields=["due_date"]),
        ]


class LoanEvent(AppendOnlyModel):
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=48, choices=LoanEventType.choices)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    previous_status = models.CharField(max_length=32, blank=True)
    new_status = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = PlatformDateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["loan", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]


class LoanSecurityStatus(models.TextChoices):
    """U33-DEC-21: where the security stands. Empty when it was never recorded."""

    IN_PLACE = "in_place", "In place"
    PENDING = "pending", "Being put in place"
    RELEASED = "released", "Released"


# Guarantees are undertakings of a person or company: they have a scope and a limit, never an asset
# value, and the guarantor's wealth is never added to an asset value (U33-DEC-21).
GUARANTEE_SECURITY_TYPES = frozenset(
    {CollateralType.CORPORATE_GUARANTEE, CollateralType.PERSONAL_GUARANTEE}
)
# Kept on existing records only: "mixed" is split into its securities and "asset backed" does not
# identify the right (U33-DEC-21); "unsecured" is not a security (U33-DEC-38).
LEGACY_ONLY_SECURITY_TYPES = frozenset(
    {CollateralType.MIXED_COLLATERAL, CollateralType.ASSET_BACKED}
)
# Q15 (2026-11-13): invoices are closed for new securities; the pledged claim is recorded as
# "Receivables" with the invoice attached as a document. Existing records keep their type.
CLOSED_FOR_NEW_SECURITY_TYPES = LEGACY_ONLY_SECURITY_TYPES | {CollateralType.INVOICES}
# C06 / F16 (2026-11-16): asset types that count in the loan-to-value by default when they have a
# documented valuation. Receivables count only once the admin confirms they are valued (an invoice
# nominal is not enough); guarantees never count; other types only by the admin's choice.
LTV_ASSET_SECURITY_TYPES = frozenset(
    {
        CollateralType.REAL_ESTATE,
        CollateralType.EQUIPMENT,
        CollateralType.INVENTORY,
        CollateralType.VEHICLE,
        CollateralType.SECURITIES_PLEDGE,
        CollateralType.CASH_COLLATERAL,
    }
)


class LoanSecurity(TimestampedModel):
    """U33-DEC-21: one security of a loan, managed separately (a loan can have several).

    Only the fields that apply are filled. C06 (2026-11-13): the admin chooses the main security,
    which gives the loan's summary (collateral type and description); the loan's collateral value
    is the sum of the values of the securities that count in the loan-to-value (F16), so
    ``Loan.ltv_bps`` = loan amount / that sum. Values are in the loan currency; a valuation in
    another currency keeps its amount, the rate and the rate date.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="securities")
    position = models.PositiveSmallIntegerField(default=0)
    security_type = models.CharField(max_length=32, choices=CollateralType.choices)
    description = models.TextField(blank=True, default="")
    # 18.3: the asset in a few anonymous words for the public site ("Residential building in
    # Biel"); empty: the public site names the type ("Property").
    public_name = models.CharField(max_length=120, blank=True, default="")
    # The owner of the asset or right, or the guarantor.
    holder_name = models.CharField(max_length=255, blank=True, default="")
    # 1 is first rank.
    rank = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=LoanSecurityStatus.choices, blank=True, default=""
    )
    value_minor = models.BigIntegerField(null=True, blank=True)
    valuation_date = models.DateField(null=True, blank=True)
    valuation_source = models.CharField(max_length=255, blank=True, default="")
    appraiser = models.CharField(max_length=255, blank=True, default="")
    prior_ranking_debt_minor = models.BigIntegerField(null=True, blank=True)
    insurance = models.TextField(blank=True, default="")
    undertaking_scope = models.TextField(blank=True, default="")
    undertaking_limit_minor = models.BigIntegerField(null=True, blank=True)
    # Borrower documents about this security (ids of the borrower's documents).
    document_ids = models.JSONField(default=list, blank=True)
    # C06: the security the summary shows; one per loan.
    is_main = models.BooleanField(default=False)
    # F16: the value counts in the loan-to-value. Excluding is not releasing.
    counts_in_ltv = models.BooleanField(default=False)
    # Audit S1-3 (C06): a stable identifier of the asset (land register parcel, serial or chassis
    # number, ISIN or securities account, account IBAN, inventory location), stored normalized.
    # The same asset is never counted twice in the loan-to-value.
    asset_reference = models.CharField(max_length=160, blank=True, default="")
    # F16: a valuation made in another currency than the loan's: its amount, the rate to the loan
    # currency and the rate date. ``value_minor`` is then the converted value (no FX for investors).
    valuation_currency = models.CharField(max_length=3, blank=True, default="")
    valuation_amount_minor = models.BigIntegerField(null=True, blank=True)
    valuation_fx_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    valuation_fx_rate_date = models.DateField(null=True, blank=True)
    created_by_admin_id = models.UUIDField(null=True, blank=True)
    updated_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "asset_reference"],
                condition=models.Q(counts_in_ltv=True)
                & ~models.Q(asset_reference="")
                & ~models.Q(status="released"),
                name="loan_security_counted_asset_unique",
            ),
            models.UniqueConstraint(
                fields=["loan", "position"], name="unique_loan_security_position"
            ),
            models.UniqueConstraint(
                fields=["loan"],
                condition=models.Q(is_main=True),
                name="unique_main_loan_security",
            ),
            models.CheckConstraint(
                condition=(models.Q(value_minor__isnull=True) | models.Q(value_minor__gte=0))
                & (
                    models.Q(prior_ranking_debt_minor__isnull=True)
                    | models.Q(prior_ranking_debt_minor__gte=0)
                )
                & (
                    models.Q(undertaking_limit_minor__isnull=True)
                    | models.Q(undertaking_limit_minor__gte=0)
                ),
                name="loan_security_amounts_not_negative",
            ),
        ]



class LoanSecurityVerification(AppendOnlyModel, TimestampedModel):
    """18.10 (Q13): a named verification that a security's documents are complete.

    It is current while the security's essential fields keep the fingerprint recorded here; an
    essential change needs a new verification (the old ones stay as history).
    """

    security = models.ForeignKey(
        LoanSecurity, on_delete=models.PROTECT, related_name="verifications"
    )
    verifier_user_id = models.UUIDField()
    verifier_name = models.CharField(max_length=255)
    verified_at = models.DateTimeField()
    proofs = models.JSONField(default=dict)
    required_proofs = models.JSONField(default=list)
    essential_fingerprint = models.TextField()
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-verified_at"]
        indexes = [models.Index(fields=["security", "verified_at"])]

class LoanCreditCheck(TimestampedModel):
    """U33-DEC-20: a check made on the loan or the borrower, with its source, date and result."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="credit_checks")
    position = models.PositiveSmallIntegerField(default=0)
    name = models.CharField(max_length=255)
    result = models.TextField()
    source = models.CharField(max_length=255, blank=True, default="")
    checked_on = models.DateField(null=True, blank=True)
    # The design's chip: "received" (the document is in the file) or "reviewed" (Banxum checked it).
    status = models.CharField(max_length=16, blank=True, default="")
    updated_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
