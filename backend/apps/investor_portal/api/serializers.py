from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.investor_portal.services import NOTIFICATION_CATEGORIES, NOTIFICATION_TARGET_TYPES


class PortalLimitQuerySerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=50)


class PortfolioQuerySerializer(serializers.Serializer[Any]):
    include_inactive = serializers.BooleanField(required=False, default=False)


class BalanceSummarySerializer(serializers.Serializer[Any]):
    investor_user_id = serializers.UUIDField()
    currency = serializers.CharField()
    total_available_minor = serializers.IntegerField()
    investable_minor = serializers.IntegerField(
        help_text=(
            "Potentially investable balance; each loan's remaining funding window "
            "is checked separately."
        )
    )
    withdraw_only_minor = serializers.IntegerField(
        help_text="Balance on its last day (day 56): it can only be withdrawn."
    )
    overdue_minor = serializers.IntegerField(
        help_text=(
            "Balance due back to the investor's bank (from the day after the last day) that "
            "is not returned yet, usually because no verified payout IBAN is known."
        )
    )
    frozen_minor = serializers.IntegerField()
    penalty_mode_minor = serializers.IntegerField(
        help_text="Remaining balance of lots in penalty mode: blocked until withdrawn."
    )
    penalty_charged_minor = serializers.IntegerField(
        help_text=(
            "Balance-ageing penalties charged so far on this currency's lots; already deducted "
            "and not included in any balance figure."
        )
    )
    lot_count = serializers.IntegerField()
    active_lot_count = serializers.IntegerField()
    next_investment_deadline_at = serializers.DateTimeField(
        allow_null=True, help_text="Compatibility alias of the next source holding deadline."
    )
    next_withdrawal_deadline_at = serializers.DateTimeField(allow_null=True)
    next_return_date = serializers.DateField(
        allow_null=True,
        help_text=(
            "Next Europe/Zurich date on which money of this currency that is still not "
            "invested goes back to the investor's bank (money already due back is in "
            "overdue_minor)."
        ),
    )


class BalanceLotSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    # 18.3: the part of this lot reserved for primary investments waiting for the closing.
    reserved_amount_minor = serializers.IntegerField(default=0)
    currency = serializers.CharField()
    source_type = serializers.CharField()
    status = serializers.CharField()
    bucket = serializers.CharField()
    received_at = serializers.DateTimeField()
    investment_deadline_at = serializers.DateTimeField(
        help_text="Compatibility alias of withdrawal_deadline_at, not a fixed source-age cutoff."
    )
    withdrawal_deadline_at = serializers.DateTimeField(
        help_text="60-day legal holding limit (day 60 after the value date)."
    )
    days_until_investment_deadline = serializers.IntegerField()
    days_until_withdrawal_deadline = serializers.IntegerField()
    return_after_days = serializers.IntegerField(
        help_text="Q01: the holding day this money may stay until (56; 58 for older money)."
    )
    last_day = serializers.DateField(
        help_text=(
            "Last Europe/Zurich day the money may stay (day 56 after the value date, earlier "
            "when the return date moves). On that day it can only be withdrawn."
        )
    )
    return_date = serializers.DateField(
        help_text=(
            "Day the platform starts the return of money still not invested to the "
            "investor's verified bank account: day 57, moved to an earlier settlement day "
            "when the calendar or the bank's processing time needs it."
        )
    )
    return_date_adjusted = serializers.BooleanField(
        help_text="True when the return date moved earlier than day 57."
    )
    days_until_last_day = serializers.IntegerField(
        help_text="Days until last_day: 0 on the last day, negative once the money is due back."
    )
    direct_funding_until = serializers.DateField(
        allow_null=True,
        help_text=(
            "F01: the latest last subscription date of a direct loan this money can fund "
            "(close + payout margin on or before day 56); null when none fits."
        ),
    )
    return_failed = serializers.BooleanField(
        help_text="Q02: this money came back from a failed return and waits for the team."
    )
    original_amount_minor = serializers.IntegerField()
    available_amount_minor = serializers.IntegerField()
    invested_amount_minor = serializers.IntegerField()
    converted_amount_minor = serializers.IntegerField()
    withdrawn_amount_minor = serializers.IntegerField()
    penalized_amount_minor = serializers.IntegerField(
        help_text="Balance-ageing penalty charged on this lot so far."
    )
    requires_withdrawal = serializers.BooleanField()
    blocks_financial_actions = serializers.BooleanField()


class PayoutInstructionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    currency = serializers.CharField()
    status = serializers.CharField()
    destination_iban = serializers.CharField()
    destination_account_name = serializers.CharField()
    # 18.3: from the SIX bank master for CH and LI IBANs, else as typed by the investor; may be "".
    bank_name = serializers.CharField(allow_blank=True, required=False, default="")
    is_verified_usable = serializers.BooleanField()
    verification_status = serializers.ChoiceField(
        choices=[("verified", "Verified"), ("pending", "Pending verification")],
        help_text="U33-DEC-05: a pending account cannot be used until the team verifies it.",
    )
    is_default_return = serializers.BooleanField(
        help_text=(
            "U33-DEC-05: the account money going back to the investor's bank is sent to; "
            "one per currency, always a verified account."
        ),
    )
    verified_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class PendingWithdrawalSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    destination_iban = serializers.CharField()
    destination_account_name = serializers.CharField(allow_blank=True)
    requested_at = serializers.DateTimeField()
    is_forced = serializers.BooleanField(
        help_text=(
            "Automatic return of money not invested in time (day 57), not asked by the "
            "investor."
        )
    )


class ReturnFailurePortalSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    is_forced = serializers.BooleanField()
    reason_code = serializers.CharField()
    reason_text = serializers.CharField(help_text="The bank's reason, for the investor.")
    destination_iban = serializers.CharField()
    returned_value_date = serializers.DateField()
    recorded_at = serializers.DateTimeField()


class InvestorBalancePortalSerializer(serializers.Serializer[Any]):
    as_of = serializers.DateTimeField()
    summaries = BalanceSummarySerializer(many=True)
    lots = BalanceLotSerializer(many=True)
    payout_instructions = PayoutInstructionSerializer(many=True)
    pending_withdrawals = PendingWithdrawalSerializer(
        many=True, help_text="Withdrawal requests waiting for the bank transfer, oldest first."
    )
    auto_return_after_days = serializers.IntegerField(
        help_text=(
            "New money may stay until this holding day (56); the return is requested the "
            "next day or earlier. The legal limit is 60."
        )
    )
    return_failures = ReturnFailurePortalSerializer(
        many=True, help_text="Q02: failed returns waiting for the team, oldest first."
    )


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
    template_title = serializers.CharField(required=False)
    document_type = serializers.CharField()
    category = serializers.CharField(required=False)
    version = serializers.CharField()
    date = serializers.DateTimeField()
    context_label = serializers.CharField()
    context_type = serializers.CharField(required=False)
    context_id = serializers.CharField(required=False)
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


