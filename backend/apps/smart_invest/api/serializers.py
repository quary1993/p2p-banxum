from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.smart_invest.models import SmartInvestCurrency, SmartInvestRepaymentOption
from backend.apps.smart_invest.services import (
    STATE_ACTIVE,
    STATE_NOT_SET_UP,
    STATE_PAUSED,
    collateral_choices,
)

COLLATERAL_CHOICES = collateral_choices()
# Bounds a request; duplicates are accepted and de-duplicated by the service.
MAX_CHOICES = 100

ORIGINATORS_HELP = (
    '"banxum" for BANXUM direct loans and/or Loan Originator ids. Empty means any source.'
)
COLLATERAL_HELP = (
    '"any_secured" matches every secured loan, including collateral types added later; '
    '"unsecured" matches loans without collateral. Empty means no collateral condition.'
)
COUNTRIES_HELP = (
    "Borrower countries as the opportunities carry them (borrower_country). Empty means "
    "any country."
)
LTV_HELP = (
    "Maximum loan-to-value in basis points. An opportunity without a loan-to-value figure "
    "does not match a limit."
)
REPAYMENT_HELP = (
    "18.3: the design's Repayments step. interest_only and principal_and_interest are the "
    "Periodic repayments; at_maturity is Payment at maturity. Empty means no preference."
)
AMOUNT_HELP = (
    "U33-DEC-19: optional usual amount per investment, in minor units of each selected "
    "currency. It prepares the amount on an opportunity page and never excludes an "
    "opportunity."
)


class SmartInvestRuleSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    is_active = serializers.BooleanField()
    state = serializers.ChoiceField(
        choices=[
            (STATE_NOT_SET_UP, "Not set up"),
            (STATE_ACTIVE, "Active"),
            (STATE_PAUSED, "Paused"),
        ],
        help_text=(
            "U33-DEC-19: paused keeps the preferences and shows no matches or alerts until "
            "the investor resumes."
        ),
    )
    revision = serializers.IntegerField()
    minimum_yield_bps = serializers.IntegerField(allow_null=True)
    maximum_term_months = serializers.IntegerField(allow_null=True)
    maximum_ltv_bps = serializers.IntegerField(allow_null=True, help_text=LTV_HELP)
    preferred_amount_minor = serializers.IntegerField(allow_null=True, help_text=AMOUNT_HELP)
    originators = serializers.ListField(child=serializers.CharField(), help_text=ORIGINATORS_HELP)
    collateral = serializers.ListField(
        child=serializers.ChoiceField(choices=COLLATERAL_CHOICES), help_text=COLLATERAL_HELP
    )
    currencies = serializers.ListField(
        child=serializers.ChoiceField(choices=SmartInvestCurrency.choices)
    )
    countries = serializers.ListField(child=serializers.CharField(), help_text=COUNTRIES_HELP)
    repayment = serializers.ListField(
        child=serializers.ChoiceField(choices=SmartInvestRepaymentOption.choices),
        help_text=REPAYMENT_HELP,
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
    maximum_ltv_bps = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=10_000, help_text=LTV_HELP
    )
    preferred_amount_minor = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=1_000_000_000_000,
        help_text=AMOUNT_HELP,
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
    countries = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
        max_length=MAX_CHOICES,
        help_text=COUNTRIES_HELP,
    )
    repayment = serializers.ListField(
        child=serializers.ChoiceField(choices=SmartInvestRepaymentOption.choices),
        required=False,
        default=list,
        max_length=MAX_CHOICES,
        help_text=REPAYMENT_HELP,
    )


class SmartInvestOpportunitySerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    product_type = serializers.CharField()
    investment_flow = serializers.CharField()
    title = serializers.CharField()
    purpose = serializers.CharField()
    collateral_type = serializers.CharField()
    security_types = serializers.ListField(child=serializers.CharField(), required=False)
    repayment_type = serializers.CharField(required=False, allow_blank=True)
    interest_rate_bps = serializers.IntegerField()
    yield_bps = serializers.IntegerField()
    underlying_interest_rate_bps = serializers.IntegerField()
    term_months = serializers.IntegerField()
    remaining_term_days = serializers.IntegerField(allow_null=True)
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
    borrower_country = serializers.CharField(allow_blank=True)
    borrower_city = serializers.CharField(allow_blank=True)
    skin_in_the_game_bps = serializers.IntegerField(required=False, default=0)
    minimum_subscription_bps = serializers.IntegerField(required=False, default=5_000)
    # U33-DEC-17: only for a Coming soon match.
    planned_opening_date = serializers.DateField(required=False, allow_null=True)


class SmartInvestChannelsSerializer(serializers.Serializer[Any]):
    """U33-DEC-30: the in-app and email channels of the match alerts."""

    in_app = serializers.BooleanField()
    email = serializers.BooleanField()


class SmartInvestResponseSerializer(serializers.Serializer[Any]):
    rule = SmartInvestRuleSerializer(allow_null=True)
    notification_channels = SmartInvestChannelsSerializer()
    match_count = serializers.IntegerField()
    open_opportunity_count = serializers.IntegerField()
    matches = SmartInvestOpportunitySerializer(many=True)
    # U33-DEC-17: matching Coming soon opportunities; not in match_count, nothing to invest yet.
    coming_soon_matches = SmartInvestOpportunitySerializer(many=True)
