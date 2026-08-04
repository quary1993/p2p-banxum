from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from backend.apps.loans.models import (
    CollateralType,
    Loan,
    LoanEvent,
    LoanPurpose,
    LoanStatus,
    RepaymentType,
    RiskRating,
)


class ManualScheduleRowRequestSerializer(serializers.Serializer[Any]):
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField(min_value=0)
    interest_minor = serializers.IntegerField(min_value=0)


class LoanSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    product_type = serializers.CharField()
    borrower_id = serializers.UUIDField(allow_null=True)
    borrower_name = serializers.SerializerMethodField()
    originator_id = serializers.SerializerMethodField()
    originator_name = serializers.SerializerMethodField()
    yield_bps = serializers.SerializerMethodField()
    opportunity_status = serializers.SerializerMethodField()
    minimum_investment_minor = serializers.SerializerMethodField()
    current_outstanding_principal_minor = serializers.SerializerMethodField()
    unsold_principal_minor = serializers.SerializerMethodField()
    maturity_date = serializers.SerializerMethodField()
    originator_schedule_revision = serializers.SerializerMethodField()
    status = serializers.CharField()
    title = serializers.CharField()
    investor_summary = serializers.CharField()
    purpose = serializers.CharField()
    purpose_description = serializers.CharField()
    is_refinancing = serializers.BooleanField()
    original_principal_minor = serializers.IntegerField()
    original_interest_rate_bps = serializers.IntegerField(allow_null=True)
    original_term_months = serializers.IntegerField(allow_null=True)
    original_repayment_type = serializers.SerializerMethodField()
    original_interest_only_months = serializers.IntegerField(allow_null=True)
    original_loan_start_date = serializers.DateField(allow_null=True)
    principal_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    interest_rate_bps = serializers.IntegerField()
    term_months = serializers.IntegerField()
    repayment_type = serializers.CharField()
    interest_only_months = serializers.IntegerField()
    loan_start_date = serializers.DateField()
    funding_deadline = serializers.DateField(allow_null=True)
    first_payment_date = serializers.DateField()
    pre_publication_paid_installments = serializers.ListField(child=serializers.IntegerField())
    collateral_type = serializers.CharField()
    collateral_value_minor = serializers.IntegerField()
    collateral_description = serializers.CharField()
    risk_rating = serializers.CharField()
    borrower_success_fee_bps = serializers.IntegerField()
    lender_payment_fee_minor = serializers.IntegerField()
    default_penalty_interest_bps = serializers.IntegerField()
    recovery_fee_bps = serializers.IntegerField()
    recovery_waterfall_version = serializers.CharField()
    schedule_version = serializers.IntegerField()
    total_scheduled_principal_minor = serializers.IntegerField()
    total_scheduled_interest_minor = serializers.IntegerField()
    committed_principal_minor = serializers.IntegerField()
    ltv_bps = serializers.IntegerField(allow_null=True)
    ltv_warnings = serializers.ListField(child=serializers.CharField())
    published_at = serializers.DateTimeField(allow_null=True)
    created_by_admin_id = serializers.UUIDField()
    updated_by_admin_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_original_repayment_type(self, obj: Loan) -> str | None:
        return obj.original_repayment_type or None

    def _originator_profile(self, obj: Loan) -> Any | None:
        try:
            return obj.originator_profile
        except (AttributeError, ObjectDoesNotExist):
            return None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_borrower_name(self, obj: Loan) -> str | None:
        borrower = obj.borrower
        if borrower is not None:
            return str(borrower.legal_name)
        profile = self._originator_profile(obj)
        return str(profile.borrower_legal_name) if profile is not None else None

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_originator_id(self, obj: Loan) -> Any | None:
        profile = self._originator_profile(obj)
        return profile.originator_id if profile is not None else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_originator_name(self, obj: Loan) -> str | None:
        profile = self._originator_profile(obj)
        return str(profile.originator.public_name) if profile is not None else None

    @extend_schema_field(serializers.IntegerField())
    def get_yield_bps(self, obj: Loan) -> int:
        profile = self._originator_profile(obj)
        return int(profile.target_yield_bps) if profile is not None else int(obj.interest_rate_bps)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_opportunity_status(self, obj: Loan) -> str | None:
        profile = self._originator_profile(obj)
        return str(profile.opportunity_status) if profile is not None else None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_minimum_investment_minor(self, obj: Loan) -> int | None:
        profile = self._originator_profile(obj)
        return int(profile.minimum_investment_minor) if profile is not None else None

    @extend_schema_field(serializers.IntegerField())
    def get_current_outstanding_principal_minor(self, obj: Loan) -> int:
        profile = self._originator_profile(obj)
        return (
            int(profile.current_outstanding_principal_minor)
            if profile is not None
            else int(obj.principal_minor)
        )

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_unsold_principal_minor(self, obj: Loan) -> int | None:
        profile = self._originator_profile(obj)
        return int(profile.unsold_principal_minor) if profile is not None else None

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_maturity_date(self, obj: Loan) -> Any | None:
        profile = self._originator_profile(obj)
        return profile.maturity_date if profile is not None else None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_originator_schedule_revision(self, obj: Loan) -> int | None:
        profile = self._originator_profile(obj)
        return int(profile.schedule_revision) if profile is not None else None


