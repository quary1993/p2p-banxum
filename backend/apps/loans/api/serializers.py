from __future__ import annotations

from decimal import Decimal
from importlib import import_module
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from backend.apps.loans.models import (
    CollateralType,
    InterestConvention,
    Loan,
    LoanEvent,
    LoanPurpose,
    LoanSecurity,
    LoanStatus,
    PaymentFrequency,
    RepaymentType,
    RiskRating,
)
from backend.apps.platform_core.domain.loan_status import LoanStatusThresholds
from backend.apps.platform_core.selectors.settings import (
    loan_status_thresholds,
    platform_loan_status_thresholds,
)


class ManualScheduleRowRequestSerializer(serializers.Serializer[Any]):
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField(min_value=0)
    # 18.6: a custom schedule imports due date + principal; the engine calculates the interest.
    interest_minor = serializers.IntegerField(min_value=0, required=False, default=0)


class LoanSecurityOverviewSerializer(serializers.Serializer[Any]):
    """U33-DEC-21: a security of the loan in the admin loan list (type and status only)."""

    security_type = serializers.CharField()
    status = serializers.CharField(allow_blank=True)


def admin_loan_list_context(loans: list[Loan]) -> dict[str, Any]:
    """One query per list for the securities and the opening alerts of the rows."""
    loan_ids = [str(loan.pk) for loan in loans]
    overview: dict[str, list[dict[str, str]]] = {loan_id: [] for loan_id in loan_ids}
    for security in LoanSecurity.objects.filter(loan_id__in=loan_ids).order_by(
        "position", "created_at"
    ):
        overview[str(security.loan_id)].append(
            {"security_type": security.security_type, "status": security.status}
        )
    coming_soon = [str(loan.pk) for loan in loans if loan.coming_soon_at is not None]
    counts = (
        import_module("backend.apps.marketplace_primary.services").opening_alert_counts(coming_soon)
        if coming_soon
        else {}
    )
    return {"security_overview": overview, "opening_alert_counts": counts}


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
    # U33-DEC-09: the contract's own Late / Default days (null = platform settings), the days
    # in use, and the contract termination date.
    late_threshold_days = serializers.IntegerField(allow_null=True)
    default_threshold_days = serializers.IntegerField(allow_null=True)
    effective_late_threshold_days = serializers.SerializerMethodField()
    effective_default_threshold_days = serializers.SerializerMethodField()
    contract_terminated_on = serializers.DateField(allow_null=True)
    # 18.6 interest engine: convention, frequency, grace, penalty X and its investors' share, the
    # real payout day and the admin's Default declaration.
    interest_convention = serializers.CharField()
    payment_frequency = serializers.CharField()
    grace_business_days = serializers.IntegerField()
    penalty_daily_rate_percent = serializers.DecimalField(max_digits=7, decimal_places=4)
    penalty_investor_share_bps = serializers.IntegerField()
    payout_date = serializers.DateField(allow_null=True)
    default_declared_on = serializers.DateField(allow_null=True)
    # U33-DEC-17: shown as Coming soon since, and the planned opening date.
    coming_soon_at = serializers.DateTimeField(allow_null=True)
    planned_opening_date = serializers.DateField(allow_null=True)
    # Admin list: the loan's securities and the investors waiting for the opening email.
    security_overview = serializers.SerializerMethodField()
    opening_alert_count = serializers.SerializerMethodField()
    minimum_subscription_bps = serializers.IntegerField(required=False, default=5_000)
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

    def _thresholds(self, obj: Loan) -> LoanStatusThresholds:
        # One settings read per response, shared by the rows of a list.
        platform = self.context.get("platform_loan_status_thresholds")
        if platform is None:
            platform = platform_loan_status_thresholds()
            if isinstance(self.context, dict):
                self.context["platform_loan_status_thresholds"] = platform
        return loan_status_thresholds(obj, platform=platform)

    @extend_schema_field(LoanSecurityOverviewSerializer(many=True))
    def get_security_overview(self, obj: Loan) -> list[dict[str, str]]:
        batch = self.context.get("security_overview") if isinstance(self.context, dict) else None
        if batch is not None:
            return list(batch.get(str(obj.pk), []))
        return [
            {"security_type": security.security_type, "status": security.status}
            for security in obj.securities.order_by("position", "created_at")
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_opening_alert_count(self, obj: Loan) -> int:
        batch = self.context.get("opening_alert_counts") if isinstance(self.context, dict) else None
        if batch is not None:
            return int(batch.get(str(obj.pk), 0))
        if obj.coming_soon_at is None:
            return 0
        counts = import_module("backend.apps.marketplace_primary.services").opening_alert_counts(
            [str(obj.pk)]
        )
        return int(counts.get(str(obj.pk), 0))

    @extend_schema_field(serializers.IntegerField())
    def get_effective_late_threshold_days(self, obj: Loan) -> int:
        return self._thresholds(obj).late_days

    @extend_schema_field(serializers.IntegerField())
    def get_effective_default_threshold_days(self, obj: Loan) -> int:
        return self._thresholds(obj).default_days

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
    minimum_subscription_bps = serializers.IntegerField(
        required=False, default=5_000, min_value=0, max_value=10_000
    )
    manual_schedule_rows = ManualScheduleRowRequestSerializer(
        many=True,
        required=False,
        allow_empty=False,
    )
    note = serializers.CharField(required=False, allow_blank=True)
    # 18.6 (audit S5-7): every loan created here uses the Actual/365 Fixed engine; the earlier
    # monthly schedule cannot be chosen (it exists only for contracts signed before the engine).
    interest_convention = serializers.ChoiceField(
        choices=[(InterestConvention.ACT_365_FIXED.value, InterestConvention.ACT_365_FIXED.label)],
        required=False,
        default=InterestConvention.ACT_365_FIXED,
    )
    payment_frequency = serializers.ChoiceField(
        choices=PaymentFrequency.choices, required=False, default=PaymentFrequency.MONTHLY
    )
    grace_business_days = serializers.IntegerField(
        required=False, default=0, min_value=0, max_value=30
    )
    penalty_daily_rate_percent = serializers.DecimalField(
        max_digits=7, decimal_places=4, required=False, default=Decimal("0"), min_value=Decimal("0")
    )
    penalty_investor_share_bps = serializers.IntegerField(
        required=False, default=10_000, min_value=0, max_value=10_000
    )

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
    minimum_subscription_bps = serializers.IntegerField(
        required=False, min_value=0, max_value=10_000
    )
    manual_schedule_rows = ManualScheduleRowRequestSerializer(
        many=True,
        required=False,
        allow_empty=False,
    )
    investor_message = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)
    payment_frequency = serializers.ChoiceField(choices=PaymentFrequency.choices, required=False)
    grace_business_days = serializers.IntegerField(required=False, min_value=0, max_value=30)
    penalty_daily_rate_percent = serializers.DecimalField(
        max_digits=7, decimal_places=4, required=False, min_value=Decimal("0")
    )
    penalty_investor_share_bps = serializers.IntegerField(
        required=False, min_value=0, max_value=10_000
    )

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
    # 18.6: the unadjusted due date (before the business-day move and the grace) and the start of
    # the row's interest period; empty for earlier schedules.
    original_due_date = serializers.DateField(allow_null=True, required=False)
    interest_start = serializers.DateField(allow_null=True, required=False)


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


