from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.entities.models import (
    BorrowerDocument,
    BorrowerDocumentType,
    BorrowerEntity,
    BorrowerEntityEvent,
    BorrowerEntityType,
    BorrowerKybStatus,
)


class BorrowerEntitySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    legal_name = serializers.CharField()
    year_founded = serializers.IntegerField()
    entity_type = serializers.CharField()
    kyb_status = serializers.CharField()
    compliance_hold = serializers.BooleanField()
    can_transact = serializers.BooleanField()
    country = serializers.CharField()
    city = serializers.CharField(allow_blank=True)
    employees = serializers.IntegerField(allow_null=True)
    employees_year = serializers.IntegerField(allow_null=True)
    registration_number = serializers.CharField()
    uid = serializers.CharField(
        required=False, default="", help_text="18.9: Swiss UID (CHE-123.456.789)."
    )
    business_classification = serializers.CharField()
    business_classification_public = serializers.BooleanField()
    registered_address = serializers.CharField()
    registered_address_public = serializers.BooleanField()
    operating_address = serializers.CharField()
    contact_info = serializers.CharField()
    contact_info_public = serializers.BooleanField()
    industry_activity = serializers.CharField()
    ownership_structure = serializers.CharField()
    beneficial_owners = serializers.JSONField()
    directors_officers = serializers.JSONField()
    authorized_signatories = serializers.JSONField()
    bank_account_details = serializers.JSONField()
    kyb_aml_observations = serializers.CharField()
    financial_risk = serializers.CharField()
    financials_currency = serializers.CharField()
    assets_minor = serializers.IntegerField(allow_null=True)
    liabilities_minor = serializers.IntegerField(allow_null=True)
    revenue_last_year_minor = serializers.IntegerField(allow_null=True)
    profit_last_year_minor = serializers.IntegerField(allow_null=True)
    investor_story = serializers.JSONField()
    created_by_admin_id = serializers.UUIDField()
    updated_by_admin_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class BorrowerEntityCreateRequestSerializer(serializers.Serializer[Any]):
    legal_name = serializers.CharField(max_length=255)
    year_founded = serializers.IntegerField()
    entity_type = serializers.ChoiceField(
        choices=BorrowerEntityType.choices,
        default=BorrowerEntityType.SWISS_COMPANY,
    )
    kyb_status = serializers.ChoiceField(
        choices=BorrowerKybStatus.choices,
        default=BorrowerKybStatus.PENDING,
    )
    compliance_hold = serializers.BooleanField(default=False)
    country = serializers.CharField(required=False, allow_blank=True, max_length=64)
    city = serializers.CharField(required=False, allow_blank=True, max_length=128)
    employees = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    employees_year = serializers.IntegerField(required=False, allow_null=True)
    registration_number = serializers.CharField(required=False, allow_blank=True, max_length=128)
    uid = serializers.CharField(required=False, allow_blank=True, max_length=32)
    business_classification = serializers.CharField(required=False, allow_blank=True)
    business_classification_public = serializers.BooleanField(default=False)
    registered_address = serializers.CharField(required=False, allow_blank=True)
    registered_address_public = serializers.BooleanField(default=False)
    operating_address = serializers.CharField(required=False, allow_blank=True)
    contact_info = serializers.CharField(required=False, allow_blank=True)
    contact_info_public = serializers.BooleanField(default=False)
    industry_activity = serializers.CharField(required=False, allow_blank=True)
    ownership_structure = serializers.CharField(required=False, allow_blank=True)
    beneficial_owners = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    directors_officers = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    authorized_signatories = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    bank_account_details = serializers.DictField(required=False)
    kyb_aml_observations = serializers.CharField(required=False, allow_blank=True)
    financial_risk = serializers.CharField(required=False, allow_blank=True)
    financials_currency = serializers.CharField(required=False, allow_blank=True, max_length=3)
    assets_minor = serializers.IntegerField(required=False, allow_null=True)
    liabilities_minor = serializers.IntegerField(required=False, allow_null=True)
    revenue_last_year_minor = serializers.IntegerField(required=False, allow_null=True)
    profit_last_year_minor = serializers.IntegerField(required=False, allow_null=True)
    investor_story = serializers.JSONField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)
    evidence_summary = serializers.CharField(required=False, allow_blank=True)


