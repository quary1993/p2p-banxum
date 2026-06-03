from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class SecondaryMarketListingStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    APPROVAL_REQUESTED = "approval_requested", "Approval requested"
    REJECTED = "rejected", "Rejected"
    REMOVED = "removed", "Removed"
    SOLD = "sold", "Sold"
    CANCELLED = "cancelled", "Cancelled"


class SecondaryMarketListingPublicationType(models.TextChoices):
    AUTOMATIC = "automatic", "Automatic"
    ADMIN_APPROVED = "admin_approved", "Admin approved"


class SecondaryMarketListingEventType(models.TextChoices):
    CREATED = "created", "Created"
    AUTO_PUBLISHED = "auto_published", "Auto published"
    APPROVAL_REQUESTED = "approval_requested", "Approval requested"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    REMOVED = "removed", "Removed"
    SOLD = "sold", "Sold"


class SecondaryMarketListing(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    holding = models.ForeignKey(
        "holdings.InvestorLoanHolding",
        on_delete=models.PROTECT,
        related_name="secondary_market_listings",
    )
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="secondary_market_listings",
    )
    seller_user_id = models.UUIDField()
    status = models.CharField(
        max_length=64,
        choices=SecondaryMarketListingStatus.choices,
    )
    publication_type = models.CharField(
        max_length=64,
        choices=SecondaryMarketListingPublicationType.choices,
    )
    current_principal_minor = models.BigIntegerField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="secondary_market_listings",
    )
    price_bps = models.PositiveIntegerField()
    transfer_price_minor = models.BigIntegerField()
    discount_premium_bps = models.IntegerField()
    accrued_interest_minor = models.BigIntegerField(default=0)
    accrued_interest_from_date = models.DateField(null=True, blank=True)
    accrued_interest_to_date = models.DateField()
    maker_fee_bps = models.PositiveIntegerField()
    taker_fee_bps = models.PositiveIntegerField()
    minimum_maker_fee_minor = models.BigIntegerField(default=0)
    minimum_taker_fee_minor = models.BigIntegerField(default=0)
    maker_fee_minor = models.BigIntegerField(default=0)
    taker_fee_minor = models.BigIntegerField(default=0)
    seller_net_proceeds_minor = models.BigIntegerField()
    buyer_total_cost_minor = models.BigIntegerField()
    loan_status_at_listing = models.CharField(max_length=64)
    days_past_due = models.PositiveIntegerField(default=0)
    last_payment_date = models.DateField(null=True, blank=True)
    risk_acknowledgement_required = models.BooleanField(default=False)
    document_acceptance = models.ForeignKey(
        "documents.DocumentAcceptanceEvidence",
        on_delete=models.PROTECT,
        related_name="secondary_market_listings",
    )
    public_disclosure_note = models.TextField(blank=True)
    listed_at = models.DateTimeField(null=True, blank=True)
    approved_by_admin_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_reason = models.TextField(blank=True)
    rejected_by_admin_id = models.UUIDField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    removed_by_admin_id = models.UUIDField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removal_reason = models.TextField(blank=True)
    sold_to_user_id = models.UUIDField(null=True, blank=True)
    sold_at = models.DateTimeField(null=True, blank=True)
    created_by_user_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-listed_at", "-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(current_principal_minor__gt=0),
                name="secondary_listing_current_principal_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(price_bps__gt=0),
                name="secondary_listing_price_bps_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(transfer_price_minor__gt=0),
                name="secondary_listing_transfer_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(accrued_interest_minor__gte=0),
                name="secondary_listing_accrued_interest_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_maker_fee_minor__gte=0)
                & models.Q(minimum_taker_fee_minor__gte=0)
                & models.Q(maker_fee_minor__gte=0)
                & models.Q(taker_fee_minor__gte=0),
                name="secondary_listing_fees_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(seller_net_proceeds_minor__gte=0),
                name="secondary_listing_seller_net_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(buyer_total_cost_minor__gt=0),
                name="secondary_listing_buyer_total_positive",
            ),
            models.UniqueConstraint(
                fields=["holding"],
                condition=models.Q(
                    status__in=[
                        SecondaryMarketListingStatus.ACTIVE,
                        SecondaryMarketListingStatus.APPROVAL_REQUESTED,
                    ]
                ),
                name="unique_open_secondary_listing_per_holding",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "listed_at"]),
            models.Index(fields=["seller_user_id", "status", "created_at"]),
            models.Index(fields=["holding", "status"]),
            models.Index(fields=["loan", "status"]),
            models.Index(fields=["currency", "status"]),
        ]


