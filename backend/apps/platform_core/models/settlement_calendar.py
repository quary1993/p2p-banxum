"""IP of Webby-Soft SRL. 18.4 (F17): the CHF and EUR settlement calendars kept by operations.

A year is preloaded from the rule list (``platform_core.domain.settlement_calendar``); operations
add or remove days in the admin and confirm the year once it matches the bank's calendar. Return
dates (18.4) and due dates (18.6) use the same calendars. Reference data: kept across QA resets.
"""

from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import TimestampedModel


class SettlementCurrency(models.TextChoices):
    CHF = "CHF", "CHF (SIX SIC)"
    EUR = "EUR", "EUR (TARGET)"


class SettlementHolidaySource(models.TextChoices):
    RULE = "rule", "Preloaded by rule"
    ADMIN = "admin", "Added by an admin"


class SettlementCalendarYear(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    currency = models.CharField(max_length=3, choices=SettlementCurrency.choices)
    year = models.PositiveSmallIntegerField()
    preloaded_at = models.DateTimeField()
    preloaded_by = models.CharField(max_length=128)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by_admin_id = models.UUIDField(null=True, blank=True)
    confirmation_note = models.TextField(blank=True)
    # Audit S3-4: every added or removed day gives the year a new revision and clears its
    # confirmation. ``reconfirmation_needed_since`` is set while a year that was confirmed
    # waits to be confirmed again after such a change.
    revision = models.PositiveIntegerField(default=0)
    reconfirmation_needed_since = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["currency", "year"]
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "year"], name="platform_core_one_calendar_per_currency_year"
            )
        ]

    def __str__(self) -> str:
        return f"{self.currency} {self.year}"


class SettlementHoliday(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    currency = models.CharField(max_length=3, choices=SettlementCurrency.choices)
    date = models.DateField()
    name = models.CharField(max_length=128)
    source = models.CharField(max_length=16, choices=SettlementHolidaySource.choices)
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=128)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by_admin_id = models.UUIDField(null=True, blank=True)
    removal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["currency", "date"]
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "date"], name="platform_core_one_holiday_per_currency_date"
            )
        ]
        indexes = [models.Index(fields=["currency", "is_active", "date"])]

    def __str__(self) -> str:
        return f"{self.currency} {self.date.isoformat()} {self.name}"
