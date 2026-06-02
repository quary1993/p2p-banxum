from __future__ import annotations

from django.contrib import admin

from backend.apps.admin_ops.models import AdminTask, AdminTaskEvent


@admin.register(AdminTask)
class AdminTaskAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "title",
        "task_type",
        "priority",
        "status",
        "assigned_admin",
        "due_at",
        "created_at",
    )
    list_filter = ("task_type", "priority", "status")
    search_fields = ("title", "notes", "related_object_type", "related_object_id")
    readonly_fields = ("id", "created_at", "updated_at", "completed_at")


@admin.register(AdminTaskEvent)
class AdminTaskEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("task", "event_type", "actor_user_id", "occurred_at")
    list_filter = ("event_type", "actor_account_type")
    search_fields = ("task__title", "actor_user_id", "note")
    readonly_fields = (
        "id",
        "task",
        "event_type",
        "actor_user_id",
        "actor_account_type",
        "previous_status",
        "new_status",
        "note",
        "metadata",
        "occurred_at",
    )

    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False
