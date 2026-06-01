from __future__ import annotations

from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel


class AuditEvent(AppendOnlyModel):
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor_type = models.CharField(max_length=64)
    actor_id = models.CharField(max_length=128)
    action = models.CharField(max_length=128)
    target_type = models.CharField(max_length=128, blank=True)
    target_id = models.CharField(max_length=128, blank=True)
    request_id = models.CharField(max_length=128, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["action", "occurred_at"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["actor_type", "actor_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.id}"
