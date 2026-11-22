from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import TimestampedModel


class Currency(TimestampedModel):
    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=64)
    minor_units = models.PositiveSmallIntegerField(default=2)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class SnbReferenceRate(TimestampedModel):
    """18.9 (Q03): the SNB reference rate used to count EUR debts in CHF for the creditor modes.

    One rate per currency and day: CHF for one unit of the currency. Entered by an admin from the
    SNB publication (source and date kept); the last rate on or before the day of a check applies.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    currency = models.CharField(max_length=3)
    rate_date = models.DateField()
    chf_per_unit = models.DecimalField(max_digits=12, decimal_places=6)
    source = models.CharField(max_length=255)
    entered_by_admin_id = models.UUIDField()

    class Meta:
        ordering = ["-rate_date", "currency"]
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "rate_date"], name="platform_core_snb_rate_unique_day"
            ),
            models.CheckConstraint(
                condition=models.Q(chf_per_unit__gt=0), name="platform_core_snb_rate_positive"
            ),
        ]
