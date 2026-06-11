from __future__ import annotations

import uuid

from django.db import models

from backend.apps.platform_core.models.base import TimestampedModel


class ScheduledJobRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class ScheduledJobRun(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_name = models.CharField(max_length=128)
    run_key = models.CharField(max_length=200, unique=True)
    status = models.CharField(
        max_length=32,
        choices=ScheduledJobRunStatus.choices,
        default=ScheduledJobRunStatus.RUNNING,
    )
    scheduled_for = models.DateTimeField()
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=1)
    actor_user_id = models.UUIDField(null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [
            models.Index(fields=["job_name", "scheduled_for"]),
            models.Index(fields=["status", "started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.job_name}:{self.run_key}:{self.status}"