class BorrowerEntityUpdateRequestSerializer(serializers.Serializer[Any]):
    legal_name = serializers.CharField(required=False, max_length=255)
    year_founded = serializers.IntegerField(required=False)
    entity_type = serializers.ChoiceField(required=False, choices=BorrowerEntityType.choices)
    kyb_status = serializers.ChoiceField(required=False, choices=BorrowerKybStatus.choices)
    compliance_hold = serializers.BooleanField(required=False)
    country = serializers.CharField(required=False, allow_blank=True, max_length=64)
    city = serializers.CharField(required=False, allow_blank=True, max_length=128)
    employees = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    employees_year = serializers.IntegerField(required=False, allow_null=True)
    clear_employees = serializers.BooleanField(required=False, default=False)
    registration_number = serializers.CharField(required=False, allow_blank=True, max_length=128)
    uid = serializers.CharField(required=False, allow_blank=True, max_length=32)
    business_classification = serializers.CharField(required=False, allow_blank=True)
    business_classification_public = serializers.BooleanField(required=False)
    registered_address = serializers.CharField(required=False, allow_blank=True)
    registered_address_public = serializers.BooleanField(required=False)
    operating_address = serializers.CharField(required=False, allow_blank=True)
    contact_info = serializers.CharField(required=False, allow_blank=True)
    contact_info_public = serializers.BooleanField(required=False)
    industry_activity = serializers.CharField(required=False, allow_blank=True)
    ownership_structure = serializers.CharField(required=False, allow_blank=True)
    beneficial_owners = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    directors_officers = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    authorized_signatories = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    bank_account_details = serializers.DictField(required=False)
    kyb_aml_observations = serializers.CharField(required=False, allow_blank=True)
    financial_risk = serializers.CharField(required=False, allow_blank=True)
    financials_currency = serializers.CharField(required=False, allow_blank=True, max_length=3)
    assets_minor = serializers.IntegerField(required=False, allow_null=True)
    liabilities_minor = serializers.IntegerField(required=False, allow_null=True)
    revenue_last_year_minor = serializers.IntegerField(required=False, allow_null=True)
    profit_last_year_minor = serializers.IntegerField(required=False, allow_null=True)
    clear_assets = serializers.BooleanField(required=False, default=False)
    clear_liabilities = serializers.BooleanField(required=False, default=False)
    clear_revenue_last_year = serializers.BooleanField(required=False, default=False)
    clear_profit_last_year = serializers.BooleanField(required=False, default=False)
    investor_story = serializers.JSONField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)
    evidence_summary = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("At least one borrower change is required.")
        return attrs


class BorrowerEntityListQuerySerializer(serializers.Serializer[Any]):
    kyb_status = serializers.ChoiceField(required=False, choices=BorrowerKybStatus.choices)
    entity_type = serializers.ChoiceField(required=False, choices=BorrowerEntityType.choices)
    compliance_hold = serializers.BooleanField(required=False)
    country = serializers.CharField(required=False, allow_blank=True, max_length=64)
    q = serializers.CharField(required=False, allow_blank=True, max_length=255)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


class BorrowerDocumentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    borrower_id = serializers.UUIDField(source="borrower.id")
    document_type = serializers.CharField()
    display_name = serializers.CharField()
    description = serializers.CharField()
    stored_file_id = serializers.IntegerField()
    investor_visible = serializers.BooleanField()
    # U33-DEC-20: library metadata.
    category = serializers.CharField(allow_blank=True)
    document_date = serializers.DateField(allow_null=True)
    period_label = serializers.CharField(allow_blank=True)
    issuer = serializers.CharField(allow_blank=True)
    version = serializers.CharField(allow_blank=True)
    document_status = serializers.CharField(allow_blank=True)
    created_by_admin_id = serializers.UUIDField()
    created_by_account_type = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class BorrowerDocumentCreateRequestSerializer(serializers.Serializer[Any]):
    stored_file_id = serializers.IntegerField()
    document_type = serializers.ChoiceField(choices=BorrowerDocumentType.choices)
    display_name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    investor_visible = serializers.BooleanField(default=False)
    note = serializers.CharField(required=False, allow_blank=True)


class BorrowerEntityEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    borrower_id = serializers.UUIDField(source="borrower.id")
    event_type = serializers.CharField()
    actor_user_id = serializers.UUIDField()
    actor_account_type = serializers.CharField()
    previous_kyb_status = serializers.CharField()
    new_kyb_status = serializers.CharField()
    note = serializers.CharField()
    evidence_summary = serializers.CharField()
    metadata = serializers.JSONField()
    occurred_at = serializers.DateTimeField()


