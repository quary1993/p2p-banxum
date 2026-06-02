from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from backend.apps.platform_core.models.base import AppendOnlyModel, TimestampedModel


class AdminTaskType(models.TextChoices):
    KYC_MANUAL_REVIEW = "kyc_manual_review", "KYC manual review"
    ACCOUNT_ACCESS_REVIEW = "account_access_review", "Account access review"
    BORROWER_ONBOARDING = "borrower_onboarding", "Borrower onboarding"
    LOAN_SETUP = "loan_setup", "Loan setup"
    PAYMENT_RECONCILIATION = "payment_reconciliation", "Payment reconciliation"
    FX_SETTLEMENT = "fx_settlement", "FX settlement"
    DOCUMENT_REVIEW = "document_review", "Document review"
    EMAIL_DELIVERY_FAILURE = "email_delivery_failure", "Email delivery failure"
    REPORTING = "reporting", "Reporting"
    SUPPORT = "support", "Support"
    OTHER = "other", "Other"


class AdminTaskPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class AdminTaskStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In progress"
    WAITING = "waiting", "Waiting"
    RESOLVED = "resolved", "Resolved"
    CANCELLED = "cancelled", "Cancelled"


TERMINAL_ADMIN_TASK_STATUSES = frozenset(
    {
        AdminTaskStatus.RESOLVED,
        AdminTaskStatus.CANCELLED,
    }
)


class AdminTaskEventType(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    STATUS_CHANGED = "status_changed", "Status changed"
    ASSIGNED = "assigned", "Assigned"


class AdminTask(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_type = models.CharField(max_length=64, choices=AdminTaskType.choices)
    title = models.CharField(max_length=255)
    priority = models.CharField(
        max_length=32,
        choices=AdminTaskPriority.choices,
        default=AdminTaskPriority.NORMAL,
    )
    status = models.CharField(
        max_length=32,
        choices=AdminTaskStatus.choices,
        default=AdminTaskStatus.OPEN,
    )
    assigned_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_admin_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_admin_tasks",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    related_object_type = models.CharField(max_length=128, blank=True)
    related_object_id = models.CharField(max_length=128, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_note = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "due_at", "-priority", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["task_type", "status"]),
            models.Index(fields=["assigned_admin", "status"]),
            models.Index(fields=["due_at"]),
            models.Index(fields=["related_object_type", "related_object_id"]),
        ]

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_ADMIN_TASK_STATUSES

    def __str__(self) -> str:
        return f"{self.task_type}:{self.title}"


class AdminTaskEvent(AppendOnlyModel):
    task = models.ForeignKey(AdminTask, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=32, choices=AdminTaskEventType.choices)
    actor_user_id = models.UUIDField()
    actor_account_type = models.CharField(max_length=64)
    previous_status = models.CharField(max_length=32, blank=True)
    new_status = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["task", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["actor_user_id", "occurred_at"]),
        ]
