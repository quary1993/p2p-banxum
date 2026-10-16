from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from backend.apps.marketplace_primary.models import (
    PrimaryInvestmentOrder,
    PrimaryLoanCancellation,
    PrimaryLoanClose,
)
from backend.apps.platform_core.api.sensitive_actions import sensitive_action_pin_field


class PublicProjectListQuerySerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=500,
        default=250,
        help_text="Maximum number of projects to return (1 to 500).",
    )


class PublicProjectOriginatorSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(help_text="Loan Originator id.")
    name = serializers.CharField(help_text="The Loan Originator's public name.")
    country = serializers.CharField(
        allow_blank=True,
        help_text="ISO 3166-1 alpha-2 country of the Loan Originator when known, else empty.",
    )


class PublicProjectRecordSerializer(serializers.Serializer[Any]):
    installments_total = serializers.IntegerField(
        help_text=(
            "Installments of the repayment schedule (for a Loan Originator claim: the "
            "installments after the investors' entitlement start)."
        ),
    )
    installments_paid = serializers.IntegerField(help_text="Installments paid in full.")
    principal_repaid_minor = serializers.IntegerField(
        help_text="Principal repaid to investors so far, in minor units.",
    )
    interest_paid_minor = serializers.IntegerField(
        help_text="Interest paid to investors so far, in minor units.",
    )
    outstanding_principal_minor = serializers.IntegerField(
        help_text=(
            "Principal not repaid yet (loan amount minus principal repaid), in minor units. "
            "For a loan in default: outstanding at default, before recovery."
        ),
    )
    days_past_due = serializers.IntegerField(
        help_text="Days past the due date of the oldest unpaid installment; 0 unless late or "
        "in default.",
    )
    defaulted_on = serializers.DateField(
        allow_null=True,
        help_text="Date the loan went into default; null unless in default.",
    )
    public_note = serializers.CharField(
        allow_blank=True,
        help_text="Text of the latest public loan note by Garanta, or empty.",
    )