class LoanCreateRequestSerializer(serializers.Serializer[Any]):
    borrower_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    investor_summary = serializers.CharField()
    purpose = serializers.ChoiceField(choices=LoanPurpose.choices)
    purpose_description = serializers.CharField(required=False, allow_blank=True)
    is_refinancing = serializers.BooleanField(required=False, default=False)
    original_principal_minor = serializers.IntegerField(required=False)
    original_interest_rate_bps = serializers.IntegerField(required=False)
    original_term_months = serializers.IntegerField(required=False)
    original_repayment_type = serializers.ChoiceField(required=False, choices=RepaymentType.choices)
    original_interest_only_months = serializers.IntegerField(required=False)
    original_loan_start_date = serializers.DateField(required=False)
    principal_minor = serializers.IntegerField()
    currency = serializers.CharField(max_length=3)
    interest_rate_bps = serializers.IntegerField()
    term_months = serializers.IntegerField()
    repayment_type = serializers.ChoiceField(
        choices=RepaymentType.choices,
        default=RepaymentType.EQUAL_INSTALLMENTS,
    )
    interest_only_months = serializers.IntegerField(required=False, default=0)
    loan_start_date = serializers.DateField(required=False)
    funding_deadline = serializers.DateField(required=False)
    collateral_type = serializers.ChoiceField(
        choices=CollateralType.choices,
        default=CollateralType.REAL_ESTATE,
    )
    collateral_value_minor = serializers.IntegerField()
    collateral_description = serializers.CharField(required=False, allow_blank=True)
    risk_rating = serializers.ChoiceField(choices=RiskRating.choices)
    borrower_success_fee_bps = serializers.IntegerField(required=False, default=200)
    lender_payment_fee_minor = serializers.IntegerField(required=False, default=0)
    default_penalty_interest_bps = serializers.IntegerField(required=False, default=0)
    recovery_fee_bps = serializers.IntegerField(required=False, default=0)
    recovery_waterfall_version = serializers.CharField(required=False, default="v1")
    manual_schedule_rows = ManualScheduleRowRequestSerializer(
        many=True,
        required=False,
        allow_empty=False,
    )
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get("is_refinancing"):
            raise serializers.ValidationError(
                {
                    "is_refinancing": (
                        "New refinancing loans are disabled. Use the Loan Originator claim "
                        "workflow for existing loans."
                    )
                }
            )
        return attrs