class BorrowerInvestorDisclosureSerializer(serializers.Serializer[Any]):
    legal_name = serializers.CharField()
    year_founded = serializers.IntegerField()
    business_classification = serializers.CharField(required=False)
    registered_address = serializers.CharField(required=False)
    contact_info = serializers.CharField(required=False)
    country = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    employees = serializers.IntegerField(required=False)
    employees_year = serializers.IntegerField(required=False)
    financials_currency = serializers.CharField(required=False)
    assets_minor = serializers.IntegerField(required=False)
    liabilities_minor = serializers.IntegerField(required=False)
    revenue_last_year_minor = serializers.IntegerField(required=False)
    profit_last_year_minor = serializers.IntegerField(required=False)
    documents = serializers.ListField(child=serializers.DictField(), required=False)


def serialize_borrower_entity(borrower: BorrowerEntity) -> dict[str, Any]:
    return dict(BorrowerEntitySerializer(borrower).data)


def serialize_borrower_document(document: BorrowerDocument) -> dict[str, Any]:
    return dict(BorrowerDocumentSerializer(document).data)


def serialize_borrower_event(event: BorrowerEntityEvent) -> dict[str, Any]:
    return dict(BorrowerEntityEventSerializer(event).data)


class CreditFileDocumentRefSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    display_name = serializers.CharField()


FINANCIAL_YEAR_FIELD_HELP = "Minor units; costs, assets and debts as positive amounts."


class BorrowerFinancialYearSerializer(serializers.Serializer[Any]):
    """U33-DEC-20: the figures of one financial year (totals, and details that add up)."""

    id = serializers.UUIDField()
    year = serializers.IntegerField()
    period_end = serializers.DateField()
    currency = serializers.CharField()
    source_document = CreditFileDocumentRefSerializer(allow_null=True)
    revenue_minor = serializers.IntegerField(allow_null=True)
    materials_costs_minor = serializers.IntegerField(allow_null=True)
    staff_costs_minor = serializers.IntegerField(allow_null=True)
    other_operating_costs_minor = serializers.IntegerField(allow_null=True)
    depreciation_minor = serializers.IntegerField(allow_null=True)
    operating_profit_minor = serializers.IntegerField(allow_null=True)
    interest_expense_minor = serializers.IntegerField(allow_null=True)
    profit_before_tax_minor = serializers.IntegerField(allow_null=True)
    income_tax_minor = serializers.IntegerField(allow_null=True)
    net_profit_minor = serializers.IntegerField(allow_null=True)
    cash_minor = serializers.IntegerField(allow_null=True)
    trade_receivables_minor = serializers.IntegerField(allow_null=True)
    inventories_minor = serializers.IntegerField(allow_null=True)
    other_current_assets_minor = serializers.IntegerField(allow_null=True)
    current_assets_minor = serializers.IntegerField(allow_null=True)
    property_plant_equipment_minor = serializers.IntegerField(allow_null=True)
    other_non_current_assets_minor = serializers.IntegerField(allow_null=True)
    total_assets_minor = serializers.IntegerField(allow_null=True)
    current_financial_debt_minor = serializers.IntegerField(allow_null=True)
    non_current_financial_debt_minor = serializers.IntegerField(allow_null=True)
    financial_debt_minor = serializers.IntegerField(allow_null=True)
    trade_payables_minor = serializers.IntegerField(allow_null=True)
    other_operating_liabilities_minor = serializers.IntegerField(allow_null=True)
    equity_minor = serializers.IntegerField(allow_null=True)


class BorrowerFinancialYearListSerializer(serializers.Serializer[Any]):
    financial_years = BorrowerFinancialYearSerializer(many=True)


class BorrowerFinancialYearRequestSerializer(serializers.Serializer[Any]):
    year = serializers.IntegerField(min_value=1900, max_value=2100)
    period_end = serializers.DateField()
    currency = serializers.CharField(max_length=3)
    source_document_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    amounts = serializers.DictField(
        child=serializers.IntegerField(allow_null=True), help_text=FINANCIAL_YEAR_FIELD_HELP
    )


class BorrowerDebtFacilitySerializer(serializers.Serializer[Any]):
    """U33-DEC-20: one facility of the borrower's existing debt, at a date."""

    id = serializers.UUIDField()
    position = serializers.IntegerField()
    facility_type = serializers.CharField()
    currency = serializers.CharField()
    balance_minor = serializers.IntegerField()
    current_portion_minor = serializers.IntegerField(allow_null=True)
    non_current_portion_minor = serializers.IntegerField(allow_null=True)
    security_description = serializers.CharField(allow_blank=True)
    as_at = serializers.DateField()
    source_document = CreditFileDocumentRefSerializer(allow_null=True)