class SecondaryMarketListingEvent(AppendOnlyModel):
    listing = models.ForeignKey(
        SecondaryMarketListing,
        on_delete=models.PROTECT,
        related_name="events",
    )
    holding_id = models.UUIDField()
    loan_id = models.UUIDField()
    seller_user_id = models.UUIDField()
    event_type = models.CharField(
        max_length=64,
        choices=SecondaryMarketListingEventType.choices,
    )
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    previous_status = models.CharField(max_length=64, blank=True)
    new_status = models.CharField(max_length=64, blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["listing", "occurred_at"]),
            models.Index(fields=["loan_id", "event_type"]),
            models.Index(fields=["holding_id", "event_type"]),
            models.Index(fields=["seller_user_id", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]


class SecondaryMarketPurchase(AppendOnlyModel, TimestampedModel):
    listing = models.ForeignKey(
        SecondaryMarketListing,
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    seller_holding = models.ForeignKey(
        "holdings.InvestorLoanHolding",
        on_delete=models.PROTECT,
        related_name="secondary_market_sales",
    )
    buyer_holding = models.ForeignKey(
        "holdings.InvestorLoanHolding",
        on_delete=models.PROTECT,
        related_name="secondary_market_purchases",
    )
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="secondary_market_purchases",
    )
    buyer_user_id = models.UUIDField()
    seller_user_id = models.UUIDField()
    currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="secondary_market_purchases",
    )
    current_principal_minor = models.BigIntegerField()
    price_bps = models.PositiveIntegerField()
    transfer_price_minor = models.BigIntegerField()
    discount_premium_bps = models.IntegerField()
    accrued_interest_minor = models.BigIntegerField(default=0)
    accrued_interest_from_date = models.DateField(null=True, blank=True)
    accrued_interest_to_date = models.DateField()
    maker_fee_bps = models.PositiveIntegerField()
    taker_fee_bps = models.PositiveIntegerField()
    minimum_maker_fee_minor = models.BigIntegerField(default=0)
    minimum_taker_fee_minor = models.BigIntegerField(default=0)
    maker_fee_minor = models.BigIntegerField(default=0)
    taker_fee_minor = models.BigIntegerField(default=0)
    seller_net_proceeds_minor = models.BigIntegerField()
    buyer_total_cost_minor = models.BigIntegerField()
    loan_status_at_purchase = models.CharField(max_length=64)
    days_past_due = models.PositiveIntegerField(default=0)
    last_payment_date = models.DateField(null=True, blank=True)
    purchase_document_acceptance = models.ForeignKey(
        "documents.DocumentAcceptanceEvidence",
        on_delete=models.PROTECT,
        related_name="secondary_market_purchases",
    )
    risk_acknowledgement_accepted = models.BooleanField(default=False)
    ledger_journal_entry = models.ForeignKey(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        related_name="secondary_market_purchases",
    )
    seller_balance_lot = models.ForeignKey(
        "ledger.InvestorBalanceLot",
        on_delete=models.PROTECT,
        related_name="secondary_market_sales",
    )
    buyer_lot_allocations = models.JSONField(default=list, blank=True)
    purchased_at = models.DateTimeField()
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-purchased_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["listing"], name="unique_purchase_per_listing"),
            models.CheckConstraint(
                condition=models.Q(current_principal_minor__gt=0),
                name="secondary_purchase_current_principal_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(price_bps__gt=0),
                name="secondary_purchase_price_bps_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(transfer_price_minor__gt=0),
                name="secondary_purchase_transfer_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(accrued_interest_minor__gte=0),
                name="secondary_purchase_accrued_interest_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_maker_fee_minor__gte=0)
                & models.Q(minimum_taker_fee_minor__gte=0)
                & models.Q(maker_fee_minor__gte=0)
                & models.Q(taker_fee_minor__gte=0),
                name="secondary_purchase_fees_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(seller_net_proceeds_minor__gte=0),
                name="secondary_purchase_seller_net_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(buyer_total_cost_minor__gt=0),
                name="secondary_purchase_buyer_total_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["listing", "purchased_at"]),
            models.Index(fields=["buyer_user_id", "purchased_at"]),
            models.Index(fields=["seller_user_id", "purchased_at"]),
            models.Index(fields=["loan", "purchased_at"]),
            models.Index(fields=["currency", "purchased_at"]),
        ]
