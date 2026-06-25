from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import TimestampedModel


class QaDevModeState(TimestampedModel):
    singleton_id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    is_enabled = models.BooleanField(default=False)
    entered_at = models.DateTimeField(null=True, blank=True)
    entered_by_user_id = models.UUIDField(null=True, blank=True)
    current_time = models.DateTimeField(null=True, blank=True)
    snapshot_path = models.TextField(blank=True)
    snapshot_created_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    last_advanced_at = models.DateTimeField(null=True, blank=True)
    last_advance_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(singleton_id=1),
                name="qa_dev_mode_singleton_id_one",
            )
        ]

    def __str__(self) -> str:
        return "qa-dev-mode:enabled" if self.is_enabled else "qa-dev-mode:disabled"