class PublicProjectSerializer(serializers.Serializer[Any]):
    """A loan on the public site. Never carries the borrower's name or identifiers."""

    loan_id = serializers.UUIDField(help_text="Public id for the project page link.")
    title = serializers.CharField(help_text="Loan title (never the borrower's name).")
    product_type = serializers.ChoiceField(
        choices=["direct", "originator_claim"],
        help_text="A BANXUM Direct loan or a Loan Originator claim.",
    )
    is_refinancing = serializers.BooleanField(help_text="Loan type: new or refinancing.")
    public_status = serializers.ChoiceField(
        choices=["open", "fully_funded", "repaying", "late", "repaid", "default"],
        help_text=(
            "open: published, capacity left, round still taking orders; fully_funded: "
            "nothing left to invest, round not closed yet; repaying: funded or active; "
            "late; repaid; default: defaulted or written off."
        ),
    )
    currency = serializers.CharField(help_text="ISO currency code (CHF or EUR).")
    principal_minor = serializers.IntegerField(
        help_text=(
            "Loan amount offered to investors, in minor units: the final principal after "
            "a partial close; for a Loan Originator claim the principal offered in (or "
            "subscribed at the close of) its round."
        ),
    )
    committed_principal_minor = serializers.IntegerField(
        help_text="Funded so far, in minor units (equal to the principal once funded).",
    )
    remaining_capacity_minor = serializers.IntegerField(
        help_text="Amount still open for investment, in minor units; 0 unless open.",
    )
    minimum_investment_minor = serializers.IntegerField(
        allow_null=True,
        help_text=(
            "What a new investor must invest now (the loan minimum, capped by the remaining "
            "capacity; for a Swiss-borrower loan raised so the places left can fill the "
            "loan), in minor units; null unless open, and null when a Swiss-borrower loan "
            "has no place left."
        ),
    )
    investors_count = serializers.IntegerField(
        help_text=(
            "Distinct investors: current (not transferred) holders and investors with money "
            "allocated to the funding round."
        ),
    )
    max_investors = serializers.IntegerField(
        allow_null=True,
        help_text=(
            "Most investors this loan may have (Swiss borrower, platform setting, default "
            "20); null when no limit applies."
        ),
    )
    places_left = serializers.IntegerField(
        allow_null=True,
        help_text=(
            "Places left for new investors (max_investors - investors_count, never below "
            "0); null when no limit applies."
        ),
    )
    interest_rate_bps = serializers.IntegerField(
        help_text="Investor interest per year in basis points (the investor marketplace yield).",
    )
    term_months = serializers.IntegerField(help_text="Loan period in months.")
    repayment_type = serializers.CharField(help_text="RepaymentType value.")
    risk_rating = serializers.CharField(help_text="RiskRating value.")
    collateral_type = serializers.CharField(help_text="CollateralType value.")
    collateral_description = serializers.CharField(allow_blank=True)
    ltv_bps = serializers.IntegerField(
        allow_null=True,
        help_text="Loan-to-value in basis points; null without a collateral value.",
    )
    purpose = serializers.CharField(help_text="LoanPurpose value.")
    purpose_description = serializers.CharField(allow_blank=True)
    investor_summary = serializers.CharField(allow_blank=True)
    borrower_country = serializers.CharField(
        allow_blank=True,
        help_text="Borrower country as ISO 3166-1 alpha-2 when known, else empty.",
    )
    borrower_sector = serializers.CharField(
        allow_blank=True,
        help_text="Borrower business classification when it is marked public, else empty.",
    )
    borrower_year_founded = serializers.IntegerField(allow_null=True)
    originator = PublicProjectOriginatorSerializer(
        allow_null=True,
        help_text="The Loan Originator of a claim; null for a Direct loan.",
    )
    published_at = serializers.DateTimeField(allow_null=True)
    funding_deadline = serializers.DateField(allow_null=True)
    funded_at = serializers.DateField(
        allow_null=True,
        help_text="Funding close date; null while the round is running.",
    )
    record = PublicProjectRecordSerializer(
        allow_null=True,
        help_text="Repayment record; only for repaying, late, repaid and default loans.",
    )


class PublicStatisticsCurrencySerializer(serializers.Serializer[Any]):
    currency = serializers.CharField(help_text="ISO currency code (CHF or EUR).")
    loans = serializers.IntegerField(help_text="Funded loans in this currency.")
    lent_minor = serializers.IntegerField(help_text="Principal lent, in minor units.")
    principal_repaid_minor = serializers.IntegerField()
    interest_paid_minor = serializers.IntegerField()
    outstanding_minor = serializers.IntegerField(
        help_text="Outstanding principal of loans not in default, in minor units.",
    )
    defaulted_minor = serializers.IntegerField(
        help_text="Outstanding principal of loans in default (before recovery), in minor units.",
    )


class PublicStatisticsSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField(help_text="When the figures were computed.")
    loans_funded = serializers.IntegerField(
        help_text="Funded public loans (repaying, late, repaid or in default).",
    )
    loans_repaid = serializers.IntegerField()
    loans_late = serializers.IntegerField()
    loans_defaulted = serializers.IntegerField()
    average_interest_rate_bps = serializers.IntegerField(
        allow_null=True,
        help_text=(
            "Investor interest weighted by principal over funded loans, rounded half up; "
            "null without funded loans."
        ),
    )
    originators_count = serializers.IntegerField(
        help_text="Active Loan Originators with at least one public claim.",
    )
    countries_count = serializers.IntegerField(
        help_text="Distinct borrower countries over all public projects.",
    )
    by_currency = PublicStatisticsCurrencySerializer(
        many=True,
        help_text="One row per currency; CHF and EUR are always present.",
    )


class PublicOriginatorSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(help_text="Loan Originator id.")
    name = serializers.CharField(help_text="The Loan Originator's public name.")
    country = serializers.CharField(
        allow_blank=True,
        help_text="ISO 3166-1 alpha-2 country when known, else empty.",
    )
    partner_since = serializers.DateField(help_text="Date the partner was added.")
    claims_funded = serializers.IntegerField(
        help_text="Public claims of this originator that were funded.",
    )


class MarketplaceLoanPreviewSerializer(serializers.Serializer[Any]):
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
    minimum_investment_minor = serializers.IntegerField(
        help_text=(
            "What the viewing investor must invest now, in minor units. On a Swiss-borrower "
            "loan a new investor's minimum is raised so the places left can fill the loan; "
            "an investor who already invests keeps the loan minimum, capped by the "
            "remaining capacity."
        ),
    )
    max_investors = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text=(
            "Most investors this loan may have (Swiss borrower, platform setting, default "
            "20); null when no limit applies."
        ),
    )
    places_left = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Places left for new investors; null when no limit applies.",
    )
    is_existing_investor = serializers.BooleanField(
        required=False,
        allow_null=True,
        help_text=(
            "The viewing investor already invests in this loan, so needs no new place; "
            "null when no limit applies."
        ),
    )
    ltv_bps = serializers.IntegerField(allow_null=True)
    is_refinancing = serializers.BooleanField()
    originator_id = serializers.UUIDField(allow_null=True)
    originator_name = serializers.CharField(allow_null=True)
    borrower_display_name = serializers.CharField(allow_null=True)
    distribution_model = serializers.CharField(
        required=False,
        allow_null=True,
    )
    entitlement_start_date = serializers.DateField(
        required=False,
        allow_null=True,
    )
    investor_interest_participation_bps = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    investor_penalty_participation_bps = serializers.IntegerField(
        required=False,
        allow_null=True,
    )
    skin_in_the_game_bps = serializers.IntegerField(required=False, default=0)
    minimum_subscription_bps = serializers.IntegerField(required=False, default=5_000)


class MarketplaceOriginalLoanScheduleRowSerializer(serializers.Serializer[Any]):
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    outstanding_after_minor = serializers.IntegerField()
    paid_before_publication = serializers.BooleanField()


class MarketplaceLoanScheduleRowSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(required=False)
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    outstanding_after_minor = serializers.IntegerField()
    status = serializers.CharField(required=False)
    row_type = serializers.CharField(required=False)
    label = serializers.CharField(required=False)  # type: ignore[assignment]
    payment_date = serializers.DateField(allow_null=True, required=False)
    paid_principal_minor = serializers.IntegerField(required=False)
    paid_interest_minor = serializers.IntegerField(required=False)
    outstanding_principal_minor = serializers.IntegerField(required=False)
    outstanding_interest_minor = serializers.IntegerField(required=False)


class MarketplaceOriginatorScheduleRowSerializer(serializers.Serializer[Any]):
    installment_number = serializers.IntegerField()
    accrual_start_date = serializers.DateField()
    due_date = serializers.DateField()
    opening_principal_minor = serializers.IntegerField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    outstanding_after_minor = serializers.IntegerField()


class MarketplaceOriginatorPaymentRowSerializer(serializers.Serializer[Any]):
    reference = serializers.CharField()
    value_date = serializers.DateField()
    payment_type = serializers.CharField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()
    resulting_principal_minor = serializers.IntegerField()


class StoryDocumentSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField()
    blocks = serializers.ListField(child=serializers.DictField())


