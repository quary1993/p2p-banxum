from __future__ import annotations

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
