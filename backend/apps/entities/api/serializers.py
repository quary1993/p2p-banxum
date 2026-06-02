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
    registration_number = serializers.CharField()
    registered_address = serializers.CharField()
    operating_address = serializers.CharField()
    industry_activity = serializers.CharField()
    ownership_structure = serializers.CharField()
    beneficial_owners = serializers.JSONField()
    directors_officers = serializers.JSONField()
    authorized_signatories = serializers.JSONField()
    bank_account_details = serializers.JSONField()
    financials_currency = serializers.CharField()
    assets_minor = serializers.IntegerField(allow_null=True)
    liabilities_minor = serializers.IntegerField(allow_null=True)
    revenue_last_year_minor = serializers.IntegerField(allow_null=True)
    profit_last_year_minor = serializers.IntegerField(allow_null=True)
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
    registration_number = serializers.CharField(required=False, allow_blank=True, max_length=128)
    registered_address = serializers.CharField(required=False, allow_blank=True)
    operating_address = serializers.CharField(required=False, allow_blank=True)
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
    financials_currency = serializers.CharField(required=False, allow_blank=True, max_length=3)
    assets_minor = serializers.IntegerField(required=False, allow_null=True)
    liabilities_minor = serializers.IntegerField(required=False, allow_null=True)
    revenue_last_year_minor = serializers.IntegerField(required=False, allow_null=True)
    profit_last_year_minor = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)
    evidence_summary = serializers.CharField(required=False, allow_blank=True)


class BorrowerEntityUpdateRequestSerializer(serializers.Serializer[Any]):
    legal_name = serializers.CharField(required=False, max_length=255)
    year_founded = serializers.IntegerField(required=False)
    entity_type = serializers.ChoiceField(required=False, choices=BorrowerEntityType.choices)
    kyb_status = serializers.ChoiceField(required=False, choices=BorrowerKybStatus.choices)
    compliance_hold = serializers.BooleanField(required=False)
    country = serializers.CharField(required=False, allow_blank=True, max_length=64)
    registration_number = serializers.CharField(required=False, allow_blank=True, max_length=128)
    registered_address = serializers.CharField(required=False, allow_blank=True)
    operating_address = serializers.CharField(required=False, allow_blank=True)
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
    financials_currency = serializers.CharField(required=False, allow_blank=True, max_length=3)
    assets_minor = serializers.IntegerField(required=False, allow_null=True)
    liabilities_minor = serializers.IntegerField(required=False, allow_null=True)
    revenue_last_year_minor = serializers.IntegerField(required=False, allow_null=True)
    profit_last_year_minor = serializers.IntegerField(required=False, allow_null=True)
    clear_assets = serializers.BooleanField(required=False, default=False)
    clear_liabilities = serializers.BooleanField(required=False, default=False)
    clear_revenue_last_year = serializers.BooleanField(required=False, default=False)
    clear_profit_last_year = serializers.BooleanField(required=False, default=False)
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
    country = serializers.CharField(required=False)
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