class LoanUpdateRequestSerializer(serializers.Serializer[Any]):
    title = serializers.CharField(required=False, max_length=255)
    investor_summary = serializers.CharField(required=False)
    purpose = serializers.ChoiceField(required=False, choices=LoanPurpose.choices)
    purpose_description = serializers.CharField(required=False, allow_blank=True)
    is_refinancing = serializers.BooleanField(required=False)
    original_principal_minor = serializers.IntegerField(required=False)
    original_interest_rate_bps = serializers.IntegerField(required=False)
    original_term_months = serializers.IntegerField(required=False)
    original_repayment_type = serializers.ChoiceField(required=False, choices=RepaymentType.choices)
    original_interest_only_months = serializers.IntegerField(required=False)
    original_loan_start_date = serializers.DateField(required=False)
    principal_minor = serializers.IntegerField(required=False)
    interest_rate_bps = serializers.IntegerField(required=False)
    term_months = serializers.IntegerField(required=False)
    repayment_type = serializers.ChoiceField(required=False, choices=RepaymentType.choices)
    interest_only_months = serializers.IntegerField(required=False)
    loan_start_date = serializers.DateField(required=False)
    funding_deadline = serializers.DateField(required=False)
    collateral_type = serializers.ChoiceField(required=False, choices=CollateralType.choices)
    collateral_value_minor = serializers.IntegerField(required=False)
    collateral_description = serializers.CharField(required=False, allow_blank=True)
    risk_rating = serializers.ChoiceField(required=False, choices=RiskRating.choices)
    borrower_success_fee_bps = serializers.IntegerField(required=False)
    lender_payment_fee_minor = serializers.IntegerField(required=False)
    default_penalty_interest_bps = serializers.IntegerField(required=False)
    recovery_fee_bps = serializers.IntegerField(required=False)
    recovery_waterfall_version = serializers.CharField(required=False)
    manual_schedule_rows = ManualScheduleRowRequestSerializer(
        many=True,
        required=False,
        allow_empty=False,
    )
    investor_message = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("At least one loan change is required.")
        return attrs


class LoanListQuerySerializer(serializers.Serializer[Any]):
    borrower_id = serializers.UUIDField(required=False)
    product_type = serializers.CharField(required=False, max_length=32)
    status = serializers.ChoiceField(required=False, choices=LoanStatus.choices)
    purpose = serializers.ChoiceField(required=False, choices=LoanPurpose.choices)
    repayment_type = serializers.ChoiceField(required=False, choices=RepaymentType.choices)
    risk_rating = serializers.ChoiceField(required=False, choices=RiskRating.choices)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=3)
    q = serializers.CharField(required=False, allow_blank=True, max_length=255)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


class PublishLoanRequestSerializer(serializers.Serializer[Any]):
    pre_publication_paid_installment_numbers = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    note = serializers.CharField(required=False, allow_blank=True)


class LoanInstallmentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    schedule_version = serializers.IntegerField()
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    paid_principal_minor = serializers.IntegerField()
    paid_interest_minor = serializers.IntegerField()
    outstanding_principal_minor = serializers.IntegerField()
    outstanding_interest_minor = serializers.IntegerField()
    outstanding_total_minor = serializers.IntegerField()
    is_paid = serializers.BooleanField()
    days_past_due = serializers.IntegerField()
    status = serializers.CharField()
    row_type = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    payment_date = serializers.DateField(allow_null=True)
    admin_overridden = serializers.BooleanField()


class OriginalLoanScheduleRowSerializer(serializers.Serializer[Any]):
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    outstanding_after_minor = serializers.IntegerField()
    paid_before_publication = serializers.BooleanField()


class LoanEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    event_type = serializers.CharField()
    actor_user_id = serializers.UUIDField()
    actor_account_type = serializers.CharField()
    previous_status = serializers.CharField()
    new_status = serializers.CharField()
    note = serializers.CharField()
    metadata = serializers.JSONField()
    occurred_at = serializers.DateTimeField()


def serialize_loan(loan: Loan) -> dict[str, Any]:
    return dict(LoanSerializer(loan).data)


def serialize_loan_event(event: LoanEvent) -> dict[str, Any]:
    return dict(LoanEventSerializer(event).data)
