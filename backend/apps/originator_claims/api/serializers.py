from __future__ import annotations

from typing import Any, cast

from django.apps import apps
from rest_framework import serializers

from backend.apps.originator_claims.models import LoanOriginator, LoanOriginatorStatus


def _loan_field_choices(field_name: str) -> list[tuple[str, str]]:
    """Reuse the loan catalog without creating a domain-module import dependency."""
    loan_model = apps.get_model("loans", "Loan")
    field = cast(Any, loan_model)._meta.get_field(field_name)
    return [(str(value), str(label)) for value, label in field.choices]


LOAN_PURPOSE_CHOICES = _loan_field_choices("purpose")
REPAYMENT_TYPE_CHOICES = _loan_field_choices("repayment_type")
COLLATERAL_TYPE_CHOICES = _loan_field_choices("collateral_type")
RISK_RATING_CHOICES = _loan_field_choices("risk_rating")


class LoanOriginatorSerializer(serializers.ModelSerializer[LoanOriginator]):
    # Keep schema generation independent of each database backend's integer ranges.
    default_premium_fee_bps = serializers.IntegerField(
        min_value=0, max_value=10_000, required=False
    )

    class Meta:
        model = LoanOriginator
        fields = (
            "id",
            "legal_name",
            "public_name",
            "registration_number",
            "jurisdiction",
            "registered_address",
            "contact_info",
            "settlement_account_name",
            "settlement_iban",
            "settlement_bic",
            "kyb_evidence_reference",
            "kyb_aml_observations",
            "risk_observations",
            "status",
            "default_premium_fee_bps",
            "created_by_admin_id",
            "updated_by_admin_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_by_admin_id",
            "updated_by_admin_id",
            "created_at",
            "updated_at",
        )


class LoanOriginatorCreateSerializer(serializers.Serializer[dict[str, object]]):
    legal_name = serializers.CharField(max_length=255)
    public_name = serializers.CharField(max_length=255)
    registration_number = serializers.CharField(max_length=128)
    jurisdiction = serializers.CharField(max_length=64)
    registered_address = serializers.CharField()
    contact_info = serializers.CharField(required=False, allow_blank=True, default="")
    settlement_account_name = serializers.CharField(max_length=255)
    settlement_iban = serializers.CharField(max_length=128)
    settlement_bic = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    kyb_evidence_reference = serializers.CharField(max_length=255)
    kyb_aml_observations = serializers.CharField(required=False, allow_blank=True, default="")
    risk_observations = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=LoanOriginatorStatus.choices,
        required=False,
        default=LoanOriginatorStatus.INACTIVE,
    )
    default_premium_fee_bps = serializers.IntegerField(
        min_value=0, max_value=10_000, required=False, default=5000
    )


class LoanOriginatorUpdateSerializer(serializers.Serializer[dict[str, object]]):
    legal_name = serializers.CharField(max_length=255, required=False)
    public_name = serializers.CharField(max_length=255, required=False)
    registration_number = serializers.CharField(max_length=128, required=False)
    jurisdiction = serializers.CharField(max_length=64, required=False)
    registered_address = serializers.CharField(required=False)
    contact_info = serializers.CharField(required=False, allow_blank=True)
    settlement_account_name = serializers.CharField(max_length=255, required=False)
    settlement_iban = serializers.CharField(max_length=128, required=False)
    settlement_bic = serializers.CharField(max_length=64, required=False, allow_blank=True)
    kyb_evidence_reference = serializers.CharField(max_length=255, required=False)
    kyb_aml_observations = serializers.CharField(required=False, allow_blank=True)
    risk_observations = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=LoanOriginatorStatus.choices, required=False)
    default_premium_fee_bps = serializers.IntegerField(
        min_value=0, max_value=10_000, required=False
    )


class OriginatorLoanCreateSerializer(serializers.Serializer[dict[str, object]]):
    originator_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    investor_summary = serializers.CharField()
    purpose = serializers.ChoiceField(choices=LOAN_PURPOSE_CHOICES)
    purpose_description = serializers.CharField(required=False, allow_blank=True, default="")
    currency = serializers.CharField(min_length=3, max_length=3)
    original_principal_minor = serializers.IntegerField(min_value=1)
    interest_rate_bps = serializers.IntegerField(min_value=1)
    target_yield_bps = serializers.IntegerField(min_value=1)
    minimum_investment_minor = serializers.IntegerField(min_value=1)
    repayment_type = serializers.ChoiceField(choices=REPAYMENT_TYPE_CHOICES)
    interest_only_months = serializers.IntegerField(min_value=0, default=0)
    collateral_type = serializers.ChoiceField(choices=COLLATERAL_TYPE_CHOICES)
    collateral_value_minor = serializers.IntegerField(min_value=0)
    collateral_description = serializers.CharField(required=False, allow_blank=True, default="")
    risk_rating = serializers.ChoiceField(choices=RISK_RATING_CHOICES)
    csv_content = serializers.CharField()
    source_filename = serializers.CharField(max_length=255)
    as_of_date = serializers.DateField()
    borrower_snapshot = serializers.JSONField()
    premium_fee_bps = serializers.IntegerField(
        min_value=0, max_value=10_000, required=False, allow_null=True
    )
    skin_in_the_game_bps = serializers.IntegerField(
        min_value=0, max_value=9_999, required=False, default=0
    )