class LoanHistoryEntrySerializer(serializers.Serializer[Any]):
    """One line of a loan's admin history: a loan event or an audit entry about the loan."""

    id = serializers.CharField()
    kind = serializers.ChoiceField(choices=["event", "change"])
    code = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    actor = serializers.CharField()
    previous_status = serializers.CharField(allow_blank=True)
    new_status = serializers.CharField(allow_blank=True)
    note = serializers.CharField(allow_blank=True)
    details = serializers.JSONField()


class LoanHistoryResponseSerializer(serializers.Serializer[Any]):
    entries = LoanHistoryEntrySerializer(many=True)


def serialize_loan(loan: Loan) -> dict[str, Any]:
    return dict(LoanSerializer(loan).data)


def serialize_loan_event(event: LoanEvent) -> dict[str, Any]:
    return dict(LoanEventSerializer(event).data)


class LoanComingSoonRequestSerializer(serializers.Serializer[Any]):
    planned_opening_date = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)


class LoanSecurityDocumentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    display_name = serializers.CharField()


class LoanSecuritySerializer(serializers.Serializer[Any]):
    """U33-DEC-21: one security of a loan; only the fields that apply are filled."""

    id = serializers.UUIDField()
    position = serializers.IntegerField()
    security_type = serializers.CharField()
    is_guarantee = serializers.BooleanField()
    description = serializers.CharField(allow_blank=True)
    # 18.3: the anonymous asset name of the public site.
    public_name = serializers.CharField(allow_blank=True, required=False, default="")
    holder_name = serializers.CharField(
        allow_blank=True, help_text="Owner of the asset or right, or the guarantor."
    )
    rank = serializers.IntegerField(allow_null=True, help_text="1 is first rank.")
    status = serializers.CharField(
        allow_blank=True, help_text="in_place, pending, released, or empty when not recorded."
    )
    value_minor = serializers.IntegerField(allow_null=True)
    valuation_date = serializers.DateField(allow_null=True)
    valuation_source = serializers.CharField(allow_blank=True)
    appraiser = serializers.CharField(allow_blank=True)
    prior_ranking_debt_minor = serializers.IntegerField(allow_null=True)
    insurance = serializers.CharField(allow_blank=True)
    undertaking_scope = serializers.CharField(allow_blank=True)
    undertaking_limit_minor = serializers.IntegerField(allow_null=True)
    # C06: the security the loan's summary shows (one per loan).
    is_main = serializers.BooleanField()
    # F16: its value counts in the loan-to-value (the loan's collateral value is the sum).
    counts_in_ltv = serializers.BooleanField()
    # Audit S1-3: the asset's stable identifier (one asset never counts twice).
    asset_reference = serializers.CharField(allow_blank=True)
    # F16: a valuation in another currency (value_minor is then the converted value).
    valuation_currency = serializers.CharField(allow_blank=True)
    valuation_amount_minor = serializers.IntegerField(allow_null=True)
    valuation_fx_rate = serializers.CharField(allow_null=True)
    valuation_fx_rate_date = serializers.DateField(allow_null=True)
    documents = LoanSecurityDocumentSerializer(many=True)


