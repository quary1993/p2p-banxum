from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class LoanStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    FUNDED = "funded", "Funded"
    CANCELLED = "cancelled", "Cancelled"


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


class LoanEventType(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    PUBLISHED = "published", "Published"
    FUNDING_CLOSED = "funding_closed", "Funding closed"
    SCHEDULE_GENERATED = "schedule_generated", "Schedule generated"


class Loan(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(
        "entities.BorrowerEntity",
        on_delete=models.PROTECT,
        related_name="loans",
    )
    status = models.CharField(max_length=32, choices=LoanStatus.choices, default=LoanStatus.DRAFT)
    title = models.CharField(max_length=255)
    investor_summary = models.TextField()
    purpose = models.CharField(max_length=64, choices=LoanPurpose.choices)
    purpose_description = models.TextField(blank=True)
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
    funding_deadline = models.DateField()
    first_payment_date = models.DateField()
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
    recovery_fee_bps = models.PositiveIntegerField(default=0)
    recovery_waterfall_version = models.CharField(max_length=64, default="v1")
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
        ]
        indexes = [
            models.Index(fields=["status", "funding_deadline"]),
            models.Index(fields=["borrower", "status"]),
            models.Index(fields=["currency", "status"]),
            models.Index(fields=["purpose", "status"]),
            models.Index(fields=["risk_rating", "status"]),
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
    event_type = models.CharField(max_length=32, choices=LoanEventType.choices)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    previous_status = models.CharField(max_length=32, blank=True)
    new_status = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["loan", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]
