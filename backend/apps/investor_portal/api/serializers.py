from __future__ import annotations

from typing import Any

from rest_framework import serializers


class PortalLimitQuerySerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=50)


class PortfolioQuerySerializer(serializers.Serializer[Any]):
    include_inactive = serializers.BooleanField(required=False, default=False)


class BalanceSummarySerializer(serializers.Serializer[Any]):
    investor_user_id = serializers.UUIDField()
    currency = serializers.CharField()
    total_available_minor = serializers.IntegerField()
    investable_minor = serializers.IntegerField()
    withdraw_only_minor = serializers.IntegerField()
    overdue_minor = serializers.IntegerField()
    frozen_minor = serializers.IntegerField()
    penalty_mode_minor = serializers.IntegerField()
    lot_count = serializers.IntegerField()
    active_lot_count = serializers.IntegerField()
    next_investment_deadline_at = serializers.DateTimeField(allow_null=True)
    next_withdrawal_deadline_at = serializers.DateTimeField(allow_null=True)


class BalanceLotSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    currency = serializers.CharField()
    source_type = serializers.CharField()
    status = serializers.CharField()
    bucket = serializers.CharField()
    received_at = serializers.DateTimeField()
    investment_deadline_at = serializers.DateTimeField()
    withdrawal_deadline_at = serializers.DateTimeField()
    days_until_investment_deadline = serializers.IntegerField()
    days_until_withdrawal_deadline = serializers.IntegerField()
    original_amount_minor = serializers.IntegerField()
    available_amount_minor = serializers.IntegerField()
    invested_amount_minor = serializers.IntegerField()
    converted_amount_minor = serializers.IntegerField()
    withdrawn_amount_minor = serializers.IntegerField()
    penalized_amount_minor = serializers.IntegerField()
    requires_withdrawal = serializers.BooleanField()
    blocks_financial_actions = serializers.BooleanField()


class PayoutInstructionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    currency = serializers.CharField()
    status = serializers.CharField()
    destination_iban = serializers.CharField()
    destination_account_name = serializers.CharField()
    is_verified_usable = serializers.BooleanField()
    verified_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class InvestorBalancePortalSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField()
    summaries = BalanceSummarySerializer(many=True)
    lots = BalanceLotSerializer(many=True)
    payout_instructions = PayoutInstructionSerializer(many=True)
    has_penalty_mode_balance = serializers.BooleanField()


class DepositInstructionSerializer(serializers.Serializer[Any]):
    currency = serializers.CharField()
    account_holder_name = serializers.CharField(allow_blank=True)
    iban = serializers.CharField(allow_blank=True)
    qr_iban = serializers.CharField(allow_blank=True, required=False)
    bic = serializers.CharField(allow_blank=True)
    bank_name = serializers.CharField(allow_blank=True)
    collection_account_identifier = serializers.CharField()
    qr_bill_payload = serializers.CharField(allow_blank=True, required=False)
    payment_reference = serializers.CharField()
    notes = serializers.CharField(allow_blank=True)
    is_configured = serializers.BooleanField()


class InvestorDepositInstructionsSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField()
    instructions = DepositInstructionSerializer(many=True)
    reference_rule = serializers.CharField()


class InvestorDocumentSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    document_kind = serializers.CharField()
    title = serializers.CharField()
    document_type = serializers.CharField()
    version = serializers.CharField()
    date = serializers.DateTimeField()
    context_label = serializers.CharField()
    output_formats = serializers.ListField(child=serializers.CharField())
    generated_on_request = serializers.BooleanField()
    content_hash = serializers.CharField(required=False)
    period_start = serializers.DateField(required=False)
    period_end = serializers.DateField(required=False)


class InvestorDocumentsSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField()
    documents = InvestorDocumentSerializer(many=True)
    disclaimer = serializers.CharField()


class InvestorDocumentDownloadRequestSerializer(serializers.Serializer[Any]):
    document_kind = serializers.ChoiceField(
        choices=["acceptance_evidence", "account_statement", "annual_tax_information"]
    )
    document_id = serializers.CharField(required=False, allow_blank=True)
    output_format = serializers.ChoiceField(
        choices=["pdf", "csv", "zip"],
        required=False,
        default="pdf",
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)


class InvestorDocumentDownloadResponseSerializer(serializers.Serializer[Any]):
    content_type = serializers.CharField()
    filename = serializers.CharField()
    content_encoding = serializers.CharField()
    content = serializers.CharField()
    content_sha256 = serializers.CharField()
    manifest = serializers.JSONField()


class InvestorNotificationSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    notification_source = serializers.CharField()
    topic = serializers.CharField()
    status = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    created_at = serializers.DateTimeField()
    sent_at = serializers.DateTimeField(allow_null=True)
    unread = serializers.BooleanField()
    metadata = serializers.JSONField()


class InvestorNotificationsSerializer(serializers.Serializer[Any]):
    notifications = InvestorNotificationSerializer(many=True)
    unread_count = serializers.IntegerField()


class AmountByCurrencySerializer(serializers.Serializer[Any]):
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()


class ExposureBucketSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    name = serializers.CharField()
    currency = serializers.CharField()
    outstanding_principal_minor = serializers.IntegerField()
    holding_count = serializers.IntegerField()


class PortfolioSummarySerializer(serializers.Serializer[Any]):
    holding_count = serializers.IntegerField()
    active_holding_count = serializers.IntegerField()
    outstanding_principal_by_currency = AmountByCurrencySerializer(many=True)
    original_principal_by_currency = AmountByCurrencySerializer(many=True)
    realized_interest_by_currency = AmountByCurrencySerializer(many=True)
    late_or_defaulted_exposure_by_currency = AmountByCurrencySerializer(many=True)


class PortfolioExposureSerializer(serializers.Serializer[Any]):
    by_borrower = ExposureBucketSerializer(many=True)
    by_country = ExposureBucketSerializer(many=True)
    by_purpose = ExposureBucketSerializer(many=True)
    by_risk_rating = ExposureBucketSerializer(many=True)
    by_collateral_type = ExposureBucketSerializer(many=True)
    by_maturity = ExposureBucketSerializer(many=True)
    by_loan_status = ExposureBucketSerializer(many=True)


class PortfolioLoanSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    loan_title = serializers.CharField()
    loan_status = serializers.CharField()
    borrower_id = serializers.UUIDField()
    borrower_name = serializers.CharField()
    borrower_country = serializers.CharField(allow_blank=True)
    purpose = serializers.CharField()
    collateral_type = serializers.CharField()
    risk_rating = serializers.CharField()
    interest_rate_bps = serializers.IntegerField()
    term_months = serializers.IntegerField()
    repayment_type = serializers.CharField()
    currency = serializers.CharField()
    principal_minor = serializers.IntegerField()
    funding_deadline = serializers.DateField()
    first_payment_date = serializers.DateField()
    ltv_bps = serializers.IntegerField(allow_null=True)
    days_past_due = serializers.IntegerField()


class LatestPublicNoteSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    note_type = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    occurred_at = serializers.DateTimeField()


class HoldingSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    status = serializers.CharField()
    source_type = serializers.CharField()
    original_principal_minor = serializers.IntegerField()
    current_principal_minor = serializers.IntegerField()
    currency = serializers.CharField()
    loan_share_ppm = serializers.IntegerField()
    assignment_effective_at = serializers.DateTimeField()
    loan = PortfolioLoanSerializer()
    received_principal_minor = serializers.IntegerField()
    received_interest_minor = serializers.IntegerField()
    repayment_fee_minor = serializers.IntegerField()
    recovered_principal_minor = serializers.IntegerField()
    recovered_contractual_interest_minor = serializers.IntegerField()
    recovered_default_interest_minor = serializers.IntegerField()
    recovered_penalties_minor = serializers.IntegerField()
    recovered_other_costs_minor = serializers.IntegerField()
    latest_public_note = LatestPublicNoteSerializer(allow_null=True, required=False)


class InvestorPortfolioSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField()
    summary = PortfolioSummarySerializer()
    holdings = HoldingSerializer(many=True)
    exposure = PortfolioExposureSerializer()


class PendingActionSerializer(serializers.Serializer[Any]):
    type = serializers.CharField()
    severity = serializers.CharField()
    currency = serializers.CharField(required=False, allow_blank=True)
    amount_minor = serializers.IntegerField(required=False)
    count = serializers.IntegerField(required=False)
    message = serializers.CharField()


class ActivityEntrySerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    activity_type = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    direction = serializers.CharField()
    title = serializers.CharField()
    amount_minor = serializers.IntegerField(allow_null=True)
    currency = serializers.CharField(allow_blank=True)
    status = serializers.CharField(allow_blank=True)
    loan_id = serializers.UUIDField(allow_null=True, required=False)
    loan_title = serializers.CharField(allow_blank=True)
    metadata = serializers.JSONField()


