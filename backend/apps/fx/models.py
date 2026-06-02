from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class FxExchangeStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"


class FxEventType(models.TextChoices):
    QUOTE_ISSUED = "quote_issued", "Quote issued"
    QUOTE_SANITY_REJECTED = "quote_sanity_rejected", "Quote sanity rejected"
    EXCHANGE_COMPLETED = "exchange_completed", "Exchange completed"


class FxQuote(AppendOnlyModel, TimestampedModel):
    investor_user_id = models.UUIDField()
    source_currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="fx_quotes_as_source",
    )
    target_currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="fx_quotes_as_target",
    )
    source_amount_minor = models.BigIntegerField()
    provider = models.CharField(max_length=64)
    provider_quote_id = models.CharField(max_length=128, blank=True)
    rate = models.DecimalField(max_digits=24, decimal_places=12)
    previous_day_average_rate = models.DecimalField(
        max_digits=24,
        decimal_places=12,
        null=True,
        blank=True,
    )
    platform_fee_bps = models.PositiveIntegerField()
    gross_target_amount_minor = models.BigIntegerField()
    fee_minor = models.BigIntegerField()
    target_amount_minor = models.BigIntegerField()
    limit_chf_equivalent_minor = models.BigIntegerField()
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    provider_rate_timestamp = models.DateTimeField()
    sanity_check_passed = models.BooleanField(default=True)
    sanity_metadata = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-issued_at", "-id"]
        indexes = [
            models.Index(fields=["investor_user_id", "issued_at"]),
            models.Index(fields=["source_currency", "target_currency", "issued_at"]),
            models.Index(fields=["expires_at"]),
        ]


class FxExchange(AppendOnlyModel, TimestampedModel):
    quote = models.ForeignKey(FxQuote, on_delete=models.PROTECT, related_name="exchanges")
    investor_user_id = models.UUIDField()
    source_currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="fx_exchanges_as_source",
    )
    target_currency = models.ForeignKey(
        "platform_core.Currency",
        on_delete=models.PROTECT,
        related_name="fx_exchanges_as_target",
    )
    source_amount_minor = models.BigIntegerField()
    rate = models.DecimalField(max_digits=24, decimal_places=12)
    platform_fee_bps = models.PositiveIntegerField()
    gross_target_amount_minor = models.BigIntegerField()
    fee_minor = models.BigIntegerField()
    target_amount_minor = models.BigIntegerField()
    limit_chf_equivalent_minor = models.BigIntegerField()
    status = models.CharField(
        max_length=32,
        choices=FxExchangeStatus.choices,
        default=FxExchangeStatus.COMPLETED,
    )
    source_journal_entry = models.ForeignKey(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        related_name="fx_source_exchanges",
    )
    target_journal_entry = models.ForeignKey(
        "ledger.LedgerJournalEntry",
        on_delete=models.PROTECT,
        related_name="fx_target_exchanges",
    )
    target_balance_lot = models.ForeignKey(
        "ledger.InvestorBalanceLot",
        on_delete=models.PROTECT,
        related_name="fx_exchanges",
    )
    source_lot_allocations = models.JSONField(default=list, blank=True)
    executed_at = models.DateTimeField()
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-executed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["quote"], name="unique_fx_exchange_per_quote"),
        ]
        indexes = [
            models.Index(fields=["investor_user_id", "executed_at"]),
            models.Index(fields=["source_currency", "target_currency", "executed_at"]),
            models.Index(fields=["quote"]),
        ]


class FxEvent(AppendOnlyModel):
    quote = models.ForeignKey(
        FxQuote,
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
    )
    exchange = models.ForeignKey(
        FxExchange,
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=64, choices=FxEventType.choices)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]
