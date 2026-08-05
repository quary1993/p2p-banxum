from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.smart_invest.models import (
    CollateralScope,
    CurrencyScope,
    LoanKind,
    OriginatorScope,
)


class SmartInvestRuleSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    is_active = serializers.BooleanField()
    revision = serializers.IntegerField()
    minimum_yield_bps = serializers.IntegerField(allow_null=True)
    maximum_term_months = serializers.IntegerField(allow_null=True)
    originator_scope = serializers.ChoiceField(choices=OriginatorScope.choices)
    originator_id = serializers.UUIDField(allow_null=True)
    collateral_scope = serializers.ChoiceField(choices=CollateralScope.choices)
    collateral_type = serializers.CharField(allow_blank=True)
    currency_scope = serializers.ChoiceField(choices=CurrencyScope.choices)
    risk_rating = serializers.CharField(allow_blank=True)
    purpose = serializers.CharField(allow_blank=True)
    loan_kind = serializers.ChoiceField(choices=LoanKind.choices)
    activated_at = serializers.DateTimeField(allow_null=True)
    deactivated_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class SmartInvestRuleSaveRequestSerializer(serializers.Serializer[Any]):
    minimum_yield_bps = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=100_000
    )
    maximum_term_months = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=1_200
    )
    originator_scope = serializers.ChoiceField(
        choices=OriginatorScope.choices, required=False, default=OriginatorScope.ALL
    )
    originator_id = serializers.UUIDField(required=False, allow_null=True)
    collateral_scope = serializers.ChoiceField(
        choices=CollateralScope.choices, required=False, default=CollateralScope.ALL
    )
    collateral_type = serializers.CharField(required=False, allow_blank=True, max_length=64)
    currency_scope = serializers.ChoiceField(
        choices=CurrencyScope.choices, required=False, default=CurrencyScope.ALL
    )
    risk_rating = serializers.CharField(required=False, allow_blank=True, max_length=32)
    purpose = serializers.CharField(required=False, allow_blank=True, max_length=64)
    loan_kind = serializers.ChoiceField(
        choices=LoanKind.choices, required=False, default=LoanKind.ALL
    )


class SmartInvestOpportunitySerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    product_type = serializers.CharField()
    investment_flow = serializers.CharField()
    title = serializers.CharField()
    purpose = serializers.CharField()
    collateral_type = serializers.CharField()
    interest_rate_bps = serializers.IntegerField()
    yield_bps = serializers.IntegerField()
    underlying_interest_rate_bps = serializers.IntegerField()
    term_months = serializers.IntegerField()
    remaining_term_days = serializers.IntegerField(allow_null=True)
    risk_rating = serializers.CharField()
    funding_deadline = serializers.DateField(allow_null=True)
    maturity_date = serializers.DateField(allow_null=True)
    status = serializers.CharField()
    loan_status = serializers.CharField()
    opportunity_status = serializers.CharField()
    currency = serializers.CharField()
    principal_minor = serializers.IntegerField()
    committed_principal_minor = serializers.IntegerField()
    remaining_capacity_minor = serializers.IntegerField()
    fillable_amount_minor = serializers.IntegerField()
    minimum_investment_minor = serializers.IntegerField()
    ltv_bps = serializers.IntegerField(allow_null=True)
    is_refinancing = serializers.BooleanField()
    originator_id = serializers.UUIDField(allow_null=True)
    originator_name = serializers.CharField(allow_null=True)
    borrower_display_name = serializers.CharField(allow_null=True)
    skin_in_the_game_bps = serializers.IntegerField(required=False, default=0)
    minimum_subscription_bps = serializers.IntegerField(required=False, default=5_000)


class SmartInvestResponseSerializer(serializers.Serializer[Any]):
    rule = SmartInvestRuleSerializer(allow_null=True)
    match_count = serializers.IntegerField()
    open_opportunity_count = serializers.IntegerField()
    matches = SmartInvestOpportunitySerializer(many=True)