class InvestorActivitySerializer(serializers.Serializer[Any]):
    entries = ActivityEntrySerializer(many=True)


class InvestorDashboardSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField()
    investor_user_id = serializers.UUIDField()
    balances = BalanceSummarySerializer(many=True)
    portfolio_summary = PortfolioSummarySerializer()
    exposure = PortfolioExposureSerializer()
    pending_actions = PendingActionSerializer(many=True)
    recent_activity = ActivityEntrySerializer(many=True)


class PrimaryOrderPortalSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    loan_title = serializers.CharField()
    loan_status = serializers.CharField()
    status = serializers.CharField()
    requested_amount_minor = serializers.IntegerField()
    allocated_amount_minor = serializers.IntegerField()
    currency = serializers.CharField()
    created_at = serializers.DateTimeField()
    allocated_at = serializers.DateTimeField(allow_null=True)
    released_at = serializers.DateTimeField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)


class PrimaryOrdersPortalSerializer(serializers.Serializer[Any]):
    orders = PrimaryOrderPortalSerializer(many=True)


class SecondaryListingPortalSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    holding_id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    loan_title = serializers.CharField()
    status = serializers.CharField()
    publication_type = serializers.CharField()
    current_principal_minor = serializers.IntegerField()
    transfer_price_minor = serializers.IntegerField()
    discount_premium_bps = serializers.IntegerField()
    accrued_interest_minor = serializers.IntegerField()
    maker_fee_minor = serializers.IntegerField()
    seller_net_proceeds_minor = serializers.IntegerField()
    currency = serializers.CharField()
    loan_status_at_listing = serializers.CharField()
    risk_acknowledgement_required = serializers.BooleanField()
    public_disclosure_note = serializers.CharField(allow_blank=True)
    listed_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class SecondaryPurchaseAsBuyerPortalSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    listing_id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    loan_title = serializers.CharField()
    buyer_holding_id = serializers.UUIDField()
    current_principal_minor = serializers.IntegerField()
    transfer_price_minor = serializers.IntegerField()
    discount_premium_bps = serializers.IntegerField()
    accrued_interest_minor = serializers.IntegerField()
    taker_fee_minor = serializers.IntegerField()
    buyer_total_cost_minor = serializers.IntegerField()
    currency = serializers.CharField()
    loan_status_at_purchase = serializers.CharField()
    risk_acknowledgement_accepted = serializers.BooleanField()
    purchased_at = serializers.DateTimeField()


class SecondarySaleAsSellerPortalSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    listing_id = serializers.UUIDField()
    loan_id = serializers.UUIDField()
    loan_title = serializers.CharField()
    seller_holding_id = serializers.UUIDField()
    current_principal_minor = serializers.IntegerField()
    transfer_price_minor = serializers.IntegerField()
    discount_premium_bps = serializers.IntegerField()
    accrued_interest_minor = serializers.IntegerField()
    maker_fee_minor = serializers.IntegerField()
    seller_net_proceeds_minor = serializers.IntegerField()
    currency = serializers.CharField()
    loan_status_at_purchase = serializers.CharField()
    purchased_at = serializers.DateTimeField()


class SecondaryMarketActivityPortalSerializer(serializers.Serializer[Any]):
    listings = SecondaryListingPortalSerializer(many=True)
    purchases_as_buyer = SecondaryPurchaseAsBuyerPortalSerializer(many=True)
    sales_as_seller = SecondarySaleAsSellerPortalSerializer(many=True)


class FxQuotePortalSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    source_currency = serializers.CharField()
    target_currency = serializers.CharField()
    source_amount_minor = serializers.IntegerField()
    rate = serializers.CharField()
    platform_fee_bps = serializers.IntegerField()
    gross_target_amount_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    target_amount_minor = serializers.IntegerField()
    issued_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    is_expired = serializers.BooleanField()
    has_exchange = serializers.BooleanField()


class FxExchangePortalSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    quote_id = serializers.UUIDField()
    source_currency = serializers.CharField()
    target_currency = serializers.CharField()
    source_amount_minor = serializers.IntegerField()
    rate = serializers.CharField()
    platform_fee_bps = serializers.IntegerField()
    gross_target_amount_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    target_amount_minor = serializers.IntegerField()
    status = serializers.CharField()
    executed_at = serializers.DateTimeField()


class FxHistoryPortalSerializer(serializers.Serializer[Any]):
    quotes = FxQuotePortalSerializer(many=True)
    exchanges = FxExchangePortalSerializer(many=True)