class MarketplaceLoanDetailSerializer(MarketplaceLoanPreviewSerializer):
    default_penalty_interest_bps = serializers.IntegerField(required=False, default=0)
    borrower_id = serializers.UUIDField(allow_null=True)
    borrower_disclosure = serializers.DictField()
    story = StoryDocumentSerializer(required=False)
    investor_summary = serializers.CharField()
    purpose_description = serializers.CharField()
    collateral_value_minor = serializers.IntegerField()
    collateral_description = serializers.CharField()
    ltv_warnings = serializers.ListField(child=serializers.CharField())
    original_principal_minor = serializers.IntegerField()
    original_interest_rate_bps = serializers.IntegerField(allow_null=True)
    original_term_months = serializers.IntegerField(allow_null=True)
    original_repayment_type = serializers.CharField(allow_null=True)
    original_interest_only_months = serializers.IntegerField(allow_null=True)
    original_loan_start_date = serializers.DateField(allow_null=True)
    original_loan_schedule = MarketplaceOriginalLoanScheduleRowSerializer(
        many=True,
        required=False,
    )
    repayment_type = serializers.CharField()
    loan_start_date = serializers.DateField()
    first_payment_date = serializers.DateField(allow_null=True)
    schedule_version = serializers.IntegerField()
    loan_schedule = MarketplaceLoanScheduleRowSerializer(many=True, required=False)
    originator_schedule = MarketplaceOriginatorScheduleRowSerializer(many=True, required=False)
    originator_payment_history = MarketplaceOriginatorPaymentRowSerializer(
        many=True, required=False
    )
    schedule_revision = serializers.IntegerField(allow_null=True, required=False)
    pricing_as_of_date = serializers.DateField(allow_null=True, required=False)


class MarketplaceBorrowerDocumentDownloadSerializer(serializers.Serializer[Any]):
    document_id = serializers.UUIDField()
    display_name = serializers.CharField()
    filename = serializers.CharField()
    content_type = serializers.CharField()
    content_encoding = serializers.CharField()
    content = serializers.CharField()
    content_sha256 = serializers.CharField()


class PrimaryInvestmentOrderSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    investor_user_id = serializers.UUIDField()
    status = serializers.CharField()
    requested_amount_minor = serializers.IntegerField()
    allocated_amount_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    document_acceptance_id = serializers.UUIDField(allow_null=True)
    reservation_journal_entry_id = serializers.UUIDField(allow_null=True)
    release_journal_entry_id = serializers.UUIDField(allow_null=True)
    lot_allocations = serializers.JSONField()
    created_by_user_id = serializers.UUIDField()
    allocated_at = serializers.DateTimeField(allow_null=True)
    released_at = serializers.DateTimeField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)
    closed_by_admin_id = serializers.UUIDField(allow_null=True)
    closed_reason = serializers.SerializerMethodField()
    notes = serializers.CharField()
    admin_notes = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @extend_schema_field(serializers.CharField())
    def get_closed_reason(self, order: Any) -> str:
        """Why the order closed without an investment (empty for other states)."""
        metadata = getattr(order, "metadata", None)
        if not isinstance(metadata, dict):
            return ""
        return str(metadata.get("closed_reason") or "")


class PrimaryInvestmentOrderCreateRequestSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.CharField(max_length=160)
    notes = serializers.CharField(required=False, allow_blank=True)


class PrimaryInvestmentOrderAllocateRequestSerializer(serializers.Serializer[Any]):
    document_acceptance_id = serializers.UUIDField()
    idempotency_key = serializers.CharField(max_length=160)
    sensitive_action_code_id = serializers.UUIDField()
    sensitive_action_code = serializers.CharField(max_length=32, trim_whitespace=True)
    pin = sensitive_action_pin_field()


class PrimaryOrderBatchItemSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=1)
    quote_id = serializers.UUIDField(required=False, allow_null=True)


class PrimaryOrderBatchRequestSerializer(serializers.Serializer[Any]):
    items = PrimaryOrderBatchItemSerializer(many=True, allow_empty=False)
    document_acceptance_id = serializers.UUIDField()
    idempotency_key = serializers.CharField(max_length=128)
    sensitive_action_code_id = serializers.UUIDField()
    sensitive_action_code = serializers.CharField(max_length=32, trim_whitespace=True)
    pin = sensitive_action_pin_field()


class PrimaryOrderBatchOriginatorPurchaseResponseSerializer(serializers.Serializer[Any]):
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


