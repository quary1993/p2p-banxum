from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class PlatformSetting(TimestampedModel):
    key = models.CharField(max_length=128, unique=True)
    value = models.JSONField(default=dict, blank=True)
    value_type = models.CharField(max_length=32, default="json")
    current_version = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class PlatformSettingVersion(AppendOnlyModel):
    key = models.CharField(max_length=128)
    version = models.PositiveIntegerField()
    value = models.JSONField(default=dict, blank=True)
    value_type = models.CharField(max_length=32, default="json")
    changed_by_type = models.CharField(max_length=64)
    changed_by_id = models.CharField(max_length=128)
    reason = models.TextField(blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["key", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["key", "version"],
                name="unique_platform_setting_version",
            )
        ]
        indexes = [models.Index(fields=["key", "occurred_at"])]