class CreditFileMoveRequestSerializer(serializers.Serializer[Any]):
    direction = serializers.ChoiceField(choices=["up", "down"])


class BorrowerDebtFacilityListSerializer(serializers.Serializer[Any]):
    debt_facilities = BorrowerDebtFacilitySerializer(many=True)


class BorrowerDebtFacilityRequestSerializer(serializers.Serializer[Any]):
    facility_type = serializers.CharField(max_length=255)
    currency = serializers.CharField(max_length=3)
    balance_minor = serializers.IntegerField(min_value=0)
    current_portion_minor = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )
    security_description = serializers.CharField(required=False, allow_blank=True, default="")
    as_at = serializers.DateField()
    source_document_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class BorrowerDocumentMetadataRequestSerializer(serializers.Serializer[Any]):
    category = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    document_date = serializers.DateField(required=False, allow_null=True, default=None)
    period_label = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=64
    )
    issuer = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    version = serializers.CharField(required=False, allow_blank=True, default="", max_length=32)
    document_status = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=64
    )


class SwissCreditorFinancingSerializer(serializers.Serializer[dict[str, object]]):
    loan_id = serializers.UUIDField()
    title = serializers.CharField()
    status = serializers.CharField()
    currency = serializers.CharField()
    creditors = serializers.IntegerField()


class BorrowerExternalDebtSerializer(serializers.Serializer[dict[str, object]]):
    id = serializers.UUIDField()
    creditor_name = serializers.CharField()
    creditor_identification = serializers.CharField()
    creditor_is_bank = serializers.BooleanField()
    financing_id = serializers.CharField()
    identical_terms_group = serializers.CharField(allow_blank=True)
    principal_minor = serializers.IntegerField()
    currency = serializers.CharField()
    start_date = serializers.DateField()
    ended_on = serializers.DateField(allow_null=True)
    declaration_reference = serializers.CharField(allow_blank=True)
    checked_at = serializers.DateTimeField()


class SwissCreditorModeOverviewSerializer(serializers.Serializer[dict[str, object]]):
    """18.9: the creditor mode of a Swiss borrower UID with its total and creditors."""

    uid = serializers.CharField()
    mode = serializers.ChoiceField(choices=["sandbox", "ten_twenty"])
    confirmed = serializers.BooleanField()
    confirmed_at = serializers.DateTimeField(allow_null=True)
    confirmed_by_admin_id = serializers.UUIDField(allow_null=True)
    confirmation_note = serializers.CharField(allow_blank=True)
    total_chf_minor = serializers.IntegerField(allow_null=True)
    total_error = serializers.CharField(allow_blank=True)
    sandbox_limit_chf_minor = serializers.IntegerField()
    borrower_creditors = serializers.IntegerField()
    borrower_creditor_limit = serializers.IntegerField()
    financing_creditor_limit = serializers.IntegerField()
    financings = SwissCreditorFinancingSerializer(many=True)
    external_debts = BorrowerExternalDebtSerializer(many=True)


class SwissCreditorModeRequestSerializer(serializers.Serializer[dict[str, object]]):
    mode = serializers.ChoiceField(choices=["sandbox", "ten_twenty"])
    note = serializers.CharField(required=False, allow_blank=True, default="")


class BorrowerExternalDebtRequestSerializer(serializers.Serializer[dict[str, object]]):
    creditor_name = serializers.CharField(max_length=255)
    creditor_identification = serializers.CharField(max_length=128)
    creditor_is_bank = serializers.BooleanField(default=False)
    financing_id = serializers.CharField(max_length=128)
    identical_terms_group = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=128
    )
    principal_minor = serializers.IntegerField(min_value=1)
    currency = serializers.ChoiceField(choices=["CHF", "EUR"])
    start_date = serializers.DateField()
    declaration_document_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    declaration_reference = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class BorrowerExternalDebtEndRequestSerializer(serializers.Serializer[dict[str, object]]):
    ended_on = serializers.DateField()


class SnbReferenceRateSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(read_only=True)
    currency = serializers.ChoiceField(choices=["EUR"])
    rate_date = serializers.DateField()
    chf_per_unit = serializers.DecimalField(max_digits=12, decimal_places=6)
    source = serializers.CharField(max_length=255)  # type: ignore[assignment]