class PrimaryOrderBatchResponseSerializer(serializers.Serializer[Any]):
    batch_id = serializers.UUIDField()
    currency = serializers.CharField(allow_null=True)
    currency_totals = serializers.ListField(child=serializers.DictField())
    orders = PrimaryInvestmentOrderSerializer(many=True)
    order_count = serializers.IntegerField()
    originator_purchases = PrimaryOrderBatchOriginatorPurchaseResponseSerializer(many=True)
    originator_purchase_count = serializers.IntegerField()
    total_amount_minor = serializers.IntegerField(allow_null=True)


class PrimaryInvestmentOrderReleaseRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    idempotency_key = serializers.CharField(max_length=160)


class PrimaryLoanCloseSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    close_type = serializers.CharField()
    accepted_principal_minor = serializers.IntegerField()
    currency = serializers.CharField(source="currency.code")
    allocated_order_count = serializers.IntegerField()
    closed_not_invested_order_count = serializers.IntegerField()
    borrower_success_fee_bps = serializers.IntegerField()
    borrower_success_fee_minor = serializers.IntegerField()
    borrower_disbursement_payable_minor = serializers.IntegerField()
    funding_close_journal_entry_id = serializers.UUIDField()
    created_by_admin_id = serializers.UUIDField()
    closed_at = serializers.DateTimeField()
    reason = serializers.CharField()
    investor_message = serializers.CharField()
    created_at = serializers.DateTimeField()


class PrimaryLoanCloseRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    investor_message = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class PrimaryLoanCancellationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    currency = serializers.CharField(source="currency.code")
    released_order_count = serializers.IntegerField()
    closed_not_invested_order_count = serializers.IntegerField()
    released_principal_minor = serializers.IntegerField()
    created_by_admin_id = serializers.UUIDField()
    cancelled_at = serializers.DateTimeField()
    reason = serializers.CharField()
    investor_message = serializers.CharField()
    created_at = serializers.DateTimeField()


class PrimaryLoanCancellationRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()
    investor_message = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160)


class PrimaryLoanExpiryScanRequestSerializer(serializers.Serializer[Any]):
    as_of_date = serializers.DateField(required=False)
    loan_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    investor_message = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=160, required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=250)


class PrimaryLoanExpiryScanResponseSerializer(serializers.Serializer[Any]):
    as_of_date = serializers.DateField()
    scanned_count = serializers.IntegerField()
    cancelled_count = serializers.IntegerField()
    closed_count = serializers.IntegerField(required=False, default=0)
    closes = PrimaryLoanCloseSerializer(many=True, required=False)
    failed_count = serializers.IntegerField(required=False, default=0)
    failures = serializers.ListField(child=serializers.DictField(), required=False)
    skipped_count = serializers.IntegerField()
    cancellations = PrimaryLoanCancellationSerializer(many=True)
    skipped = serializers.ListField(child=serializers.DictField())


class PublicMarketplaceLoanListQuerySerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


def serialize_primary_order(order: PrimaryInvestmentOrder) -> dict[str, Any]:
    return dict(PrimaryInvestmentOrderSerializer(order).data)


def serialize_primary_loan_close(close: PrimaryLoanClose) -> dict[str, Any]:
    return dict(PrimaryLoanCloseSerializer(close).data)


def serialize_primary_loan_cancellation(
    cancellation: PrimaryLoanCancellation,
) -> dict[str, Any]:
    return dict(PrimaryLoanCancellationSerializer(cancellation).data)


def serialize_primary_expiry_scan_result(result: dict[str, Any]) -> dict[str, Any]:
    as_of_date = result["as_of_date"]
    return {
        **result,
        "as_of_date": as_of_date.isoformat() if hasattr(as_of_date, "isoformat") else as_of_date,
        "closes": [serialize_primary_loan_close(close) for close in result.get("closes", [])],
        "cancellations": [
            serialize_primary_loan_cancellation(cancellation)
            for cancellation in result["cancellations"]
        ],
    }