class OriginatorLoanScheduleRowResponseSerializer(serializers.Serializer[dict[str, object]]):
    installment_number = serializers.IntegerField()
    accrual_start_date = serializers.DateField()
    due_date = serializers.DateField()
    opening_principal_minor = serializers.IntegerField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    closing_principal_minor = serializers.IntegerField()


class OriginatorLoanPaymentRowResponseSerializer(serializers.Serializer[dict[str, object]]):
    reference = serializers.CharField()
    value_date = serializers.DateField()
    payment_type = serializers.CharField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    resulting_principal_minor = serializers.IntegerField()


class OriginatorAdminLoanDetailResponseSerializer(serializers.Serializer[dict[str, object]]):
    loan_id = serializers.UUIDField()
    originator_id = serializers.UUIDField()
    originator_name = serializers.CharField()
    title = serializers.CharField()
    investor_summary = serializers.CharField()
    purpose = serializers.CharField()
    purpose_description = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    opportunity_status = serializers.CharField()
    currency = serializers.CharField()
    original_principal_minor = serializers.IntegerField()
    current_outstanding_principal_minor = serializers.IntegerField()
    unsold_principal_minor = serializers.IntegerField()
    retained_principal_minor = serializers.IntegerField()
    sellable_principal_minor = serializers.IntegerField()
    interest_rate_bps = serializers.IntegerField()
    target_yield_bps = serializers.IntegerField()
    minimum_investment_minor = serializers.IntegerField()
    premium_fee_bps = serializers.IntegerField()
    skin_in_the_game_bps = serializers.IntegerField()
    repayment_type = serializers.CharField()
    interest_only_months = serializers.IntegerField()
    collateral_type = serializers.CharField()
    collateral_value_minor = serializers.IntegerField()
    collateral_description = serializers.CharField(allow_blank=True)
    risk_rating = serializers.CharField()
    maturity_date = serializers.DateField()
    schedule_revision = serializers.IntegerField()
    borrower_snapshot = serializers.JSONField()
    current_import_id = serializers.UUIDField()
    import_as_of_date = serializers.DateField()
    source_filename = serializers.CharField()
    source_sha256 = serializers.CharField()
    schedule = OriginatorLoanScheduleRowResponseSerializer(many=True)
    payment_history = OriginatorLoanPaymentRowResponseSerializer(many=True)
    is_on_hold = serializers.BooleanField()
    hold_reason = serializers.CharField(allow_blank=True)


class OriginatorLoanPublishSerializer(serializers.Serializer[dict[str, object]]):
    as_of_date = serializers.DateField()


class OriginatorLoanHoldSerializer(serializers.Serializer[dict[str, object]]):
    reason = serializers.CharField(max_length=255)


class OriginatorClaimQuoteRequestSerializer(serializers.Serializer[dict[str, object]]):
    requested_cash_minor = serializers.IntegerField(min_value=1)


class OriginatorClaimPurchaseRequestSerializer(serializers.Serializer[dict[str, object]]):
    document_acceptance_id = serializers.UUIDField()
    sensitive_action_code_id = serializers.UUIDField()
    sensitive_action_code = serializers.RegexField(r"^\d{6}$")
    idempotency_key = serializers.CharField(max_length=160)


