from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import (
    AppendOnlyModel,
    PlatformDateTimeField,
    TimestampedModel,
)
from backend.apps.platform_core.models.files import StoredFile


class BorrowerEntityType(models.TextChoices):
    SWISS_COMPANY = "swiss_company", "Swiss company"
    NON_SWISS_COMPANY = "non_swiss_company", "Non-Swiss company"
    REAL_ESTATE_PROJECT_COMPANY = "real_estate_project_company", "Real estate project company"
    SPECIAL_PURPOSE_VEHICLE = "special_purpose_vehicle", "Special purpose vehicle"
    OTHER = "other", "Other"


class BorrowerKybStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    DECLINED = "declined", "Declined"
    MANUAL_REVIEW = "manual_review", "Manual review"
    EXPIRED = "expired", "Expired"
    REVERIFICATION_REQUIRED = "reverification_required", "Re-verification required"


class BorrowerDocumentType(models.TextChoices):
    PRESENTATION = "presentation", "Borrower presentation"
    FINANCIALS = "financials", "Financial PDF"
    KYB_EVIDENCE = "kyb_evidence", "KYB/AML evidence"
    GENERIC = "generic", "Generic borrower document"
    OTHER = "other", "Other"


class BorrowerEntityEventType(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    KYB_STATUS_CHANGED = "kyb_status_changed", "KYB status changed"
    DOCUMENT_ADDED = "document_added", "Document added"
    # 18.9: Swiss creditor mode and external debts (Q03, F06-F09).
    CREDITOR_MODE_CHANGED = "creditor_mode_changed", "Creditor mode changed"
    EXTERNAL_DEBT_RECORDED = "external_debt_recorded", "External debt recorded"
    EXTERNAL_DEBT_ENDED = "external_debt_ended", "External debt ended"


class BorrowerEntity(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_name = models.CharField(max_length=255)
    year_founded = models.PositiveSmallIntegerField()
    entity_type = models.CharField(
        max_length=64,
        choices=BorrowerEntityType.choices,
        default=BorrowerEntityType.SWISS_COMPANY,
    )
    kyb_status = models.CharField(
        max_length=32,
        choices=BorrowerKybStatus.choices,
        default=BorrowerKybStatus.PENDING,
    )
    compliance_hold = models.BooleanField(default=False)
    country = models.CharField(max_length=64, blank=True)
    # U33-DEC-23: shown to investors when present; an unknown value stays empty (never 0).
    city = models.CharField(max_length=128, blank=True)
    employees = models.PositiveIntegerField(null=True, blank=True)
    employees_year = models.PositiveSmallIntegerField(null=True, blank=True)
    registration_number = models.CharField(max_length=128, blank=True)
    # 18.9: the Swiss UID (CHE-123.456.789), mandatory for a Swiss borrower before publication.
    uid = models.CharField(max_length=16, blank=True, default="")
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
    investor_story = models.JSONField(default=dict, blank=True)
    created_by_admin_id = models.UUIDField()
    updated_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["legal_name", "id"]
        indexes = [
            models.Index(fields=["legal_name"]),
            models.Index(fields=["kyb_status", "compliance_hold"]),
            models.Index(fields=["country"]),
            models.Index(fields=["entity_type"]),
        ]

    @property
    def can_transact(self) -> bool:
        # Company KYB is handled offline. Explicit adverse decisions still block.
        return not self.compliance_hold and self.kyb_status not in {
            BorrowerKybStatus.DECLINED,
            BorrowerKybStatus.MANUAL_REVIEW,
        }

    def __str__(self) -> str:
        return self.legal_name


class BorrowerDocument(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(
        BorrowerEntity,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    document_type = models.CharField(max_length=64, choices=BorrowerDocumentType.choices)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    stored_file = models.ForeignKey(
        StoredFile,
        on_delete=models.PROTECT,
        related_name="borrower_documents",
    )
    investor_visible = models.BooleanField(default=False)
    # U33-DEC-20: library metadata (category, date or period, issuer, version, status).
    category = models.CharField(max_length=64, blank=True, default="")
    document_date = models.DateField(null=True, blank=True)
    period_label = models.CharField(max_length=64, blank=True, default="")
    issuer = models.CharField(max_length=255, blank=True, default="")
    version = models.CharField(max_length=32, blank=True, default="")
    document_status = models.CharField(max_length=64, blank=True, default="")
    created_by_admin_id = models.UUIDField()
    created_by_account_type = models.CharField(max_length=64)

    class Meta:
        ordering = ["document_type", "display_name", "id"]
        indexes = [
            models.Index(fields=["borrower", "document_type"]),
            models.Index(fields=["borrower", "investor_visible"]),
        ]


class BorrowerEntityEvent(AppendOnlyModel):
    borrower = models.ForeignKey(
        BorrowerEntity,
        on_delete=models.PROTECT,
        related_name="events",
    )
    event_type = models.CharField(max_length=32, choices=BorrowerEntityEventType.choices)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    previous_kyb_status = models.CharField(max_length=32, blank=True)
    new_kyb_status = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    evidence_summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = PlatformDateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["borrower", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]


# U33-DEC-20: the structured financial history of a borrower, one row per financial year. The
# totals are the figures shown; the details are optional and must add up to the totals. Costs and
# expenses are stored as positive amounts. All amounts are in minor units of the year's currency.
FINANCIAL_YEAR_AMOUNT_FIELDS = (
    "revenue_minor",
    "materials_costs_minor",
    "staff_costs_minor",
    "other_operating_costs_minor",
    "depreciation_minor",
    "operating_profit_minor",
    "interest_expense_minor",
    "profit_before_tax_minor",
    "income_tax_minor",
    "net_profit_minor",
    "cash_minor",
    "trade_receivables_minor",
    "inventories_minor",
    "other_current_assets_minor",
    "current_assets_minor",
    "property_plant_equipment_minor",
    "other_non_current_assets_minor",
    "total_assets_minor",
    "current_financial_debt_minor",
    "non_current_financial_debt_minor",
    "financial_debt_minor",
    "trade_payables_minor",
    "other_operating_liabilities_minor",
    "equity_minor",
)


class BorrowerFinancialYear(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(
        BorrowerEntity, on_delete=models.CASCADE, related_name="financial_years"
    )
    year = models.PositiveSmallIntegerField()
    period_end = models.DateField()
    currency = models.CharField(max_length=3)
    revenue_minor = models.BigIntegerField(null=True, blank=True)
    materials_costs_minor = models.BigIntegerField(null=True, blank=True)
    staff_costs_minor = models.BigIntegerField(null=True, blank=True)
    other_operating_costs_minor = models.BigIntegerField(null=True, blank=True)
    depreciation_minor = models.BigIntegerField(null=True, blank=True)
    operating_profit_minor = models.BigIntegerField(null=True, blank=True)
    interest_expense_minor = models.BigIntegerField(null=True, blank=True)
    profit_before_tax_minor = models.BigIntegerField(null=True, blank=True)
    income_tax_minor = models.BigIntegerField(null=True, blank=True)
    net_profit_minor = models.BigIntegerField(null=True, blank=True)
    cash_minor = models.BigIntegerField(null=True, blank=True)
    trade_receivables_minor = models.BigIntegerField(null=True, blank=True)
    inventories_minor = models.BigIntegerField(null=True, blank=True)
    other_current_assets_minor = models.BigIntegerField(null=True, blank=True)
    current_assets_minor = models.BigIntegerField(null=True, blank=True)
    property_plant_equipment_minor = models.BigIntegerField(null=True, blank=True)
    other_non_current_assets_minor = models.BigIntegerField(null=True, blank=True)
    total_assets_minor = models.BigIntegerField(null=True, blank=True)
    current_financial_debt_minor = models.BigIntegerField(null=True, blank=True)
    non_current_financial_debt_minor = models.BigIntegerField(null=True, blank=True)
    financial_debt_minor = models.BigIntegerField(null=True, blank=True)
    trade_payables_minor = models.BigIntegerField(null=True, blank=True)
    other_operating_liabilities_minor = models.BigIntegerField(null=True, blank=True)
    equity_minor = models.BigIntegerField(null=True, blank=True)
    source_document = models.ForeignKey(
        BorrowerDocument,
        on_delete=models.SET_NULL,
        related_name="financial_years",
        null=True,
        blank=True,
    )
    updated_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["year", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["borrower", "year"], name="unique_borrower_financial_year"
            )
        ]


class BorrowerDebtFacility(TimestampedModel):
    """U33-DEC-20: the borrower's existing debt, explained from the documents, at a date."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(
        BorrowerEntity, on_delete=models.CASCADE, related_name="debt_facilities"
    )
    position = models.PositiveSmallIntegerField(default=0)
    facility_type = models.CharField(max_length=255)
    currency = models.CharField(max_length=3)
    balance_minor = models.BigIntegerField()
    current_portion_minor = models.BigIntegerField(null=True, blank=True)
    security_description = models.TextField(blank=True, default="")
    as_at = models.DateField()
    source_document = models.ForeignKey(
        BorrowerDocument,
        on_delete=models.SET_NULL,
        related_name="debt_facilities",
        null=True,
        blank=True,
    )
    updated_by_admin_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance_minor__gte=0)
                & (
                    models.Q(current_portion_minor__isnull=True)
                    | models.Q(current_portion_minor__gte=0)
                ),
                name="borrower_debt_facility_amounts_not_negative",
            )
        ]


class SwissCreditorMode(models.TextChoices):
    SANDBOX = "sandbox", "Sandbox (total below CHF 500,000, no creditor limit)"
    TEN_TWENTY = "ten_twenty", "10/20 (10 creditors per financing, 20 per borrower)"


class SwissCreditorRegime(TimestampedModel):
    """18.9 (E-02): the creditor mode of one Swiss borrower, by UID (direct loans and Loan
    Originator claims of the same company share it). Pre-selected sandbox; confirmed by an admin
    before the first publication."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uid = models.CharField(max_length=16, unique=True)
    mode = models.CharField(
        max_length=16, choices=SwissCreditorMode.choices, default=SwissCreditorMode.SANDBOX
    )
    confirmed_by_admin_id = models.UUIDField(null=True, blank=True)
    confirmed_at = PlatformDateTimeField(null=True, blank=True)
    confirmation_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["uid"]


class BorrowerExternalDebt(TimestampedModel):
    """18.9 (F09): a debt of a Swiss borrower outside Banxum, from a signed borrower declaration.

    It counts in the borrower total ``T`` and, for a non-bank creditor, in the creditor counts.
    Records are ended (``ended_on``), never deleted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uid = models.CharField(max_length=16, db_index=True)
    creditor_name = models.CharField(max_length=255)
    creditor_identification = models.CharField(max_length=128)
    creditor_is_bank = models.BooleanField(default=False)
    financing_id = models.CharField(max_length=128)
    identical_terms_group = models.CharField(max_length=128, blank=True, default="")
    principal_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    start_date = models.DateField()
    ended_on = models.DateField(null=True, blank=True)
    declaration_document_id = models.UUIDField(null=True, blank=True)
    declaration_reference = models.CharField(max_length=255, blank=True, default="")
    checked_by_admin_id = models.UUIDField()
    checked_at = PlatformDateTimeField()
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["uid", "start_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(principal_minor__gt=0),
                name="entities_external_debt_positive_principal",
            ),
            models.UniqueConstraint(
                fields=["uid", "creditor_identification", "financing_id"],
                condition=models.Q(ended_on__isnull=True),
                name="entities_external_debt_open_unique",
            ),
        ]
