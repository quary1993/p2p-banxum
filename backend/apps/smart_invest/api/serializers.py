from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.smart_invest.models import SmartInvestCurrency, SmartInvestLoanKind
from backend.apps.smart_invest.services import collateral_choices, loan_field_choices

COLLATERAL_CHOICES = collateral_choices()
RISK_RATING_CHOICES = loan_field_choices("risk_rating")
LOAN_PURPOSE_CHOICES = loan_field_choices("purpose")
# Bounds a request; duplicates are accepted and de-duplicated by the service.
MAX_CHOICES = 100

ORIGINATORS_HELP = (
    '"banxum" for BANXUM direct loans and/or Loan Originator ids. Empty means any source.'
)
COLLATERAL_HELP = (
    '"any_secured" matches every secured loan, including collateral types added later; '
    '"unsecured" matches loans without collateral. Empty means no collateral condition.'
)


class SmartInvestRuleSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    is_active = serializers.BooleanField()
    revision = serializers.IntegerField()
    minimum_yield_bps = serializers.IntegerField(allow_null=True)
    maximum_term_months = serializers.IntegerField(allow_null=True)
    originators = serializers.ListField(child=serializers.CharField(), help_text=ORIGINATORS_HELP)
    collateral = serializers.ListField(
        child=serializers.ChoiceField(choices=COLLATERAL_CHOICES), help_text=COLLATERAL_HELP
    )
    currencies = serializers.ListField(
        child=serializers.ChoiceField(choices=SmartInvestCurrency.choices)
    )
    risk_ratings = serializers.ListField(child=serializers.ChoiceField(choices=RISK_RATING_CHOICES))
    purposes = serializers.ListField(child=serializers.ChoiceField(choices=LOAN_PURPOSE_CHOICES))
    loan_kinds = serializers.ListField(
        child=serializers.ChoiceField(choices=SmartInvestLoanKind.choices)
    )
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
    # Every list is multi-select: an empty or omitted list does not restrict matching.
    originators = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
        max_length=MAX_CHOICES,
        help_text=ORIGINATORS_HELP,
    )
    collateral = serializers.ListField(
        child=serializers.ChoiceField(choices=COLLATERAL_CHOICES),
        required=False,
        default=list,
        max_length=MAX_CHOICES,
        help_text=COLLATERAL_HELP,
    )
    currencies = serializers.ListField(
        child=serializers.ChoiceField(choices=SmartInvestCurrency.choices),
        required=False,
        default=list,
        max_length=MAX_CHOICES,
    )
    risk_ratings = serializers.ListField(
        child=serializers.ChoiceField(choices=RISK_RATING_CHOICES),
        required=False,
        default=list,
        max_length=MAX_CHOICES,
    )
    purposes = serializers.ListField(
        child=serializers.ChoiceField(choices=LOAN_PURPOSE_CHOICES),
        required=False,
        default=list,
        max_length=MAX_CHOICES,
    )
    loan_kinds = serializers.ListField(
        child=serializers.ChoiceField(choices=SmartInvestLoanKind.choices),
        required=False,
        default=list,
        max_length=MAX_CHOICES,
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