class OriginatorSettlementRequestSerializer(serializers.Serializer[dict[str, object]]):
    originator_id = serializers.UUIDField()
    currency = serializers.CharField(min_length=3, max_length=3)
    purchase_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    repayment_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
        required=False,
        default=list,
    )
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField(max_length=128)
    bank_reference = serializers.CharField(max_length=160, required=False, allow_blank=True)
    payment_reference = serializers.CharField(max_length=160, required=False, allow_blank=True)
    evidence_reference = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class OriginatorBorrowerRepaymentRequestSerializer(serializers.Serializer[dict[str, object]]):
    csv_content = serializers.CharField()
    source_filename = serializers.CharField(max_length=255)
    as_of_date = serializers.DateField()
    payment_reference = serializers.CharField(max_length=128)
    booking_date = serializers.DateField()
    value_date = serializers.DateField()
    collection_account_identifier = serializers.CharField(max_length=128)
    payer_name = serializers.CharField(max_length=255)
    payer_account_identifier = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
    )
    bank_reference = serializers.CharField(
        max_length=160,
        required=False,
        allow_blank=True,
    )
    bank_payment_reference = serializers.CharField(
        max_length=160,
        required=False,
        allow_blank=True,
    )
    evidence_reference = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class OriginatorLoanProfileResponseSerializer(serializers.Serializer[dict[str, object]]):
    loan_id = serializers.UUIDField()
    originator_id = serializers.UUIDField()
    originator_name = serializers.CharField()
    opportunity_status = serializers.CharField()
    target_yield_bps = serializers.IntegerField()
    minimum_investment_minor = serializers.IntegerField()
    premium_fee_bps = serializers.IntegerField()
    current_outstanding_principal_minor = serializers.IntegerField()
    unsold_principal_minor = serializers.IntegerField()
    skin_in_the_game_bps = serializers.IntegerField()
    retained_principal_minor = serializers.IntegerField()
    sellable_principal_minor = serializers.IntegerField()
    maturity_date = serializers.DateField()
    schedule_revision = serializers.IntegerField()
    borrower_display_name = serializers.CharField()
    is_on_hold = serializers.BooleanField()
    hold_reason = serializers.CharField(allow_blank=True)
    import_id = serializers.UUIDField(required=False)


class OriginatorClaimCashFlowResponseSerializer(serializers.Serializer[dict[str, object]]):
    installment_number = serializers.IntegerField()
    accrual_start_date = serializers.DateField()
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    days_to_payment = serializers.IntegerField()
    present_value_minor = serializers.IntegerField()


class OriginatorClaimQuoteResponseSerializer(serializers.Serializer[dict[str, object]]):
    quote_id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    currency = serializers.CharField()
    requested_cash_minor = serializers.IntegerField()
    executable_cash_minor = serializers.IntegerField()
    assigned_principal_minor = serializers.IntegerField()
    outstanding_principal_at_pricing_minor = serializers.IntegerField()
    share_ppm = serializers.IntegerField()
    target_yield_bps = serializers.IntegerField()
    premium_discount_minor = serializers.IntegerField()
    rounding_remainder_minor = serializers.IntegerField()
    entitlement_start_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    cash_flows = OriginatorClaimCashFlowResponseSerializer(many=True)


class OriginatorClaimPurchaseResponseSerializer(serializers.Serializer[dict[str, object]]):
    purchase_id = serializers.UUIDField()
    quote_id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    holding_id = serializers.UUIDField()
    currency = serializers.CharField()
    cash_consideration_minor = serializers.IntegerField()
    assigned_principal_minor = serializers.IntegerField()
    outstanding_principal_at_pricing_minor = serializers.IntegerField()
    share_ppm = serializers.IntegerField()
    target_yield_bps = serializers.IntegerField()
    purchased_at = serializers.DateTimeField()


class OriginatorSettlementQueueRowSerializer(serializers.Serializer[dict[str, object]]):
    originator_id = serializers.UUIDField()
    originator_name = serializers.CharField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    purchase_amount_minor = serializers.IntegerField()
    servicing_amount_minor = serializers.IntegerField()
    purchase_count = serializers.IntegerField()
    repayment_count = serializers.IntegerField()
    purchase_ids = serializers.ListField(child=serializers.UUIDField())
    repayment_ids = serializers.ListField(child=serializers.UUIDField())
    oldest_purchased_at = serializers.DateTimeField()
    settlement_due_at = serializers.DateTimeField()
    task_due_at = serializers.DateTimeField()


class OriginatorBorrowerRepaymentResponseSerializer(serializers.Serializer[dict[str, object]]):
    repayment_id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    payment_reference = serializers.CharField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    investor_distributed_minor = serializers.IntegerField()
    originator_payable_minor = serializers.IntegerField()
    principal_after_minor = serializers.IntegerField()
    schedule_revision = serializers.IntegerField()


class OriginatorSettlementResponseSerializer(serializers.Serializer[dict[str, object]]):
    settlement_id = serializers.UUIDField()
    originator_id = serializers.UUIDField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    purchase_count = serializers.IntegerField()
    repayment_count = serializers.IntegerField()
    purchase_amount_minor = serializers.IntegerField()
    servicing_amount_minor = serializers.IntegerField()
    bank_operation_id = serializers.UUIDField()
    journal_entry_id = serializers.UUIDField()
    settled_at = serializers.DateTimeField()
