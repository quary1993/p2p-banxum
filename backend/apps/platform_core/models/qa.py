from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


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


class QaDatasetReset(AppendOnlyModel):
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor_user_id = models.UUIDField()
    environment = models.CharField(max_length=32)
    backup_path = models.TextField()
    backup_sha256 = models.CharField(max_length=64)
    summary = models.JSONField(default=dict)


class ArchivedInvestorActivity(AppendOnlyModel):
    """Pre-reset display evidence, never a source for balances or investment metrics."""

    investor_user_id = models.UUIDField()
    stream = models.CharField(max_length=32)
    source_id = models.CharField(max_length=128)
    occurred_at = models.DateTimeField()
    archived_at = models.DateTimeField(auto_now_add=True)
    reset_id = models.UUIDField()
    payload = models.JSONField()

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["investor_user_id", "stream", "source_id"],
                name="qa_activity_source_unique",
            )
        ]
        indexes = [models.Index(fields=["investor_user_id", "stream", "occurred_at"])]