class LoanSecurityListSerializer(serializers.Serializer[Any]):
    securities = LoanSecuritySerializer(many=True)
    # The borrower's documents that can be attached to a security.
    borrower_documents = LoanSecurityDocumentSerializer(many=True)


class LoanSecurityMoveRequestSerializer(serializers.Serializer[Any]):
    direction = serializers.ChoiceField(choices=["up", "down"])


class LoanSecurityRequestSerializer(serializers.Serializer[Any]):
    security_type = serializers.CharField(max_length=32)
    description = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=4000
    )
    public_name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=120,
        help_text="18.3: anonymous asset name for the public site (no borrower name or address).",
    )
    holder_name = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )
    rank = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)
    status = serializers.ChoiceField(
        choices=["", "in_place", "pending", "released"], required=False, default=""
    )
    value_minor = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )
    valuation_date = serializers.DateField(required=False, allow_null=True, default=None)
    valuation_source = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )
    appraiser = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    prior_ranking_debt_minor = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )
    insurance = serializers.CharField(required=False, allow_blank=True, default="", max_length=4000)
    undertaking_scope = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=4000
    )
    undertaking_limit_minor = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )
    document_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    # F16: omitted keeps the current choice; a new security takes the default of its type.
    counts_in_ltv = serializers.BooleanField(required=False, allow_null=True, default=None)
    asset_reference = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=160
    )
    valuation_currency = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=3
    )
    valuation_amount_minor = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=0
    )
    valuation_fx_rate = serializers.DecimalField(
        max_digits=18, decimal_places=8, required=False, allow_null=True, default=None
    )
    valuation_fx_rate_date = serializers.DateField(required=False, allow_null=True, default=None)


class LoanCreditCheckSerializer(serializers.Serializer[Any]):
    """U33-DEC-20: a recorded check (what, result, source, date)."""

    id = serializers.UUIDField()
    position = serializers.IntegerField()
    name = serializers.CharField()
    result = serializers.CharField()
    # "source" is also a DRF Field attribute; the stubs type it differently.
    source = serializers.CharField(allow_blank=True)  # type: ignore[assignment]
    checked_on = serializers.DateField(allow_null=True)
    # "received" or "reviewed" (the design's chip); empty for older checks.
    status = serializers.CharField(allow_blank=True)


class LoanReportingMilestoneSerializer(serializers.Serializer[Any]):
    """U33-DEC-20: one step of the reporting over the loan term (when, what, details)."""

    when = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=120)
    body = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")


class LoanReportingPlanSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=["proposed", "agreed"])
    milestones = LoanReportingMilestoneSerializer(many=True)


class LoanReportingPlanRequestSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=["", "proposed", "agreed"], allow_blank=True)
    milestones = LoanReportingMilestoneSerializer(many=True)


class LoanCreditChecksSerializer(serializers.Serializer[Any]):
    checks = LoanCreditCheckSerializer(many=True)
    monitoring_frequency = serializers.CharField(allow_blank=True)
    monitoring_focus = serializers.CharField(allow_blank=True)
    # 18.3: the credit file's "Source of repayment".
    repayment_source = serializers.CharField(allow_blank=True, required=False, default="")
    reporting_plan_status = serializers.CharField(allow_blank=True)
    reporting_milestones = LoanReportingMilestoneSerializer(many=True)


class LoanCreditCheckRequestSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=255)
    result = serializers.CharField(max_length=4000)
    source = serializers.CharField(  # type: ignore[assignment]
        required=False, allow_blank=True, default="", max_length=255
    )
    checked_on = serializers.DateField(required=False, allow_null=True, default=None)
    status = serializers.ChoiceField(
        choices=["", "received", "reviewed"], required=False, allow_blank=True, default=""
    )


class LoanRepaymentSourceRequestSerializer(serializers.Serializer[Any]):
    text = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)


class LoanMonitoringRequestSerializer(serializers.Serializer[Any]):
    frequency = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    focus = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