class InvestorReportSerializer(serializers.Serializer[Any]):
    """18.3: a report kept as issued (created by the investor or a monthly statement)."""

    id = serializers.UUIDField()
    kind = serializers.ChoiceField(
        choices=[
            "account_statement",
            "portfolio",
            "interest_repayments",
            "tax",
            "monthly_statement",
        ]
    )
    title = serializers.CharField()
    # Empty: EUR and CHF, reported separately.
    currency = serializers.CharField(allow_blank=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    output_format = serializers.CharField()
    filename = serializers.CharField()
    issued_at = serializers.DateTimeField()
    automatic = serializers.BooleanField()


class InvestorReportsSerializer(serializers.Serializer[Any]):
    reports = InvestorReportSerializer(many=True)


class InvestorReportCreateRequestSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(
        choices=["account_statement", "portfolio", "interest_repayments", "tax"]
    )
    # The portfolio report is always as of today; the dates are then ignored.
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    currency = serializers.ChoiceField(choices=["", "EUR", "CHF"], required=False, default="")
    output_format = serializers.ChoiceField(choices=["pdf", "csv"], required=False, default="pdf")


class InvestorReportSummaryQuerySerializer(serializers.Serializer[Any]):
    # A calendar year, or "all" for every year.
    year = serializers.CharField(required=False, default="all", max_length=4)


class InvestorReportCurrencySummarySerializer(serializers.Serializer[Any]):
    currency = serializers.CharField()
    invested_minor = serializers.IntegerField()
    principal_repaid_minor = serializers.IntegerField()
    interest_received_minor = serializers.IntegerField()


class InvestorReportSummarySerializer(serializers.Serializer[Any]):
    year = serializers.IntegerField(allow_null=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    currencies = InvestorReportCurrencySummarySerializer(many=True)


class InvestorNotificationSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    notification_source = serializers.CharField()
    topic = serializers.CharField()
    topic_label = serializers.CharField(
        help_text="Short human label of the notice type, e.g. Deposit or Withdrawal."
    )
    status = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    created_at = serializers.DateTimeField()
    sent_at = serializers.DateTimeField(allow_null=True)
    unread = serializers.BooleanField()
    navigation_target = serializers.ChoiceField(
        choices=list(NOTIFICATION_TARGET_TYPES),
        help_text="Portal page the notification opens; none opens the Notifications page.",
    )
    navigation_target_id = serializers.CharField(
        allow_blank=True,
        help_text="Loan or holding UUID for the loan and holding targets; blank otherwise.",
    )
    # 18.3: the design's tone (positive, late, default, neutral).
    category = serializers.ChoiceField(
        choices=list(NOTIFICATION_CATEGORIES), required=False, default="neutral"
    )


class InvestorNotificationsSerializer(serializers.Serializer[Any]):
    notifications = InvestorNotificationSerializer(many=True)
    unread_count = serializers.IntegerField()


class InvestorNotificationReadResponseSerializer(serializers.Serializer[Any]):
    marked_count = serializers.IntegerField(
        help_text="Notifications newly marked as read by this request (0 when already read)."
    )
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


class PortfolioInstallmentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    schedule_version = serializers.IntegerField()
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField(required=False, default=0)
    fee_minor = serializers.IntegerField(required=False, default=0)
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
    accrual_start_date = serializers.DateField(required=False)
    opening_principal_minor = serializers.IntegerField(required=False)
    closing_principal_minor = serializers.IntegerField(required=False)
    payment_reference = serializers.CharField(required=False, allow_blank=True)


class HoldingReceivedPaymentSerializer(serializers.Serializer[Any]):
    """18.3: the investor's share of one payment already received (credited to the balance)."""

    # The borrower installment (direct loans); null for a Loan Originator claim payment.
    installment_number = serializers.IntegerField(allow_null=True)
    due_date = serializers.DateField(allow_null=True)
    paid_on = serializers.DateField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField()
    fee_minor = serializers.IntegerField()
    # Principal + interest + penalty of the investor's share.
    total_minor = serializers.IntegerField()
    # What was credited to the Banxum balance (the total less any fee).
    credited_minor = serializers.IntegerField()
    principal_after_minor = serializers.IntegerField()


class PortfolioHoldingInstallmentSerializer(serializers.Serializer[Any]):
    loan_installment_id = serializers.UUIDField()
    schedule_version = serializers.IntegerField()
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    projected_principal_minor = serializers.IntegerField()
    projected_interest_minor = serializers.IntegerField()
    projected_penalty_minor = serializers.IntegerField(required=False, default=0)
    projected_fee_minor = serializers.IntegerField(required=False, default=0)
    projected_total_minor = serializers.IntegerField()
    days_past_due = serializers.IntegerField()
    status = serializers.CharField()
    accrual_start_date = serializers.DateField(required=False)


class PortfolioExposureSerializer(serializers.Serializer[Any]):
    by_borrower = ExposureBucketSerializer(many=True)
    by_country = ExposureBucketSerializer(many=True)
    by_purpose = ExposureBucketSerializer(many=True)
    by_collateral_type = ExposureBucketSerializer(many=True)
    by_maturity = ExposureBucketSerializer(many=True)
    by_loan_status = ExposureBucketSerializer(many=True)


class PortfolioLoanSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    # Q04: a Garanta account has a confirmed reservation or holds a participation (no amount).
    banxum_invests = serializers.BooleanField(required=False, default=False)
    product_type = serializers.CharField()
    loan_title = serializers.CharField()
    loan_status = serializers.CharField()
    borrower_id = serializers.UUIDField(allow_null=True)
    borrower_name = serializers.CharField()
    borrower_country = serializers.CharField(allow_blank=True)
    originator_id = serializers.UUIDField(allow_null=True)
    originator_name = serializers.CharField(allow_blank=True)
    purpose = serializers.CharField()
    collateral_type = serializers.CharField()
    collateral_value_minor = serializers.IntegerField()
    collateral_description = serializers.CharField(allow_blank=True)
    skin_in_the_game_bps = serializers.IntegerField()
    interest_rate_bps = serializers.IntegerField()
    yield_bps = serializers.IntegerField()
    underlying_interest_rate_bps = serializers.IntegerField()
    default_penalty_interest_bps = serializers.IntegerField()
    term_months = serializers.IntegerField()
    remaining_term_days = serializers.IntegerField(required=False)
    maturity_date = serializers.DateField(required=False)
    repayment_type = serializers.CharField()
    currency = serializers.CharField()
    is_refinancing = serializers.BooleanField()
    original_principal_minor = serializers.IntegerField()
    original_repayment_type = serializers.CharField(allow_null=True)
    original_interest_only_months = serializers.IntegerField(allow_null=True)
    principal_minor = serializers.IntegerField()
    funding_deadline = serializers.DateField(allow_null=True)
    loan_start_date = serializers.DateField()
    first_payment_date = serializers.DateField(allow_null=True)
    ltv_bps = serializers.IntegerField(allow_null=True)
    days_past_due = serializers.IntegerField()
    # U33-DEC-09: the contract termination date recorded by Banxum (null when not terminated).
    contract_terminated_on = serializers.DateField(allow_null=True, required=False)
    schedule_version = serializers.IntegerField()
    schedule = PortfolioInstallmentSerializer(many=True)


class HoldingRecoveryStageSerializer(serializers.Serializer[Any]):
    """U33-DEC-22: a real stage of the loan's follow-up, recorded by the team."""

    title = serializers.CharField()
    # Q16: with "Recovery closed": full, partial or none (empty otherwise).
    recovery_result = serializers.CharField(allow_blank=True, required=False, default="")
    occurred_on = serializers.DateField(
        allow_null=True, help_text="The real date; for the next step, null when not known."
    )
    investor_note = serializers.CharField(allow_blank=True)


class HoldingRecoveryEventSerializer(serializers.Serializer[Any]):
    """U33-DEC-12: one recovery of the loan (whole-loan amounts) and the investor's share."""

    recovery_event_id = serializers.UUIDField()
    value_date = serializers.DateField()
    gross_recovered_minor = serializers.IntegerField()
    external_costs_minor = serializers.IntegerField()
    # A Banxum recovery fee recorded before U33-DEC-12; 0 for every later recovery.
    recovery_fee_minor = serializers.IntegerField()
    net_distributed_minor = serializers.IntegerField()
    credited_to_you_minor = serializers.IntegerField()


class LatestPublicNoteSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    note_type = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    occurred_at = serializers.DateTimeField()


class HoldingOpenSecondaryListingSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    status = serializers.CharField()
    publication_type = serializers.CharField()
    price_bps = serializers.IntegerField()
    transfer_price_minor = serializers.IntegerField()
    seller_net_proceeds_minor = serializers.IntegerField()
    listed_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField()
    # C03: shown as "Pending" while an installment of the loan is due and unpaid.
    paused_for_due_installment = serializers.BooleanField()


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
    received_penalty_minor = serializers.IntegerField()
    repayment_fee_minor = serializers.IntegerField()
    received_payments = HoldingReceivedPaymentSerializer(many=True, required=False)
    investment_schedule = PortfolioHoldingInstallmentSerializer(many=True)
    acquisition_cash_consideration_minor = serializers.IntegerField(allow_null=True)
    acquisition_cash_flow = serializers.ListField(
        child=serializers.DictField(),
    )
    recovered_principal_minor = serializers.IntegerField()
    recovered_contractual_interest_minor = serializers.IntegerField()
    recovered_default_interest_minor = serializers.IntegerField()
    recovered_penalties_minor = serializers.IntegerField()
    recovered_other_costs_minor = serializers.IntegerField()
    recovery_events = HoldingRecoveryEventSerializer(many=True, required=False)
    recovery_stages = HoldingRecoveryStageSerializer(many=True, required=False)
    recovery_next_step = HoldingRecoveryStageSerializer(allow_null=True, required=False)
    latest_public_note = LatestPublicNoteSerializer(allow_null=True, required=False)
    open_secondary_listing = HoldingOpenSecondaryListingSerializer(allow_null=True)


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
    archived_at = serializers.DateTimeField(required=False)
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


class TransactionQuerySerializer(serializers.Serializer[Any]):
    """18.3: server filters of the Transactions page (dates are Europe/Zurich days)."""

    currency = serializers.CharField(required=False, allow_blank=True, default="", max_length=3)
    group = serializers.ChoiceField(
        choices=[
            "",
            "deposit",
            "reservation",
            "investment",
            "repayment",
            "recovery",
            "withdrawal",
            "return",
            "purchase",
            "sale",
            "fee",
            "fx",
            "other",
        ],
        required=False,
        default="",
    )
    date_from = serializers.DateField(required=False, allow_null=True, default=None)
    date_to = serializers.DateField(required=False, allow_null=True, default=None)
    q = serializers.CharField(required=False, allow_blank=True, default="", max_length=120)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=25)


class TransactionEntrySerializer(ActivityEntrySerializer):
    # The filter group the page shows.
    group = serializers.CharField()
    # The investor's available balance in this currency right after the movement.
    available_after_minor = serializers.IntegerField(allow_null=True)


class TransactionSummarySerializer(serializers.Serializer[Any]):
    currency = serializers.CharField()
    deposited_minor = serializers.IntegerField()
    invested_minor = serializers.IntegerField()
    credited_minor = serializers.IntegerField()
    withdrawn_minor = serializers.IntegerField()


class TransactionPageSerializer(serializers.Serializer[Any]):
    entries = TransactionEntrySerializer(many=True)
    # Movements that match the filters (all pages).
    total = serializers.IntegerField()
    offset = serializers.IntegerField()
    next_offset = serializers.IntegerField(allow_null=True)
    # Currencies, groups and years the investor has movements in (for the filters).
    currencies = serializers.ListField(child=serializers.CharField())
    groups = serializers.ListField(child=serializers.CharField())
    years = serializers.ListField(child=serializers.IntegerField())
    # Totals of all movements that match the filters, per currency.
    summary = TransactionSummarySerializer(many=True)


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
    # C03: an open listing of a loan with a due, unpaid installment is "Pending".
    paused_for_due_installment = serializers.BooleanField()
    risk_acknowledgement_required = serializers.BooleanField()
    public_disclosure_note = serializers.CharField(allow_blank=True)
    listed_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    # 18.3: "listed", "sold" or "cancelled" (a listing removed or refused by Banxum is cancelled).
    state = serializers.ChoiceField(choices=["listed", "sold", "cancelled"])
    closed_at = serializers.DateTimeField(allow_null=True)


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


class SecondaryMarketActivityEntryPortalSerializer(serializers.Serializer[Any]):
    archived_at = serializers.DateTimeField(required=False)
    id = serializers.CharField()
    action = serializers.CharField()
    event_type = serializers.CharField()
    listing_id = serializers.UUIDField()
    holding_id = serializers.UUIDField(allow_null=True)
    loan_id = serializers.UUIDField()
    loan_title = serializers.CharField()
    currency = serializers.CharField()
    principal_minor = serializers.IntegerField()
    cash_amount_minor = serializers.IntegerField()
    price_bps = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    occurred_at = serializers.DateTimeField()


class SecondaryMarketActivityPortalSerializer(serializers.Serializer[Any]):
    listings = SecondaryListingPortalSerializer(many=True)
    purchases_as_buyer = SecondaryPurchaseAsBuyerPortalSerializer(many=True)
    sales_as_seller = SecondarySaleAsSellerPortalSerializer(many=True)
    entries = SecondaryMarketActivityEntryPortalSerializer(many=True)


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
    archived_at = serializers.DateTimeField(required=False)
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
    effective_net_rate = serializers.CharField()
    status = serializers.CharField()
    executed_at = serializers.DateTimeField()


class FxTermsPortalSerializer(serializers.Serializer[Any]):
    daily_limit_chf_minor = serializers.IntegerField(
        help_text="Daily FX limit per investor, as a CHF equivalent in minor units."
    )
    daily_limit_used_chf_minor = serializers.IntegerField(
        help_text="CHF equivalent already converted on the current Europe/Zurich business day."
    )
    quote_ttl_seconds = serializers.IntegerField(
        help_text="How long an executable quote stays valid after it is issued."
    )
    platform_fee_bps = serializers.IntegerField()


class FxHistoryPortalSerializer(serializers.Serializer[Any]):
    quotes = FxQuotePortalSerializer(many=True)
    exchanges = FxExchangePortalSerializer(many=True)
    terms = FxTermsPortalSerializer()


class InvestorPortalFeaturesSerializer(serializers.Serializer[Any]):
    """Platform switches the investor app reads before it shows a feature."""

    fx_enabled = serializers.BooleanField()


class InvestorSupportRequestCreateSerializer(serializers.Serializer[Any]):
    """U33-DEC-35 Help message (`help`) or U33-DEC-28 account closure request."""

    kind = serializers.ChoiceField(choices=["help", "account_closure"])
    idempotency_key = serializers.CharField(max_length=160)
    topic = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    message = serializers.CharField(
        max_length=4000, required=False, allow_blank=True, default="", trim_whitespace=False
    )
    context_type = serializers.ChoiceField(
        choices=["", "holding"], required=False, allow_blank=True, default=""
    )
    context_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class InvestorSupportRequestReceiptSerializer(serializers.Serializer[Any]):
    reference = serializers.CharField()
    kind = serializers.CharField()
    received_at = serializers.DateTimeField()
    context_label = serializers.CharField(allow_blank=True)
    receipt_email = serializers.EmailField()
