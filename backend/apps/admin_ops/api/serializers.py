from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.admin_ops.models import (
    AdminTask,
    AdminTaskEvent,
    AdminTaskPriority,
    AdminTaskStatus,
    AdminTaskType,
)
from backend.apps.platform_core.models import AuditEvent


class AdminTaskSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    task_type = serializers.CharField()
    title = serializers.CharField()
    priority = serializers.CharField()
    status = serializers.CharField()
    assigned_admin_id = serializers.UUIDField(allow_null=True)
    created_by_id = serializers.UUIDField()
    due_at = serializers.DateTimeField(allow_null=True)
    notes = serializers.CharField()
    related_object_type = serializers.CharField()
    related_object_id = serializers.CharField()
    completed_at = serializers.DateTimeField(allow_null=True)
    completion_note = serializers.CharField()
    is_terminal = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class AdminTaskEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    task_id = serializers.UUIDField(source="task.id")
    event_type = serializers.CharField()
    actor_user_id = serializers.UUIDField()
    actor_account_type = serializers.CharField()
    previous_status = serializers.CharField()
    new_status = serializers.CharField()
    note = serializers.CharField()
    metadata = serializers.JSONField()
    occurred_at = serializers.DateTimeField()


class AdminTaskCreateRequestSerializer(serializers.Serializer[Any]):
    task_type = serializers.ChoiceField(choices=AdminTaskType.choices)
    title = serializers.CharField(max_length=255)
    priority = serializers.ChoiceField(
        choices=AdminTaskPriority.choices,
        default=AdminTaskPriority.NORMAL,
    )
    assigned_admin_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    related_object_type = serializers.CharField(required=False, allow_blank=True, max_length=128)
    related_object_id = serializers.CharField(required=False, allow_blank=True, max_length=128)


class AdminTaskUpdateRequestSerializer(serializers.Serializer[Any]):
    task_type = serializers.ChoiceField(required=False, choices=AdminTaskType.choices)
    title = serializers.CharField(required=False, max_length=255)
    priority = serializers.ChoiceField(required=False, choices=AdminTaskPriority.choices)
    status = serializers.ChoiceField(required=False, choices=AdminTaskStatus.choices)
    assigned_admin_id = serializers.UUIDField(required=False, allow_null=True)
    clear_assigned_admin = serializers.BooleanField(required=False, default=False)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    clear_due_at = serializers.BooleanField(required=False, default=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    completion_note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("At least one task change is required.")
        if attrs.get("clear_assigned_admin") and attrs.get("assigned_admin_id") is not None:
            raise serializers.ValidationError(
                "Use either assigned_admin_id or clear_assigned_admin, not both."
            )
        if attrs.get("clear_due_at") and attrs.get("due_at") is not None:
            raise serializers.ValidationError("Use either due_at or clear_due_at, not both.")
        return attrs


class AdminTaskListQuerySerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(required=False, choices=AdminTaskStatus.choices)
    task_type = serializers.ChoiceField(required=False, choices=AdminTaskType.choices)
    priority = serializers.ChoiceField(required=False, choices=AdminTaskPriority.choices)
    assigned_admin_id = serializers.UUIDField(required=False)
    related_object_type = serializers.CharField(required=False, allow_blank=True, max_length=128)
    related_object_id = serializers.CharField(required=False, allow_blank=True, max_length=128)
    due_before = serializers.DateTimeField(required=False)
    due_after = serializers.DateTimeField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


class AuditEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    occurred_at = serializers.DateTimeField()
    actor_type = serializers.CharField()
    actor_id = serializers.CharField()
    action = serializers.CharField()
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    request_id = serializers.CharField()
    metadata = serializers.JSONField()


class AuditEventQuerySerializer(serializers.Serializer[Any]):
    action = serializers.CharField(required=False, allow_blank=True, max_length=128)
    target_type = serializers.CharField(required=False, allow_blank=True, max_length=128)
    target_id = serializers.CharField(required=False, allow_blank=True, max_length=128)
    actor_type = serializers.CharField(required=False, allow_blank=True, max_length=64)
    actor_id = serializers.CharField(required=False, allow_blank=True, max_length=128)
    occurred_from = serializers.DateTimeField(required=False)
    occurred_to = serializers.DateTimeField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=250, default=100)


def serialize_admin_task(task: AdminTask) -> dict[str, Any]:
    return dict(AdminTaskSerializer(task).data)


def serialize_admin_task_event(event: AdminTaskEvent) -> dict[str, Any]:
    return dict(AdminTaskEventSerializer(event).data)


def serialize_audit_event(event: AuditEvent) -> dict[str, Any]:
    return dict(AuditEventSerializer(event).data)
